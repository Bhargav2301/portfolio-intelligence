from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from portfolio_api.config import get_settings
from portfolio_api.database import apply_tenant_scope, get_tenant_session
from portfolio_api.models import AuditEvent, Portfolio, Upload
from portfolio_api.schemas import SourceRole, UploadRead
from portfolio_api.services.file_security import (
    MalwareDetected,
    MalwareScannerUnavailable,
    scan_with_clamav,
)
from portfolio_api.services.ingestion import UnsafeFileError, validate_and_summarize
from portfolio_api.services.storage import build_quarantine_storage
from portfolio_api.tenant import RequestContext, request_context


router = APIRouter(prefix="/v1/uploads", tags=["uploads"])


@router.post("", response_model=UploadRead, status_code=status.HTTP_201_CREATED)
async def upload_file(
    portfolio_id: UUID = Form(...),
    source_role: SourceRole = Form(...),
    file: UploadFile = File(...),
    context: RequestContext = Depends(request_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> Upload:
    settings = get_settings()
    portfolio = await session.scalar(
        select(Portfolio).where(
            Portfolio.id == portfolio_id,
            Portfolio.tenant_id == context.tenant_id,
        )
    )
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found.")

    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "code": "FILE_TOO_LARGE",
                "message": f"File exceeds {settings.max_upload_bytes} bytes.",
            },
        )
    if settings.malware_scan_required:
        try:
            await run_in_threadpool(
                scan_with_clamav,
                content,
                settings.clamav_host,
                settings.clamav_port,
            )
        except MalwareDetected as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
            detail={
                "code": "DUPLICATE_UPLOAD",
                "message": "This file was already accepted for the same portfolio and source role.",
            },
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
        AuditEvent(
            tenant_id=context.tenant_id,
            actor_id=context.user_id,
            action="upload.accepted",
            resource_type="upload",
            resource_id=upload.id,
            details={
                "portfolio_id": str(portfolio_id),
                "source_role": source_role,
                "detected_type": summary.detected_type,
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
            detail={
                "code": "DUPLICATE_UPLOAD",
                "message": "This file was already accepted for the same portfolio and source role.",
            },
        ) from error
    except Exception:
        await session.rollback()
        await run_in_threadpool(storage.delete, object_key)
        raise
    await apply_tenant_scope(session, context.tenant_id)
    await session.refresh(upload)
    return upload


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
