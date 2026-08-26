# Supplied-source ingestion quality report

Audit date: 2026-08-26  
Scope: `Qber-Aug2026.xls`, one brokerage contract note PDF, one watchlist report PDF, and ten market-page PDFs supplied for the owner pilot.

No raw source document or personal identifier is reproduced in this report.

## Decision

The workbook is suitable for a reviewed portfolio import after deterministic normalization. It is not suitable for direct row-by-row insertion: instrument names are abbreviated, tax lots repeat an instrument across acquisition dates, quantities may contain thousands separators, and allocation values are stored in separator rows rather than lot rows.

The PDFs are not authoritative holdings sources. The contract note may become a transaction source after private parsing and owner confirmation. The watchlist and market-page PDFs are research/evidence candidates only. Until private object storage is enabled, the application registers only PDF metadata and a browser-computed SHA-256; it does not upload raw PDF bytes to D1.

## Workbook profile

| Check | Result | Disposition |
|---|---:|---|
| Sheets | `stocks` plus one empty sheet | Empty sheet skipped |
| Data rows | 109 | Classified before normalization |
| Tax-lot rows | 89 | Preserved in `portfolio_lots` and the append-only transaction ledger |
| Unique instruments | 18 | Aggregated into reviewed holdings |
| Allocation-only rows | 17 | Sixteen group rows plus one allocation summary |
| Total rows | 1 | Used for reconciliation, not inserted as a holding |
| Blank rows | 2 | Skipped |
| Invalid/unclassified rows | 0 | Pass |
| Exact duplicate lots | 0 | Pass |
| Duplicate identity/date/quantity/cost lots | 0 | Pass |
| Total quantity | 40,941 | Lot sum matches source TOTAL |
| Total latest value | ₹17,557,571 | Lot sum matches source TOTAL |
| Total gain | ₹4,003,562 | Lot sum matches source TOTAL |
| Investment total | Source TOTAL ₹13,554,006; rounded lot sum ₹13,554,009 | Warning: ₹3 source-rounding variance; values are not silently changed |
| Allocation total | 99.9437% | Warning: 0.0563 percentage-point shortfall; importer does not force 100% |
| Row arithmetic | Maximum absolute lot investment/value variance ₹0.50 | Pass within ₹1 source-rounding tolerance |

All 18 instruments have an explicit exchange-aware analysis mapping. NSE holdings use confirmed `.NS` identifiers. The two BSE holdings use numeric BSE/Yahoo identifiers ending in `.BO`; the importer does not fabricate a text ticker for BSE. Unknown aliases or exchange conflicts block normalization.

## PDF profile

| Source class | Count / shape | Data role | V1 handling |
|---|---|---|---|
| Brokerage contract note | One six-page PDF with extractable tabular text | Candidate transaction evidence | Metadata-only registration; raw document is treated as sensitive because it contains personal/account information |
| Watchlist report | One 32-page A4 report | Research context and dated watchlist telemetry | Metadata-only registration pending source review |
| Market-page captures | Ten single-page, very tall PDFs with extractable text | Secondary research/quote evidence | Metadata-only registration; not allowed to create or change holdings |

PDF text is untrusted input. It cannot set portfolio policy, change a symbol mapping, update quantity/cost, or trigger a trade. Parsed content must be associated with a file hash, owner, portfolio, symbol, publisher, publication/retrieval timestamps, and review status before it can support an agent claim.

## Implemented ingestion controls

1. `pi-normalize-portfolio` reads the legacy XLS `stocks` sheet and emits `pi-portfolio-import/v1` JSON.
2. Every input row is classified; unknown layouts, invalid numerics, inconsistent lot arithmetic, duplicate lots, missing totals, and unmapped instruments fail closed.
3. The normalized file preserves acquisition lots and separately aggregates holdings using quantity-weighted unit cost.
4. The Sites onboarding screen parses canonical CSV or normalized JSON in the browser, presents editable rows, and commits only after owner confirmation.
5. D1 stores a source-hashed `import_batch`, normalized `import_rows`, `portfolio_lots`, portfolio prices, instrument mappings, and append-only transactions. Raw workbook bytes are not retained.
6. PDF intake computes SHA-256 in the browser and stores metadata with `metadata_only` status. Such documents do not increase verified evidence coverage.
7. The migration deletes only `is_demo = 1` portfolios and their dependent rows, plus known fictional reference prices/evidence. Non-demo portfolios are preserved.

## Remaining gate before broader deployment

- Add owner-scoped private object storage before retaining raw PDFs or workbooks.
- Add a server-side upload scanner, file-type verification, parser sandbox, and retention/deletion policy.
- Add conflict resolution for multiple workbook versions and a preview diff before replacing an existing snapshot.
- Validate broker contract-note parsing against order/trade annexures and fees; require explicit confirmation before ledger insertion.
- Persist LangGraph run state in Postgres and queue events through Redis before multi-user use.
