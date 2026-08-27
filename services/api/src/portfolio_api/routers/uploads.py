from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile as StarletteUploadFile

from portfolio_api.config import Settings, get_settings
from portfolio_api.database import apply_tenant_scope, get_tenant_session
from portfolio_api.models import Job, Portfolio, Upload
from portfolio_api.observability import current_trace_id
from portfolio_api.schemas import SourceRole, UploadInitiate, UploadInitiated, UploadRead
from portfolio_api.services.control_plane import (
    audit_event,
    idempotent_replay,
    store_idempotency,
)
from portfolio_api.services.file_security import (
    MalwareDetected,
    MalwareScannerUnavailable,
    scan_with_clamav,
)
from portfolio_api.services.ingestion import UnsafeFileError, validate_and_summarize
from portfolio_api.services.publication import persist_extraction
from portfolio_api.services.reconciliation import CertifiedCsvError, parse_certified_csv
from portfolio_api.services.storage import QuarantineStorage, build_quarantine_storage
from portfolio_api.tenant import RequestContext, request_context

router = APIRouter(prefix="/v1/uploads", tags=["uploads"])


async def _portfolio_or_404(
    session: AsyncSession, context: RequestContext, portfolio_id: UUID
) -> Portfolio:
    portfolio = await session.scalar(
        select(Portfolio).where(
            Portfolio.id == portfolio_id,
            Portfolio.tenant_id == context.tenant_id,
        )
    )
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found.")
    return portfolio


async def _scan(content: bytes, settings: Settings) -> None:
    if not settings.malware_scan_required:
        return
    try:
        await run_in_threadpool(
            scan_with_clamav,
            content,
            settings.clamav_host,
            settings.clamav_port,
        )
    except MalwareDetected as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "MALWARE_DETECTED", "message": "The file was rejected."},
        ) from error
    except MalwareScannerUnavailable as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "MALWARE_SCANNER_UNAVAILABLE",
                "message": "File intake is paused because scanning is unavailable.",
            },
        ) from error


async def _accept_direct_upload(
    *,
    portfolio_id: UUID,
    source_role: SourceRole,
    file: UploadFile,
    context: RequestContext,
    session: AsyncSession,
) -> Upload:
    settings = get_settings()
    if not settings.direct_upload_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DIRECT_UPLOAD_DISABLED", "message": "Use secure upload initiation."},
        )
    await _portfolio_or_404(session, context, portfolio_id)
    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "FILE_TOO_LARGE", "message": "The file exceeds the size limit."},
        )
    await _scan(content, settings)
    try:
        summary = await run_in_threadpool(
            validate_and_summarize,
            file.filename or "upload",
            content,
            source_role,
            file.content_type,
        )
    except UnsafeFileError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": error.code, "message": str(error)},
        ) from error
    duplicate = await session.scalar(
        select(Upload.id).where(
            Upload.tenant_id == context.tenant_id,
            Upload.portfolio_id == portfolio_id,
            Upload.sha256 == summary.sha256,
            Upload.source_role == source_role,
        )
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DUPLICATE_UPLOAD", "message": "This file was already accepted."},
        )
    upload_id = uuid4()
    storage = build_quarantine_storage(settings)
    object_key = await run_in_threadpool(
        storage.put,
        context.tenant_id,
        upload_id,
        Path(file.filename or "").suffix,
        content,
    )
    upload = Upload(
        id=upload_id,
        tenant_id=context.tenant_id,
        portfolio_id=portfolio_id,
        created_by=context.user_id,
        object_key=object_key,
        original_name=Path(file.filename or "upload").name[:255],
        declared_type=file.content_type,
        detected_type=summary.detected_type,
        source_role=source_role,
        authority_level=summary.authority_level,
        size_bytes=len(content),
        sha256=summary.sha256,
        state=summary.state,
        parser_summary=summary.to_dict(),
    )
    session.add(upload)
    session.add(
        audit_event(
            context,
            action="upload.accepted",
            resource_type="upload",
            resource_id=upload.id,
            details={
                "portfolio_id": str(portfolio_id),
                "source_role": source_role,
                "detected_type": summary.detected_type,
                "path": "development_direct",
            },
        )
    )
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        await run_in_threadpool(storage.delete, object_key)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DUPLICATE_UPLOAD", "message": "This file was already accepted."},
        ) from error
    await apply_tenant_scope(session, context.tenant_id, context.user_id)
    await session.refresh(upload)
    return upload


async def _initiate(
    payload: UploadInitiate,
    context: RequestContext,
    session: AsyncSession,
) -> UploadInitiated:
    settings = get_settings()
    await _portfolio_or_404(session, context, payload.portfolio_id)
    if Path(payload.original_name).suffix.lower() != ".csv":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "R1_CSV_ONLY", "message": "R1 accepts certified CSV files only."},
        )
    duplicate = await session.scalar(
        select(Upload.id).where(
            Upload.tenant_id == context.tenant_id,
            Upload.portfolio_id == payload.portfolio_id,
            Upload.sha256 == payload.sha256,
            Upload.source_role == payload.source_role,
        )
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DUPLICATE_UPLOAD", "message": "This file was already initiated."},
        )
    upload_id = uuid4()
    storage = build_quarantine_storage(settings)
    object_key, presigned = await run_in_threadpool(
        storage.presign,
        context.tenant_id,
        upload_id,
        ".csv",
        sha256=payload.sha256,
        content_type=payload.content_type,
        max_size=min(payload.size_bytes, settings.max_upload_bytes),
        expires_seconds=settings.object_storage_presign_seconds,
    )
    upload = Upload(
        id=upload_id,
        tenant_id=context.tenant_id,
        portfolio_id=payload.portfolio_id,
        created_by=context.user_id,
        object_key=object_key,
        original_name=Path(payload.original_name).name,
        declared_type=payload.content_type,
        detected_type="pending",
        source_role=payload.source_role,
        authority_level="ledger_candidate",
        size_bytes=payload.size_bytes,
        sha256=payload.sha256,
        state="initiated",
        parser_summary={"schema": "spi-ledger-csv/v1"},
    )
    session.add(upload)
    session.add(
        audit_event(
            context,
            action="upload.initiated",
            resource_type="upload",
            resource_id=upload.id,
            details={
                "portfolio_id": str(payload.portfolio_id),
                "source_role": payload.source_role,
                "size_bytes": payload.size_bytes,
            },
        )
    )
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DUPLICATE_UPLOAD", "message": "This file was already initiated."},
        ) from error
    return UploadInitiated(
        upload_id=upload.id,
        state="initiated",
        upload_url=str(presigned["upload_url"]),
        method=presigned["method"],
        fields=presigned["fields"],
        required_headers=presigned["required_headers"],
        expires_at=datetime.now(UTC) + timedelta(seconds=settings.object_storage_presign_seconds),
        version=upload.version,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def initiate_or_direct_upload(
    request: Request,
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    content_type = request.headers.get("content-type", "").lower()
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        file = form.get("file")
        if not isinstance(file, StarletteUploadFile):
            raise HTTPException(status_code=422, detail="A file is required.")
        try:
            portfolio_id = UUID(str(form.get("portfolio_id")))
            source_role = str(form.get("source_role"))
        except ValueError as error:
            raise HTTPException(status_code=422, detail="Invalid portfolio_id.") from error
        if source_role not in SourceRole.__args__:
            raise HTTPException(status_code=422, detail="Invalid source_role.")
        try:
            return await _accept_direct_upload(
                portfolio_id=portfolio_id,
                source_role=source_role,  # type: ignore[arg-type]
                file=file,
                context=context,
                session=session,
            )
        finally:
            await file.close()
    try:
        payload = UploadInitiate.model_validate(await request.json())
    except (ValidationError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "INVALID_UPLOAD_REQUEST", "message": str(error)},
        ) from error
    return await _initiate(payload, context, session)


@router.post("/direct", response_model=UploadRead, status_code=status.HTTP_201_CREATED)
async def direct_upload(
    portfolio_id: UUID = Form(...),
    source_role: SourceRole = Form(...),
    file: UploadFile = File(...),
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> Upload:
    return await _accept_direct_upload(
        portfolio_id=portfolio_id,
        source_role=source_role,
        file=file,
        context=context,
        session=session,
    )


@router.put("/{upload_id}/content", status_code=status.HTTP_204_NO_CONTENT)
async def put_local_upload_content(
    upload_id: UUID,
    request: Request,
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> None:
    settings = get_settings()
    if settings.storage_backend.lower() != "local":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    upload = await session.scalar(
        select(Upload).where(
            Upload.id == upload_id,
            Upload.tenant_id == context.tenant_id,
            Upload.state == "initiated",
        )
    )
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found.")
    content = await request.body()
    if len(content) != upload.size_bytes or hashlib.sha256(content).hexdigest() != upload.sha256:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "UPLOAD_INTEGRITY_FAILED", "message": "Size or checksum differs."},
        )
    storage = build_quarantine_storage(settings)
    await run_in_threadpool(
        storage.put,
        context.tenant_id,
        upload.id,
        ".csv",
        content,
    )
    upload.state = "uploaded"
    upload.version += 1
    await session.commit()


@router.post("/{upload_id}/complete", status_code=status.HTTP_202_ACCEPTED)
async def complete_upload(
    upload_id: UUID,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, object]:
    settings = get_settings()
    endpoint = f"POST:/v1/uploads/{upload_id}/complete"
    request_hash, replay, replay_status = await idempotent_replay(
        session,
        context,
        endpoint=endpoint,
        key=idempotency_key,
        request_body={"upload_id": str(upload_id)},
    )
    if replay is not None:
        return replay
    upload = await session.scalar(
        select(Upload).where(
            Upload.id == upload_id,
            Upload.tenant_id == context.tenant_id,
        )
    )
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found.")
    if upload.state not in {"initiated", "uploaded"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "UPLOAD_STATE_CONFLICT", "message": "Upload cannot be completed."},
        )
    storage: QuarantineStorage = build_quarantine_storage(settings)
    try:
        object_info = await run_in_threadpool(storage.head, upload.object_key)
        content = await run_in_threadpool(storage.read, upload.object_key)
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "UPLOAD_OBJECT_MISSING", "message": "Uploaded object was not found."},
        ) from error
    actual_hash = hashlib.sha256(content).hexdigest()
    if object_info.size_bytes != upload.size_bytes or actual_hash != upload.sha256:
        upload.state = "failed"
        upload.error_code = "UPLOAD_INTEGRITY_FAILED"
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "UPLOAD_INTEGRITY_FAILED", "message": "Size or checksum differs."},
        )
    metadata_hash = object_info.metadata.get("sha256")
    if settings.storage_backend.lower() == "s3" and metadata_hash != upload.sha256:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "UPLOAD_METADATA_INVALID", "message": "Checksum metadata is missing."},
        )

    job = Job(
        id=uuid4(),
        tenant_id=context.tenant_id,
        job_type="certified_csv_extraction",
        state="running",
        resource_type="upload",
        resource_id=upload.id,
        attempts=1,
        trace_id=current_trace_id(),
        started_at=datetime.now(UTC),
    )
    session.add(job)
    upload.state = "scanning"
    try:
        await _scan(content, settings)
        upload.state = "parsing"
        summary = await run_in_threadpool(
            validate_and_summarize,
            upload.original_name,
            content,
            upload.source_role,
            upload.declared_type,
        )
        parsed = await run_in_threadpool(parse_certified_csv, content)
        upload.detected_type = summary.detected_type
        upload.authority_level = summary.authority_level
        upload.parser_summary = summary.to_dict()
        document, extraction, batch = await persist_extraction(session, context, upload, parsed)
        job.state = "completed"
        job.completed_at = datetime.now(UTC)
        job.result = {
            "document_id": str(document.id),
            "extraction_run_id": str(extraction.id),
            "import_batch_id": str(batch.id),
        }
    except (UnsafeFileError, CertifiedCsvError) as error:
        job.state = "failed"
        job.error_code = error.code
        job.completed_at = datetime.now(UTC)
        upload.state = "failed"
        upload.error_code = error.code
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": error.code, "message": str(error)},
        ) from error
    response_body: dict[str, object] = {
        "job_id": str(job.id),
        "state": job.state,
        "resource_type": "upload",
        "resource_id": str(upload.id),
        **job.result,
    }
    store_idempotency(
        session,
        context,
        settings,
        endpoint=endpoint,
        key=str(idempotency_key),
        request_hash=request_hash,
        status_code=replay_status or status.HTTP_202_ACCEPTED,
        response_body=response_body,
    )
    await session.commit()
    return response_body


@router.get("/{upload_id}", response_model=UploadRead)
async def get_upload(
    upload_id: UUID,
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> Upload:
    upload = await session.scalar(
        select(Upload).where(
            Upload.id == upload_id,
            Upload.tenant_id == context.tenant_id,
        )
    )
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found.")
    return upload
