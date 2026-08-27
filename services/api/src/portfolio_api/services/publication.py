from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from portfolio_api.models import (
    Account,
    CashEvent,
    Document,
    ExtractedRecord,
    ExtractionRun,
    ImportBatch,
    ImportBatchRecord,
    Instrument,
    Job,
    LedgerVersion,
    OutboxEvent,
    Portfolio,
    ReconciliationCase,
    Transaction,
    Upload,
)
from portfolio_api.services.control_plane import audit_event, canonical_hash
from portfolio_api.services.ledger import LedgerInvariantError, calculate_ledger
from portfolio_api.services.reconciliation import (
    PARSER_NAME,
    PARSER_VERSION,
    TEMPLATE_ID,
    CertifiedCsvResult,
)
from portfolio_api.tenant import RequestContext


async def persist_extraction(
    session: AsyncSession,
    context: RequestContext,
    upload: Upload,
    parsed: CertifiedCsvResult,
) -> tuple[Document, ExtractionRun, ImportBatch]:
    document = Document(
        id=uuid4(),
        tenant_id=context.tenant_id,
        portfolio_id=upload.portfolio_id,
        upload_id=upload.id,
        document_family="generic_ledger_csv",
        state="review_required",
        source_hash=parsed.content_hash,
    )
    extraction = ExtractionRun(
        id=uuid4(),
        tenant_id=context.tenant_id,
        document_id=document.id,
        parser_name=PARSER_NAME,
        parser_version=PARSER_VERSION,
        template_id=TEMPLATE_ID,
        state="completed",
        completed_at=datetime.now(UTC),
        metrics_json={
            "source_rows": len(parsed.records)
            + len({issue.source_row for issue in parsed.issues if issue.source_row > 1}),
            "candidate_records": len(parsed.records),
            "issues": len(parsed.issues),
            "headers": list(parsed.headers),
        },
    )
    session.add_all([document, extraction])
    await session.flush()

    portfolio = await session.scalar(
        select(Portfolio).where(
            Portfolio.id == upload.portfolio_id,
            Portfolio.tenant_id == context.tenant_id,
        )
    )
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found.")
    batch = ImportBatch(
        id=uuid4(),
        tenant_id=context.tenant_id,
        portfolio_id=upload.portfolio_id,
        document_id=document.id,
        extraction_run_id=extraction.id,
        state="draft",
        base_ledger_version=portfolio.ledger_version,
        content_hash=parsed.content_hash,
        created_by=context.user_id,
    )
    session.add(batch)
    await session.flush()

    record_by_row: dict[int, ExtractedRecord] = {}
    for candidate in parsed.records:
        record = ExtractedRecord(
            tenant_id=context.tenant_id,
            extraction_run_id=extraction.id,
            source_row=candidate.source_row,
            raw_hash=candidate.raw_hash,
            normalized_data=candidate.data,
            confidence=Decimal("1"),
            state="candidate",
        )
        session.add(record)
        await session.flush()
        record_by_row[candidate.source_row] = record
        session.add(
            ImportBatchRecord(
                tenant_id=context.tenant_id,
                import_batch_id=batch.id,
                extracted_record_id=record.id,
                disposition="pending",
            )
        )

    existing_sources = set(
        await session.scalars(
            select(Transaction.source_reference).where(
                Transaction.tenant_id == context.tenant_id,
                Transaction.portfolio_id == upload.portfolio_id,
                Transaction.source_reference.in_(
                    [str(record.data["source_reference"]) for record in parsed.records]
                ),
            )
        )
    )
    for candidate in parsed.records:
        if str(candidate.data["source_reference"]) in existing_sources:
            session.add(
                ReconciliationCase(
                    tenant_id=context.tenant_id,
                    portfolio_id=upload.portfolio_id,
                    import_batch_id=batch.id,
                    extracted_record_id=record_by_row[candidate.source_row].id,
                    kind="duplicate_source_reference",
                    severity="error",
                    details={
                        "source_row": candidate.source_row,
                        "source_reference_hash": canonical_hash(
                            str(candidate.data["source_reference"])
                        ),
                    },
                )
            )
    for issue in parsed.issues:
        session.add(
            ReconciliationCase(
                tenant_id=context.tenant_id,
                portfolio_id=upload.portfolio_id,
                import_batch_id=batch.id,
                extracted_record_id=(
                    record_by_row[issue.source_row].id
                    if issue.source_row in record_by_row
                    else None
                ),
                kind=issue.kind,
                severity="error",
                details={
                    "source_row": issue.source_row,
                    "field": issue.field,
                    "message": issue.message,
                },
            )
        )
    upload.state = "review_required"
    upload.version += 1
    upload.parser_summary = {
        **dict(upload.parser_summary),
        "document_id": str(document.id),
        "extraction_run_id": str(extraction.id),
        "import_batch_id": str(batch.id),
        "candidate_records": len(parsed.records),
        "reconciliation_cases": len(parsed.issues) + len(existing_sources),
    }
    session.add(
        audit_event(
            context,
            action="extraction.completed",
            resource_type="extraction_run",
            resource_id=extraction.id,
            details={
                "upload_id": str(upload.id),
                "candidate_records": len(parsed.records),
                "issues": len(parsed.issues) + len(existing_sources),
                "template_id": TEMPLATE_ID,
            },
        )
    )
    return document, extraction, batch


async def batch_records(
    session: AsyncSession, context: RequestContext, batch_id: UUID
) -> list[tuple[ImportBatchRecord, ExtractedRecord]]:
    rows = await session.execute(
        select(ImportBatchRecord, ExtractedRecord)
        .join(ExtractedRecord, ExtractedRecord.id == ImportBatchRecord.extracted_record_id)
        .where(
            ImportBatchRecord.tenant_id == context.tenant_id,
            ImportBatchRecord.import_batch_id == batch_id,
            ExtractedRecord.tenant_id == context.tenant_id,
        )
        .order_by(ExtractedRecord.source_row)
    )
    return list(rows.tuples())


async def validate_import_batch(
    session: AsyncSession,
    context: RequestContext,
    batch: ImportBatch,
    included_ids: set[UUID],
    excluded: dict[UUID, str],
) -> str:
    rows = await batch_records(session, context, batch.id)
    all_ids = {record.id for _, record in rows}
    excluded_ids = set(excluded)
    if included_ids & excluded_ids or included_ids | excluded_ids != all_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "RECORD_COVERAGE_INCOMPLETE",
                "message": "Every extracted record must be included or excluded exactly once.",
            },
        )
    open_cases = list(
        await session.scalars(
            select(ReconciliationCase).where(
                ReconciliationCase.tenant_id == context.tenant_id,
                ReconciliationCase.import_batch_id == batch.id,
                ReconciliationCase.state == "open",
            )
        )
    )
    batch_record_ids = all_ids
    blockers = [
        case
        for case in open_cases
        if case.extracted_record_id is None or case.extracted_record_id in batch_record_ids
    ]
    if blockers:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "RECONCILIATION_REQUIRED",
                "message": "Resolve every reconciliation case before validation.",
                "case_ids": [str(item.id) for item in blockers],
            },
        )
    if not included_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "EMPTY_PUBLICATION", "message": "Include at least one valid record."},
        )
    canonical_records = []
    for link, record in rows:
        if record.id in included_ids:
            link.disposition = "included"
            link.exclusion_reason = None
            record.state = "accepted"
            canonical_records.append(record.normalized_data)
        else:
            reason = excluded[record.id].strip()
            if len(reason) < 4:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail={
                        "code": "EXCLUSION_REASON_REQUIRED",
                        "message": "Every excluded record needs a meaningful reason.",
                    },
                )
            link.disposition = "excluded"
            link.exclusion_reason = reason[:255]
            record.state = "excluded"
    validated_hash = canonical_hash(canonical_records)
    batch.validated_hash = validated_hash
    batch.state = "approved"
    batch.version += 1
    batch.approved_by = context.user_id
    batch.validation_summary = {
        "included": len(included_ids),
        "excluded": len(excluded_ids),
        "errors": 0,
        "record_coverage_percent": "100.00",
    }
    session.add(
        audit_event(
            context,
            action="import_batch.validated",
            resource_type="import_batch",
            resource_id=batch.id,
            details={
                "included": len(included_ids),
                "excluded": len(excluded_ids),
                "validated_hash": validated_hash,
            },
        )
    )
    return validated_hash


async def _account_for(
    session: AsyncSession,
    context: RequestContext,
    portfolio_id: UUID,
    account_reference: str,
    currency: str,
) -> Account:
    masked = "*" * max(0, len(account_reference) - 4) + account_reference[-4:]
    account = await session.scalar(
        select(Account).where(
            Account.tenant_id == context.tenant_id,
            Account.portfolio_id == portfolio_id,
            Account.provider == "generic_csv",
            Account.masked_reference == masked,
        )
    )
    if account is None:
        account = Account(
            tenant_id=context.tenant_id,
            portfolio_id=portfolio_id,
            provider="generic_csv",
            account_type="brokerage",
            masked_reference=masked,
            currency=currency,
        )
        session.add(account)
        await session.flush()
    return account


async def _instrument_for(session: AsyncSession, data: dict[str, object]) -> Instrument | None:
    identifier = data.get("instrument_id")
    if not identifier:
        return None
    identifier_type = str(data["instrument_id_type"])
    instrument = await session.scalar(
        select(Instrument).where(
            Instrument.identifier_type == identifier_type,
            Instrument.identifier == str(identifier),
        )
    )
    if instrument is None:
        instrument = Instrument(
            identifier_type=identifier_type,
            identifier=str(identifier),
            exchange=str(data["exchange"]),
            symbol=str(data["symbol"]),
            asset_type="equity",
            currency=str(data["currency"]),
        )
        session.add(instrument)
        await session.flush()
    elif instrument.exchange != data["exchange"] or instrument.symbol != data["symbol"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "AMBIGUOUS_INSTRUMENT",
                "message": "The instrument identifier conflicts with its exchange or symbol.",
            },
        )
    return instrument


def _instrument_reference(data: dict[str, object]) -> str | None:
    if not data.get("symbol"):
        return None
    suffix = ".NS" if data.get("exchange") == "NSE" else ".BO"
    return f"{data['symbol']}{suffix}"


async def publish_import_batch(
    session: AsyncSession,
    context: RequestContext,
    batch: ImportBatch,
    job: Job,
) -> tuple[int, UUID]:
    portfolio = await session.scalar(
        select(Portfolio)
        .where(
            Portfolio.id == batch.portfolio_id,
            Portfolio.tenant_id == context.tenant_id,
        )
        .with_for_update()
    )
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found.")
    if batch.base_ledger_version != portfolio.ledger_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "LEDGER_VERSION_CHANGED",
                "message": "The ledger changed after this batch was created; validate it again.",
            },
        )
    rows = await batch_records(session, context, batch.id)
    included = [record for link, record in rows if link.disposition == "included"]
    if not included:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "EMPTY_PUBLICATION", "message": "No records are approved."},
        )
    new_version = portfolio.ledger_version + 1
    events: list[Transaction] = []
    cash_events: list[CashEvent] = []
    for record in included:
        data = dict(record.normalized_data)
        account = await _account_for(
            session,
            context,
            portfolio.id,
            str(data["account_reference"]),
            str(data["currency"]),
        )
        instrument = await _instrument_for(session, data)
        cash_delta = Decimal(str(data["cash_delta"]))
        event_type = (
            "dividend" if data["event_type"] == "dividend_cash" else str(data["event_type"])
        )
        event = Transaction(
            tenant_id=context.tenant_id,
            portfolio_id=portfolio.id,
            account_id=account.id,
            instrument_id=instrument.id if instrument else None,
            import_batch_id=batch.id,
            ledger_version=new_version,
            event_type=event_type,
            trade_date=datetime.fromisoformat(str(data["trade_at"])),
            instrument_reference=_instrument_reference(data),
            quantity=Decimal(str(data["quantity"])) if data.get("quantity") else None,
            price=Decimal(str(data["price"])) if data.get("price") else None,
            gross_amount=abs(cash_delta),
            cash_delta=cash_delta,
            fees=Decimal(str(data["fees"])),
            taxes=Decimal(str(data["taxes"])),
            currency=str(data["currency"]),
            source_reference=str(data["source_reference"]),
        )
        events.append(event)
    existing_events = list(
        await session.scalars(
            select(Transaction).where(
                Transaction.tenant_id == context.tenant_id,
                Transaction.portfolio_id == portfolio.id,
            )
        )
    )
    protected = Decimal(str((portfolio.rules.get("protected_cash") or {}).get("amount", "0")))
    try:
        calculate_ledger([*existing_events, *events], protected, reject_negative_cash=True)
    except LedgerInvariantError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "LEDGER_INVARIANT_VIOLATION", "message": str(error)},
        ) from error

    session.add_all(events)
    await session.flush()
    for event in events:
        if event.cash_delta and event.cash_delta != 0:
            cash_events.append(
                CashEvent(
                    tenant_id=context.tenant_id,
                    portfolio_id=portfolio.id,
                    transaction_id=event.id,
                    import_batch_id=batch.id,
                    event_at=event.trade_date,
                    amount=event.cash_delta,
                    currency=event.currency,
                    event_type=event.event_type,
                    ledger_version=new_version,
                )
            )
    session.add_all(cash_events)
    ledger_version = LedgerVersion(
        tenant_id=context.tenant_id,
        portfolio_id=portfolio.id,
        version=new_version,
        import_batch_id=batch.id,
        event_count=len(events),
        content_hash=str(batch.validated_hash),
        published_by=context.user_id,
    )
    session.add(ledger_version)
    portfolio.ledger_version = new_version
    portfolio.version += 1
    batch.state = "published"
    batch.published_ledger_version = new_version
    batch.published_at = datetime.now(UTC)
    batch.version += 1
    job.state = "completed"
    job.attempts += 1
    job.started_at = job.started_at or datetime.now(UTC)
    job.completed_at = datetime.now(UTC)
    job.result = {
        "import_batch_id": str(batch.id),
        "ledger_version": new_version,
        "published_events": len(events),
    }
    publication_audit = audit_event(
        context,
        action="import_batch.published",
        resource_type="import_batch",
        resource_id=batch.id,
        details={
            "ledger_version": new_version,
            "published_events": len(events),
            "validated_hash": batch.validated_hash,
            "human_confirmed": True,
        },
    )
    session.add(publication_audit)
    session.add(
        OutboxEvent(
            tenant_id=context.tenant_id,
            event_type="ledger.version.published",
            aggregate_type="portfolio",
            aggregate_id=portfolio.id,
            aggregate_version=new_version,
            trace_id=publication_audit.trace_id,
            payload={
                "portfolio_id": str(portfolio.id),
                "ledger_version": new_version,
                "import_batch_id": str(batch.id),
            },
        )
    )
    await session.flush()
    return new_version, publication_audit.id
