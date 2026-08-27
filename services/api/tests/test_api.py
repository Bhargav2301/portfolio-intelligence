from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
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
        os.environ["STORAGE_DIRECTORY"] = str(Path(cls.temporary_directory.name) / "uploads")
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

    def publish_event(self, portfolio_id: str, **overrides: object):
        payload: dict[str, object] = {
            "event_type": "cash_deposit",
            "trade_date": "2026-08-26T09:15:00+05:30",
            "gross_amount": "4000000.00",
            "currency": "INR",
            "source_reference": "test-" + uuid4().hex,
            "confirm_publication": True,
        }
        payload.update(overrides)
        return self.client.post(
            f"/v1/portfolios/{portfolio_id}/ledger/events",
            json=payload,
        )

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

    def test_published_ledger_drives_holdings_analytics_and_monitors(self) -> None:
        portfolio = self.create_portfolio()
        deposit = self.publish_event(portfolio["id"])
        self.assertEqual(deposit.status_code, 201, deposit.text)
        buy = self.publish_event(
            portfolio["id"],
            event_type="buy",
            instrument_reference="RELIANCE.NS",
            quantity="1000",
            price="1500",
            gross_amount="1500000",
        )
        self.assertEqual(buy.status_code, 201, buy.text)

        holdings = self.client.get(f"/v1/portfolios/{portfolio['id']}/holdings")
        self.assertEqual(holdings.status_code, 200, holdings.text)
        body = holdings.json()
        self.assertEqual(body["ledger_version"], 2)
        self.assertEqual(body["cash_balance"], "2500000.00000000")
        self.assertEqual(body["available_cash"], "0.00000000")
        self.assertEqual(body["total_value"], "4000000.00000000")
        self.assertEqual(body["holdings"][0]["weight_percent"], "37.50")

        analytics = self.client.get(f"/v1/portfolios/{portfolio['id']}/analytics/latest")
        self.assertEqual(analytics.json()["quality_state"], "trusted")
        self.assertEqual(analytics.json()["metrics"]["current_value"], "4000000.00000000")

        monitors = self.client.get(f"/v1/portfolios/{portfolio['id']}/monitors/latest")
        self.assertEqual(monitors.status_code, 200, monitors.text)
        self.assertEqual(monitors.json()["state"], "attention")
        self.assertEqual(monitors.json()["alerts"][0]["kind"], "concentration")

        context = self.client.get(f"/v1/portfolios/{portfolio['id']}/agent-context")
        self.assertEqual(context.status_code, 200, context.text)
        self.assertEqual(context.json()["ledger"]["ledger_version"], 2)
        self.assertEqual(
            [item["id"] for item in context.json()["evidence"]],
            ["ledger:snapshot", "monitor:snapshot", "rule:portfolio"],
        )

    def test_ledger_requires_confirmation_and_rejects_oversell(self) -> None:
        portfolio = self.create_portfolio()
        unconfirmed = self.publish_event(portfolio["id"], confirm_publication=False)
        self.assertEqual(unconfirmed.status_code, 422)

        deposit = self.publish_event(portfolio["id"], gross_amount="3000000")
        self.assertEqual(deposit.status_code, 201, deposit.text)
        buy = self.publish_event(
            portfolio["id"],
            event_type="buy",
            instrument_reference="TCS.NS",
            quantity="10",
            price="1000",
            gross_amount="10000",
        )
        self.assertEqual(buy.status_code, 201, buy.text)
        oversell = self.publish_event(
            portfolio["id"],
            event_type="sell",
            instrument_reference="TCS.NS",
            quantity="11",
            price="1100",
            gross_amount="12100",
        )
        self.assertEqual(oversell.status_code, 422)
        self.assertEqual(oversell.json()["detail"]["code"], "LEDGER_INVARIANT_VIOLATION")

    def test_ledger_and_agent_context_are_tenant_scoped(self) -> None:
        portfolio = self.create_portfolio()
        other_headers = {"X-Workspace-Id": "00000000-0000-0000-0000-000000000099"}
        for suffix in ("holdings", "monitors/latest", "agent-context"):
            response = self.client.get(
                f"/v1/portfolios/{portfolio['id']}/{suffix}", headers=other_headers
            )
            self.assertEqual(response.status_code, 404)

    def test_certified_csv_reconciliation_and_atomic_publication(self) -> None:
        portfolio = self.create_portfolio()
        columns = (
            "schema_version,source_reference,event_type,trade_at,account_reference,"
            "currency,cash_delta,instrument_id_type,instrument_id,exchange,symbol,"
            "quantity,price,settlement_date,fees,taxes,lot_reference,description\n"
        )
        content = (
            columns + "spi-ledger-csv/v1,cash-1,cash_deposit,2026-08-25T09:15:00+05:30,"
            "ACC1234,INR,4000000,,,,,,,,0,0,,Opening cash\n"
            + "spi-ledger-csv/v1,buy-1,buy,2026-08-26T09:15:00+05:30,"
            "ACC1234,INR,-1500000,ISIN,INE002A01018,NSE,RELIANCE,1000,1500,,0,0,,Buy\n"
        ).encode()
        digest = hashlib.sha256(content).hexdigest()
        initiated = self.client.post(
            "/v1/uploads",
            json={
                "portfolio_id": portfolio["id"],
                "original_name": "spi-ledger.csv",
                "source_role": "brokerage_ledger",
                "content_type": "text/csv",
                "size_bytes": len(content),
                "sha256": digest,
            },
        )
        self.assertEqual(initiated.status_code, 201, initiated.text)
        upload_id = initiated.json()["upload_id"]
        uploaded = self.client.put(
            initiated.json()["upload_url"],
            content=content,
            headers={"Content-Type": "text/csv"},
        )
        self.assertEqual(uploaded.status_code, 204, uploaded.text)

        completed = self.client.post(
            f"/v1/uploads/{upload_id}/complete",
            headers={"Idempotency-Key": "complete-" + upload_id},
        )
        self.assertEqual(completed.status_code, 202, completed.text)
        completion = completed.json()
        self.assertEqual(completion["state"], "completed")

        records_response = self.client.get(
            f"/v1/extractions/{completion['extraction_run_id']}/records"
        )
        self.assertEqual(records_response.status_code, 200, records_response.text)
        record_ids = [record["id"] for record in records_response.json()]
        self.assertEqual(len(record_ids), 2)

        batch_id = completion["import_batch_id"]
        batch = self.client.get(f"/v1/import-batches/{batch_id}")
        self.assertEqual(batch.headers["etag"], '"1"')
        validated = self.client.post(
            f"/v1/import-batches/{batch_id}/validate",
            headers={"If-Match": '"1"', "Idempotency-Key": "validate-" + batch_id},
            json={"included_record_ids": record_ids, "excluded_records": {}},
        )
        self.assertEqual(validated.status_code, 200, validated.text)
        self.assertEqual(validated.json()["state"], "approved")
        self.assertEqual(validated.headers["etag"], '"2"')

        published = self.client.post(
            f"/v1/import-batches/{batch_id}/publish",
            headers={"If-Match": '"2"', "Idempotency-Key": "publish-" + batch_id},
            json={
                "included_record_ids": record_ids,
                "excluded_records": {},
                "validated_hash": validated.json()["validated_hash"],
                "acknowledgment": (
                    "I reviewed this batch and authorize immutable ledger publication."
                ),
            },
        )
        self.assertEqual(published.status_code, 202, published.text)
        self.assertEqual(published.json()["ledger_version"], 1)

        holdings = self.client.get(f"/v1/portfolios/{portfolio['id']}/holdings")
        self.assertEqual(holdings.status_code, 200, holdings.text)
        self.assertEqual(holdings.json()["ledger_version"], 1)
        self.assertEqual(holdings.json()["cash_balance"], "2500000.00000000")
        self.assertEqual(holdings.json()["holdings"][0]["instrument_reference"], "RELIANCE.NS")

        replay = self.client.post(
            f"/v1/import-batches/{batch_id}/publish",
            headers={"If-Match": '"2"', "Idempotency-Key": "publish-" + batch_id},
            json={
                "included_record_ids": record_ids,
                "excluded_records": {},
                "validated_hash": validated.json()["validated_hash"],
                "acknowledgment": (
                    "I reviewed this batch and authorize immutable ledger publication."
                ),
            },
        )
        self.assertEqual(replay.status_code, 202, replay.text)
        self.assertEqual(replay.json(), published.json())

    def test_certified_csv_parser_requires_resolution_for_unknown_columns(self) -> None:
        portfolio = self.create_portfolio()
        content = (
            b"schema_version,source_reference,event_type,trade_at,account_reference,currency,"
            b"cash_delta,instrument_id_type,instrument_id,exchange,symbol,quantity,price,"
            b"mystery_column\n"
            b"spi-ledger-csv/v1,cash-x,cash_deposit,2026-08-25T09:15:00+05:30,"
            b"ACC9,INR,1000,,,,,,,must-review\n"
        )
        initiated = self.client.post(
            "/v1/uploads",
            json={
                "portfolio_id": portfolio["id"],
                "original_name": "unknown-column.csv",
                "source_role": "brokerage_ledger",
                "content_type": "text/csv",
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            },
        )
        upload_id = initiated.json()["upload_id"]
        self.client.put(initiated.json()["upload_url"], content=content)
        completed = self.client.post(
            f"/v1/uploads/{upload_id}/complete",
            headers={"Idempotency-Key": "complete-unknown-" + upload_id},
        )
        batch_id = completed.json()["import_batch_id"]
        records = self.client.get(
            f"/v1/extractions/{completed.json()['extraction_run_id']}/records"
        ).json()
        blocked = self.client.post(
            f"/v1/import-batches/{batch_id}/validate",
            headers={"If-Match": '"1"', "Idempotency-Key": "blocked-" + batch_id},
            json={"included_record_ids": [records[0]["id"]], "excluded_records": {}},
        )
        self.assertEqual(blocked.status_code, 422)
        self.assertEqual(blocked.json()["detail"]["code"], "RECONCILIATION_REQUIRED")

    def test_r2_snapshot_scenario_and_r3_evidence_run_are_durable(self) -> None:
        portfolio = self.create_portfolio()
        self.assertEqual(self.publish_event(portfolio["id"]).status_code, 201)
        self.assertEqual(
            self.publish_event(
                portfolio["id"],
                event_type="buy",
                instrument_reference="RELIANCE.NS",
                quantity="1000",
                price="1500",
                gross_amount="1500000",
            ).status_code,
            201,
        )
        as_of = datetime.now(UTC) + timedelta(seconds=1)
        known_at = as_of + timedelta(seconds=1)
        dataset = self.client.post(
            f"/v1/portfolios/{portfolio['id']}/market-data/datasets",
            headers={"Idempotency-Key": "dataset-" + portfolio["id"]},
            json={
                "provider": "licensed-test-feed",
                "provider_version": "2026-08-27T12:00Z",
                "rights_basis": "licensed",
                "cutoff_at": as_of.isoformat(),
                "known_at": known_at.isoformat(),
                "prices": [
                    {
                        "instrument_reference": "RELIANCE.NS",
                        "observed_at": as_of.isoformat(),
                        "known_at": known_at.isoformat(),
                        "close_price": "1500",
                        "currency": "INR",
                        "quality": "verified",
                        "source_hash": "a" * 64,
                    }
                ],
                "corporate_actions": [],
            },
        )
        self.assertEqual(dataset.status_code, 201, dataset.text)

        recomputed = self.client.post(
            f"/v1/portfolios/{portfolio['id']}/analytics/recompute",
            headers={"Idempotency-Key": "analytics-" + portfolio["id"]},
            json={
                "market_data_set_id": dataset.json()["id"],
                "as_of": as_of.isoformat(),
                "known_at": known_at.isoformat(),
                "max_price_age_days": 7,
            },
        )
        self.assertEqual(recomputed.status_code, 201, recomputed.text)
        snapshot = recomputed.json()
        self.assertEqual(snapshot["quality_state"], "trusted")
        self.assertEqual(snapshot["metrics"]["current_value"], "4000000.00000000")
        self.assertEqual(snapshot["market_data_version"], "2026-08-27T12:00Z")

        method_variant = self.client.post(
            f"/v1/portfolios/{portfolio['id']}/analytics/recompute",
            headers={"Idempotency-Key": "analytics-variant-" + portfolio["id"]},
            json={
                "market_data_set_id": dataset.json()["id"],
                "as_of": as_of.isoformat(),
                "known_at": known_at.isoformat(),
                "max_price_age_days": 6,
            },
        )
        self.assertEqual(method_variant.status_code, 201, method_variant.text)
        self.assertNotEqual(
            method_variant.json()["snapshot_id"],
            snapshot["snapshot_id"],
            "result-affecting method parameters must create a distinct immutable snapshot",
        )

        latest = self.client.get(f"/v1/portfolios/{portfolio['id']}/analytics/latest")
        self.assertEqual(latest.status_code, 200, latest.text)
        self.assertEqual(latest.json()["snapshot_id"], method_variant.json()["snapshot_id"])

        historical_context = self.client.get(
            f"/v1/portfolios/{portfolio['id']}/agent-context",
            params={"as_of": as_of.isoformat()},
        )
        self.assertEqual(historical_context.status_code, 200, historical_context.text)
        self.assertNotIn(
            "analytics_snapshot",
            {item["source_type"] for item in historical_context.json()["evidence"]},
        )

        scenario = self.client.post(
            f"/v1/portfolios/{portfolio['id']}/scenarios",
            headers={"Idempotency-Key": "scenario-" + portfolio["id"]},
            json={
                "base_snapshot_id": snapshot["snapshot_id"],
                "name": "Equity drawdown",
                "price_shocks": {"RELIANCE.NS": "-0.10"},
                "allocations": {},
            },
        )
        self.assertEqual(scenario.status_code, 201, scenario.text)
        self.assertFalse(scenario.json()["can_execute"])
        self.assertEqual(scenario.json()["results"]["stressed_total"], "3850000.00000000")

        blocked = self.client.post(
            f"/v1/portfolios/{portfolio['id']}/scenarios",
            headers={"Idempotency-Key": "scenario-blocked-" + portfolio["id"]},
            json={
                "base_snapshot_id": snapshot["snapshot_id"],
                "name": "Attempt to use reserve",
                "price_shocks": {},
                "allocations": {"RELIANCE.NS": "1"},
            },
        )
        self.assertEqual(blocked.status_code, 201, blocked.text)
        self.assertEqual(blocked.json()["status"], "blocked")
        self.assertIn(
            "PROTECTED_CASH_BREACH",
            {item["code"] for item in blocked.json()["constraint_results"]},
        )

        run_cutoff = known_at + timedelta(seconds=1)
        context = self.client.get(
            f"/v1/portfolios/{portfolio['id']}/agent-context",
            params={"as_of": run_cutoff.isoformat()},
        )
        self.assertEqual(context.status_code, 200, context.text)
        analytics_evidence = next(
            item
            for item in context.json()["evidence"]
            if item["source_type"] == "analytics_snapshot"
        )
        current_value_claim = next(
            claim for claim in analytics_evidence["claims"] if claim["claim_key"] == "current_value"
        )

        run_id = str(uuid4())
        thread_id = str(uuid4())
        started = self.client.post(
            f"/v1/portfolios/{portfolio['id']}/agent-runs",
            json={
                "run_id": run_id,
                "thread_id": thread_id,
                "request_id": "request-" + run_id,
                "question_hash": "b" * 64,
                "as_of": run_cutoff.isoformat(),
                "known_at": run_cutoff.isoformat(),
                "graph_version": "test-graph/1",
                "prompt_bundle_version": "test-prompt/1",
                "model_route": "deterministic-safe",
                "policy_version": "test-policy/1",
                "allowed_tools": ["core.analytics.read", "core.evidence.read"],
                "checkpoint_thread_id": "c" * 64,
            },
        )
        self.assertEqual(started.status_code, 200, started.text)
        invalid = self.client.post(
            f"/v1/agent-runs/{run_id}/complete",
            json={
                "state": "completed",
                "stages": ["response_composed"],
                "citations": [],
                "policy": {"decision": "allow_analysis"},
                "proposal": {
                    "type": "review",
                    "status": "proposal_only",
                    "title": "Review",
                    "can_execute": True,
                },
                "numeric_citation_coverage": "1",
                "answer_hash": "d" * 64,
            },
        )
        self.assertEqual(invalid.status_code, 422)

        fabricated = self.client.post(
            f"/v1/agent-runs/{run_id}/complete",
            json={
                "state": "completed",
                "stages": ["output_validated"],
                "citations": [
                    {
                        "claim_key": "fabricated_value",
                        "evidence_id": "ledger:snapshot",
                        "value": "999",
                        "unit": "INR",
                        "as_of": run_cutoff.isoformat(),
                        "locator": f"/v1/portfolios/{portfolio['id']}/holdings",
                    }
                ],
                "policy": {"decision": "allow_analysis"},
                "proposal": {
                    "type": "review",
                    "status": "proposal_only",
                    "title": "Review",
                    "can_execute": False,
                },
                "numeric_citation_coverage": "1",
                "answer": "Fabricated value is INR 999 [ledger:snapshot].",
                "answer_hash": hashlib.sha256(
                    b"Fabricated value is INR 999 [ledger:snapshot]."
                ).hexdigest(),
            },
        )
        self.assertEqual(fabricated.status_code, 422, fabricated.text)

        answer = (
            f"Portfolio value is INR {current_value_claim['numeric_value']} "
            f"[{analytics_evidence['id']}]."
        )
        completed = self.client.post(
            f"/v1/agent-runs/{run_id}/complete",
            json={
                "state": "completed",
                "intent": "portfolio_review",
                "stages": ["context_assembled", "output_validated"],
                "citations": [
                    {
                        "claim_key": "current_value",
                        "evidence_id": analytics_evidence["id"],
                        "value": current_value_claim["numeric_value"],
                        "unit": current_value_claim["unit"],
                        "as_of": analytics_evidence["as_of"],
                        "locator": analytics_evidence["uri"],
                    }
                ],
                "policy": {"decision": "allow_analysis"},
                "proposal": {
                    "type": "review",
                    "status": "proposal_only",
                    "title": "Review evidence",
                    "can_execute": False,
                },
                "numeric_citation_coverage": "1",
                "answer": answer,
                "answer_hash": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
            },
        )
        self.assertEqual(completed.status_code, 200, completed.text)
        self.assertEqual(completed.json()["state"], "completed")
        self.assertFalse(completed.json()["can_execute"])

        other_tenant = self.client.get(
            f"/v1/agent-runs/{run_id}",
            headers={"X-Workspace-Id": "00000000-0000-0000-0000-000000000099"},
        )
        self.assertEqual(other_tenant.status_code, 404)


if __name__ == "__main__":
    unittest.main()
