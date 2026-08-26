from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4


class CoreApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(cls.temporary_directory.name) / "api-test.db"
        os.environ["APP_ENV"] = "development"
        os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{database_path}"
        os.environ["STORAGE_BACKEND"] = "local"
        os.environ["STORAGE_DIRECTORY"] = str(
            Path(cls.temporary_directory.name) / "uploads"
        )
        os.environ["MALWARE_SCAN_REQUIRED"] = "false"

        from fastapi.testclient import TestClient
        from portfolio_api.main import app

        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)
        cls.temporary_directory.cleanup()

    def create_portfolio(self) -> dict:
        response = self.client.post(
            "/v1/portfolios",
            json={
                "name": "Test " + uuid4().hex,
                "portfolio_type": "self_managed",
                "base_currency": "INR",
                "benchmark_code": "NIFTY_500_TRI",
                "valuation_timezone": "Asia/Kolkata",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_portfolio_is_tenant_scoped(self) -> None:
        portfolio = self.create_portfolio()
        own_response = self.client.get(f"/v1/portfolios/{portfolio['id']}")
        self.assertEqual(own_response.status_code, 200)

        other_response = self.client.get(
            f"/v1/portfolios/{portfolio['id']}",
            headers={"X-Workspace-Id": "00000000-0000-0000-0000-000000000099"},
        )
        self.assertEqual(other_response.status_code, 404)

    def test_csv_upload_is_quarantined_and_duplicate_is_rejected(self) -> None:
        portfolio = self.create_portfolio()
        content = b"date,symbol,quantity\n2026-08-26,TEST.NS,4\n"
        fields = {
            "portfolio_id": portfolio["id"],
            "source_role": "brokerage_ledger",
        }
        first = self.client.post(
            "/v1/uploads",
            data=fields,
            files={"file": ("transactions.csv", content, "text/csv")},
        )
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(first.json()["state"], "review_required")
        self.assertEqual(first.json()["authority_level"], "ledger_candidate")

        duplicate = self.client.post(
            "/v1/uploads",
            data=fields,
            files={"file": ("transactions.csv", content, "text/csv")},
        )
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.json()["detail"]["code"], "DUPLICATE_UPLOAD")

    def test_goal_cagr_is_deterministic(self) -> None:
        response = self.client.get(
            "/v1/goals/required-cagr",
            params={"wealth_multiple": "2", "years": "10"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["required_cagr_percent"], "7.177346253629316421300632500")


if __name__ == "__main__":
    unittest.main()
