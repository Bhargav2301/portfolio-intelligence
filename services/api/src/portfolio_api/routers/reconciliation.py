from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from portfolio_api.config import get_settings
from portfolio_api.database import get_tenant_session
from portfolio_api.models import (
    Document,
    ExtractedRecord,
    ExtractionRun,
    ImportBatch,
    ImportBatchRecord,
    Job,
    LedgerVersion,
    ReconciliationCase,
)
from portfolio_api.schemas import (
    DocumentRead,
    ExtractedRecordPatch,
    ExtractedRecordRead,
    ExtractionRunRead,
    ImportBatchPublish,
    ImportBatchRead,
    ImportBatchValidate,
    JobRead,
    LedgerVersionRead,
    PublicationAccepted,
    ReconciliationCaseRead,
    ReconciliationResolution,
)
from portfolio_api.services.control_plane import (
    audit_event,
    idempotent_replay,
    parse_etag,
    require_recent_owner,
    require_version,
    store_idempotency,
)
from portfolio_api.services.publication import publish_import_batch, validate_import_batch
from portfolio_api.services.reconciliation import normalize_record
from portfolio_api.tenant import RequestContext, request_context

router = APIRouter(tags=["reconciliation"])


async def _batch_or_404(
    session: AsyncSession, context: RequestContext, batch_id: UUID
) -> ImportBatch:
    batch = await session.scalar(
        select(ImportBatch).where(
            ImportBatch.id == batch_id,
            ImportBatch.tenant_id == context.tenant_id,
        )
    )
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import batch not found.")
    return batch


@router.get("/v1/documents/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: UUID,
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> Document:
    document = await session.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == context.tenant_id,
        )
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return document


@router.get(
    "/v1/documents/{document_id}/extraction-runs",
    response_model=list[ExtractionRunRead],
)
async def list_extraction_runs(
    document_id: UUID,
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> list[ExtractionRun]:
    return list(
        await session.scalars(
            select(ExtractionRun)
            .where(
                ExtractionRun.document_id == document_id,
                ExtractionRun.tenant_id == context.tenant_id,
            )
            .order_by(ExtractionRun.started_at.desc())
        )
    )


@router.get("/v1/extractions/{extraction_id}/records", response_model=list[ExtractedRecordRead])
async def list_extracted_records(
    extraction_id: UUID,
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> list[ExtractedRecord]:
    return list(
        await session.scalars(
            select(ExtractedRecord)
            .where(
                ExtractedRecord.extraction_run_id == extraction_id,
                ExtractedRecord.tenant_id == context.tenant_id,
            )
            .order_by(ExtractedRecord.source_row)
        )
    )


@router.patch("/v1/extracted-records/{record_id}", response_model=ExtractedRecordRead)
async def patch_extracted_record(
    record_id: UUID,
    payload: ExtractedRecordPatch,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> ExtractedRecord:
    record = await session.scalar(
        select(ExtractedRecord).where(
            ExtractedRecord.id == record_id,
            ExtractedRecord.tenant_id == context.tenant_id,
        )
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found.")
    require_version(
        parse_etag(if_match, resource="Extracted record"), record.version, resource="Record"
    )
    try:
        normalized = normalize_record(payload.normalized_data, record.source_row)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "RECORD_VALIDATION_FAILED", "message": str(error)},
        ) from error
    record.normalized_data = normalized
    record.version += 1
    record.edited_by = context.user_id
    record.edited_at = datetime.now(UTC)
    record.state = "candidate"
    batch = await session.scalar(
        select(ImportBatch).where(
            ImportBatch.extraction_run_id == record.extraction_run_id,
            ImportBatch.tenant_id == context.tenant_id,
        )
    )
    if batch:
        batch.state = "draft"
        batch.validated_hash = None
        batch.version += 1
    session.add(
        audit_event(
            context,
            action="extracted_record.edited",
            resource_type="extracted_record",
            resource_id=record.id,
            details={"source_row": record.source_row, "record_version": record.version},
        )
    )
    await session.commit()
    response.headers["ETag"] = f'"{record.version}"'
    return record


@router.get(
    "/v1/import-batches/{batch_id}/reconciliation-cases",
    response_model=list[ReconciliationCaseRead],
)
async def list_reconciliation_cases(
    batch_id: UUID,
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> list[ReconciliationCase]:
    await _batch_or_404(session, context, batch_id)
    return list(
        await session.scalars(
            select(ReconciliationCase)
            .where(
                ReconciliationCase.import_batch_id == batch_id,
                ReconciliationCase.tenant_id == context.tenant_id,
            )
            .order_by(ReconciliationCase.created_at)
        )
    )


@router.post(
    "/v1/reconciliation-cases/{case_id}/resolve",
    response_model=ReconciliationCaseRead,
)
async def resolve_reconciliation_case(
    case_id: UUID,
    payload: ReconciliationResolution,
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> ReconciliationCase:
    case = await session.scalar(
        select(ReconciliationCase).where(
            ReconciliationCase.id == case_id,
            ReconciliationCase.tenant_id == context.tenant_id,
        )
    )
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")
    if case.state != "open":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CASE_ALREADY_RESOLVED", "message": "The case is already resolved."},
        )
    if payload.resolution == "replace":
        if not case.extracted_record_id or not payload.replacement_data:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"code": "REPLACEMENT_REQUIRED", "message": "Replacement data is required."},
            )
        record = await session.scalar(
            select(ExtractedRecord).where(
                ExtractedRecord.id == case.extracted_record_id,
                ExtractedRecord.tenant_id == context.tenant_id,
            )
        )
        if record is None:
            raise HTTPException(status_code=404, detail="Record not found.")
        try:
            record.normalized_data = normalize_record(payload.replacement_data, record.source_row)
        except ValueError as error:
            raise HTTPException(
                status_code=422,
                detail={"code": "RECORD_VALIDATION_FAILED", "message": str(error)},
            ) from error
        record.version += 1
        record.edited_by = context.user_id
        record.edited_at = datetime.now(UTC)
    case.state = "resolved"
    case.resolution = {"decision": payload.resolution, "reason": payload.reason}
    case.resolved_by = context.user_id
    case.resolved_at = datetime.now(UTC)
    session.add(
        audit_event(
            context,
            action="reconciliation_case.resolved",
            resource_type="reconciliation_case",
            resource_id=case.id,
            details={"decision": payload.resolution, "kind": case.kind},
        )
    )
    await session.commit()
    return case


@router.get("/v1/import-batches/{batch_id}", response_model=ImportBatchRead)
async def get_import_batch(
    batch_id: UUID,
    response: Response,
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> ImportBatch:
    batch = await _batch_or_404(session, context, batch_id)
    response.headers["ETag"] = f'"{batch.version}"'
    return batch


@router.post("/v1/import-batches/{batch_id}/validate", response_model=ImportBatchRead)
async def validate_batch(
    batch_id: UUID,
    payload: ImportBatchValidate,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    settings = get_settings()
    endpoint = f"POST:/v1/import-batches/{batch_id}/validate"
    request_hash, replay, _ = await idempotent_replay(
        session,
        context,
        endpoint=endpoint,
        key=idempotency_key,
        request_body=payload.model_dump(mode="json"),
    )
    if replay is not None:
        response.headers["ETag"] = f'"{replay["version"]}"'
        return replay
    batch = await _batch_or_404(session, context, batch_id)
    require_version(parse_etag(if_match, resource="Import batch"), batch.version, resource="Batch")
    await validate_import_batch(
        session,
        context,
        batch,
        set(payload.included_record_ids),
        payload.excluded_records,
    )
    body = ImportBatchRead.model_validate(batch).model_dump(mode="json")
    store_idempotency(
        session,
        context,
        settings,
        endpoint=endpoint,
        key=str(idempotency_key),
        request_hash=request_hash,
        status_code=200,
        response_body=body,
    )
    await session.commit()
    response.headers["ETag"] = f'"{batch.version}"'
    return batch


@router.post(
    "/v1/import-batches/{batch_id}/publish",
    response_model=PublicationAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def publish_batch(
    batch_id: UUID,
    payload: ImportBatchPublish,
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    settings = get_settings()
    require_recent_owner(context, settings)
    endpoint = f"POST:/v1/import-batches/{batch_id}/publish"
    request_hash, replay, _ = await idempotent_replay(
        session,
        context,
        endpoint=endpoint,
        key=idempotency_key,
        request_body=payload.model_dump(mode="json"),
    )
    if replay is not None:
        return replay
    batch = await _batch_or_404(session, context, batch_id)
    require_version(parse_etag(if_match, resource="Import batch"), batch.version, resource="Batch")
    if batch.state != "approved" or batch.validated_hash != payload.validated_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "BATCH_NOT_APPROVED", "message": "Validate this exact batch first."},
        )
    links = list(
        await session.scalars(
            select(ImportBatchRecord).where(
                ImportBatchRecord.import_batch_id == batch.id,
                ImportBatchRecord.tenant_id == context.tenant_id,
            )
        )
    )
    expected_included = {
        link.extracted_record_id for link in links if link.disposition == "included"
    }
    expected_excluded = {
        link.extracted_record_id for link in links if link.disposition == "excluded"
    }
    if (
        set(payload.included_record_ids) != expected_included
        or set(payload.excluded_records) != expected_excluded
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "BATCH_SELECTION_CHANGED", "message": "Validate this selection again."},
        )
    job = Job(
        id=uuid4(),
        tenant_id=context.tenant_id,
        job_type="immutable_ledger_publication",
        state="running",
        resource_type="import_batch",
        resource_id=batch.id,
        started_at=datetime.now(UTC),
    )
    session.add(job)
    try:
        ledger_version, audit_id = await publish_import_batch(session, context, batch, job)
        body = PublicationAccepted(
            job_id=job.id,
            import_batch_id=batch.id,
            ledger_version=ledger_version,
            state="completed",
            audit_event_id=audit_id,
        ).model_dump(mode="json")
        store_idempotency(
            session,
            context,
            settings,
            endpoint=endpoint,
            key=str(idempotency_key),
            request_hash=request_hash,
            status_code=status.HTTP_202_ACCEPTED,
            response_body=body,
        )
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "DUPLICATE_PUBLICATION",
                "message": "A source event or ledger version already exists.",
            },
        ) from error
    return body


@router.get("/v1/jobs/{job_id}", response_model=JobRead)
async def get_job(
    job_id: UUID,
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> Job:
    job = await session.scalar(
        select(Job).where(Job.id == job_id, Job.tenant_id == context.tenant_id)
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return job


@router.get(
    "/v1/portfolios/{portfolio_id}/ledger/versions/{version}",
    response_model=LedgerVersionRead,
)
async def get_ledger_version(
    portfolio_id: UUID,
    version: int,
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> LedgerVersion:
    item = await session.scalar(
        select(LedgerVersion).where(
            LedgerVersion.tenant_id == context.tenant_id,
            LedgerVersion.portfolio_id == portfolio_id,
            LedgerVersion.version == version,
        )
    )
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ledger version not found."
        )
    return item
