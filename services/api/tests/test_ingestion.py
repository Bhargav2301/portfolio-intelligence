from __future__ import annotations

import io
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from portfolio_api.services.ingestion import UnsafeFileError, validate_and_summarize
from portfolio_api.services.reconciliation import parse_certified_csv


class IngestionTests(unittest.TestCase):
    def test_certified_csv_formula_marker_becomes_publication_blocker(self) -> None:
        content = (
            b"schema_version,source_reference,event_type,trade_at,account_reference,currency,"
            b"cash_delta,instrument_id_type,instrument_id,exchange,symbol,quantity,price,"
            b"settlement_date,fees,taxes,lot_reference,description\n"
            b"spi-ledger-csv/v1,formula-1,cash_deposit,2026-08-26T09:15:00+05:30,"
            b"ACC-1,INR,1000,,,,,,,2026-08-27T09:15:00+05:30,0,0,,-cmd|test\n"
        )
        parsed = parse_certified_csv(content)
        self.assertEqual(parsed.records, ())
        self.assertEqual(parsed.issues[0].kind, "record_validation")
        self.assertIn("formula marker", parsed.issues[0].message)

    def test_csv_summary_and_authority(self) -> None:
        summary = validate_and_summarize(
            "ledger.csv",
            b"date,symbol,quantity\n2026-08-26,TEST.NS,4\n",
            "brokerage_ledger",
        )
        self.assertEqual(summary.detected_type, "text/csv")
        self.assertEqual(summary.authority_level, "ledger_candidate")
        self.assertEqual(summary.structure["rows"], 2)

    def test_extension_signature_mismatch(self) -> None:
        with self.assertRaises(UnsafeFileError) as raised:
            validate_and_summarize("fake.pdf", b"not a pdf", "research")
        self.assertEqual(raised.exception.code, "SIGNATURE_MISMATCH")

    def test_pdf_active_content_is_rejected(self) -> None:
        with self.assertRaises(UnsafeFileError) as raised:
            validate_and_summarize(
                "unsafe.pdf",
                b"%PDF-1.7\n/JavaScript malicious",
                "research",
            )
        self.assertEqual(raised.exception.code, "PDF_ACTIVE_CONTENT")

    def test_macro_enabled_xlsx_container_is_rejected(self) -> None:
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types />")
            archive.writestr("xl/vbaProject.bin", b"macro")
        with self.assertRaises(UnsafeFileError) as raised:
            validate_and_summarize("unsafe.xlsx", stream.getvalue(), "brokerage_ledger")
        self.assertEqual(raised.exception.code, "WORKBOOK_MACRO")

    def test_unsupported_xlsm_is_rejected(self) -> None:
        with self.assertRaises(UnsafeFileError) as raised:
            validate_and_summarize("unsafe.xlsm", b"data", "brokerage_ledger")
        self.assertEqual(raised.exception.code, "FILE_TYPE_UNSUPPORTED")


if __name__ == "__main__":
    unittest.main()
