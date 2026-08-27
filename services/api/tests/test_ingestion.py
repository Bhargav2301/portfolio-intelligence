from __future__ import annotations

import io
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from portfolio_api.config import Settings
from portfolio_api.services.demo_evidence import extract_research_rows, extract_research_text
from portfolio_api.services.ingestion import UnsafeFileError, validate_and_summarize
from portfolio_api.services.reconciliation import parse_certified_csv
from portfolio_api.services.storage import s3_server_side_encryption


class IngestionTests(unittest.TestCase):
    def test_economic_times_pdf_text_becomes_typed_market_evidence(self) -> None:
        extracted = extract_research_text(
            "Yatharth Hospital Share Price Today.pdf",
            """
            Yatharth Hospital Share Price Insights
            Yatharth Hospital Share Price Returns
            1 Day 1.66%
            1 Week 8.03%
            1 Month 9.99%
            3 Months 12.44%
            Stock Score 8 POSITIVE Outlook
            Yatharth Hospital share price is Rs 926.15 as on 25 Aug, 2026.
            Last Updated On: 25 Aug, 2026, 10:46 AM IST
            The Economic Times ETPrime
            """,
        )
        self.assertIsNotNone(extracted)
        assert extracted is not None
        claims = {item["claim_key"]: item for item in extracted.claims}
        self.assertEqual(
            claims["instrument.YATHARTH_HOSPITAL.latest_price"]["numeric_value"],
            "926.15",
        )
        self.assertEqual(
            claims["instrument.YATHARTH_HOSPITAL.stock_score"]["numeric_value"],
            "8",
        )
        self.assertIn(
            "positive outlook", claims["instrument.YATHARTH_HOSPITAL.outlook"]["statement"]
        )

    def test_watchlist_pdf_rows_are_bounded_and_instrument_scoped(self) -> None:
        extracted = extract_research_text(
            "watchlist.pdf",
            """
            Your Watchlist Summary August 24, 2026
            Watchlist Gainers - 24 Aug
            Yatharth Hospital 907.55 ↑6.13% ↑52.40 ↑7.68% ↑8.20% ↑5.27% ↑28.90%
            Watchlist Losers - 24 Aug
            AXISCADES Engg Tech 1,557 ↓-2.55% ↓-40.60 ↑0.23% ↓-3.18% ↓-21.94% ↑5.58%
            """,
        )
        self.assertIsNotNone(extracted)
        assert extracted is not None
        self.assertEqual(extracted.instruments, ("Yatharth Hospital", "AXISCADES Engg Tech"))
        self.assertEqual(len(extracted.claims), 12)

    def test_holdings_workbook_rows_are_aggregated_before_agent_use(self) -> None:
        extracted = extract_research_rows(
            "portfolio.xls",
            [
                [
                    "Stock",
                    "Latest Price",
                    "Quantity",
                    "Inv. Price",
                    "Inv. Amt",
                    "Overall Gain",
                    "Overall Gain%",
                    "Latest Value",
                ],
                ["Adani Ports - NSE", 1682, 27, 1797, 48519, -3105, -6.4, 45414],
                ["Adani Ports - NSE", 1682, 30, 1633, 48990, 1470, 3, 50460],
            ],
        )
        self.assertIsNotNone(extracted)
        assert extracted is not None
        claims = {item["claim_key"]: item for item in extracted.claims}
        self.assertEqual(claims["instrument.ADANI_PORTS.quantity"]["numeric_value"], "57")
        self.assertEqual(
            claims["instrument.ADANI_PORTS.latest_value"]["numeric_value"],
            "95874",
        )

    def test_contract_note_pdf_text_extracts_trade_evidence_without_publishing_ledger(self) -> None:
        extracted = extract_research_text(
            "contract-note.pdf",
            """
            TRADE DATE CONTRACT NOTE NO. 24-SEP-2025 NM25183/0046869
            As per Annexure YATHARTH HOSPITAL & TRAUMA CAR-
            INE0JO301016
            Buy 63 790.00 1.98 791.98 49,894.74
            CONTRACT NOTE CUM TAX INVOICE
            """,
        )
        self.assertIsNotNone(extracted)
        assert extracted is not None
        self.assertEqual(extracted.parser_name, "spi-julius-baer-contract-note-pdf")
        self.assertEqual(len(extracted.claims), 6)
        self.assertEqual(
            extracted.claims[1]["claim_key"],
            "instrument.YATHARTH_HOSPITAL_TRAUMA_CAR.quantity",
        )

    def test_s3_encryption_is_backend_aware_and_production_still_uses_kms(self) -> None:
        local_minio = Settings(
            _env_file=None,
            object_storage_endpoint="http://minio:9000",
            object_storage_kms_key_id=None,
        )
        aws_development = Settings(
            _env_file=None,
            object_storage_endpoint=None,
            object_storage_kms_key_id=None,
        )
        production_shape = Settings(
            _env_file=None,
            object_storage_endpoint=None,
            object_storage_kms_key_id="arn:aws:kms:ap-south-1:123456789012:key/test",
        )
        self.assertEqual(s3_server_side_encryption(local_minio), {})
        self.assertEqual(
            s3_server_side_encryption(aws_development),
            {"ServerSideEncryption": "AES256"},
        )
        self.assertEqual(
            s3_server_side_encryption(production_shape),
            {
                "ServerSideEncryption": "aws:kms",
                "SSEKMSKeyId": "arn:aws:kms:ap-south-1:123456789012:key/test",
            },
        )

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
