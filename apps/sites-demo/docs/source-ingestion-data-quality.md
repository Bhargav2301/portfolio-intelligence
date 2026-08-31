# Public-source ingestion quality contract

Audit baseline: 2026-08-31  
Scope: synthetic spreadsheet fixtures and metadata-only PDF intake.

This public repository intentionally contains no owner portfolio, brokerage
document, source filename, account identifier, position size, cost basis, or
private-source aggregate. Real-source audits remain private and are connected to
an import only by an owner-scoped SHA-256 reference.

## Acceptance decision

Spreadsheet imports are accepted only after deterministic normalization and an
owner review. Source rows are never inserted directly as holdings: metadata and
summary rows are classified, repeated acquisition lots are preserved, and
holdings are aggregated only after required identities and numeric values pass
validation.

PDFs are evidence sources, not holdings sources. The public demo records only
metadata and a browser-computed SHA-256. PDF text cannot change a holding,
portfolio policy, symbol mapping, or transaction.

## Spreadsheet quality matrix

| Check | Required behavior | Failure policy |
|---|---|---|
| Workbook structure | Inspect every non-empty sheet and detect the most plausible tabular region | Reject when no usable table is found |
| Header mapping | Normalize header text and map aliases to canonical fields independent of column order | Request owner mapping when a required field is ambiguous |
| Row classification | Separate lots, holdings, totals, allocations, metadata, and blank rows | Reject unclassified material rows |
| Instrument identity | Preserve the source name and use an explicit owner-approved exchange ticker when supplied | Derive a review symbol but leave the analysis ticker unset |
| Numeric parsing | Accept common separators, currency marks, percentages, and parenthesized negatives | Reject non-empty values that cannot be parsed safely |
| Lot arithmetic | Reconcile quantity, unit cost, investment, latest price, and latest value within a declared rounding tolerance | Surface a blocking error outside tolerance |
| Duplicate detection | Compare source identity, acquisition date, quantity, and unit cost | Reject exact or ledger-equivalent duplicate lots |
| Totals | Compare calculated totals with source totals when the source provides them | Report the variance; never silently force agreement |
| Allocation | Retain source allocation separately from calculated allocation | Warn when the source allocation does not reconcile |
| Provenance | Bind normalized output to source filename metadata and SHA-256 | Reject a missing or invalid source hash |

The fixtures use invented names, symbols, quantities, and prices. They exercise
the same canonical `pi-portfolio-import/v1` contract without publishing a real
portfolio.

## Consolidated workbook handling

The normalizer accepts a consolidated export when the workbook contains repeated
tax lots, separator rows, allocation summaries, and a source total. It selects a
named holdings sheet when present and otherwise inspects the first usable sheet.
Instrument mappings may be supplied at runtime; no customer-specific alias table
is compiled into the public code.

When a ticker cannot be confirmed, the normalizer keeps the source instrument
name, derives a stable review symbol, sets `analysis_symbol` to `null`, and marks
the result `validated_with_warnings`. That output may be previewed, but it must
not be used for market-data or agent analysis until the owner confirms the
exchange ticker.

## PDF quality matrix

| Source class | Data role | Public-demo handling |
|---|---|---|
| Brokerage statement or contract note | Candidate transaction evidence | Metadata and hash only; no automatic ledger mutation |
| Watchlist or research report | Dated research context | Metadata and hash only until reviewed |
| Market-page capture | Secondary quote or research evidence | Cannot create or change holdings |

Extracted PDF text is untrusted input. Before it can support an agent claim, the
private deployment must associate it with an owner, portfolio, file hash,
publisher, relevant symbol, retrieval or publication timestamp, and review
status.

## Implemented controls

1. `pi-normalize-portfolio` emits versioned canonical JSON from a consolidated
   Excel workbook and preserves acquisition lots.
2. Canonical CSV and normalized JSON are parsed in the browser and presented for
   owner confirmation before persistence.
3. Import batches, normalized rows, lots, prices, instrument mappings, and
   append-only transactions retain source provenance.
4. PDF intake computes SHA-256 in the browser and registers metadata only.
5. Unknown identities, invalid numerics, duplicate lots, inconsistent arithmetic,
   and missing required fields fail closed or require explicit review.
6. Demo reset logic targets only records explicitly marked as demo data.

## Remaining production gates

- Add owner-scoped private object storage, malware scanning, file-type
  verification, parser isolation, and retention/deletion controls before storing
  raw uploads.
- Add a mapping-review UI and persist owner-approved aliases outside the codebase.
- Add workbook-version conflict resolution and a preview diff before replacing a
  prior snapshot.
- Validate broker-specific transaction parsers against fees and trade annexures;
  require owner confirmation before ledger insertion.
- Persist agent run state and queue work before multi-user scaling.
