from __future__ import annotations

import json
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from portfolio_api.config import Settings
from portfolio_api.observability import install_request_telemetry


class TelemetryRedactionTests(unittest.TestCase):
    def test_request_logs_use_route_template_and_never_capture_payloads(self) -> None:
        app = FastAPI()
        settings = Settings(app_env="development", service_name="telemetry-test")
        install_request_telemetry(app, settings)

        @app.post("/v1/private/{resource_id}")
        async def private(resource_id: str, payload: dict) -> dict:
            return {"resource_id": resource_id, **payload}

        seeded_value = "seeded-sensitive-value-that-must-never-appear"
        with self.assertLogs("telemetry-test", level="INFO") as captured:
            response = TestClient(app).post(
                f"/v1/private/{seeded_value}",
                json={"document": seeded_value, "holding": "1000", "prompt": seeded_value},
                headers={"X-Request-Id": seeded_value},
            )
        self.assertEqual(response.status_code, 200)
        serialized = "\n".join(captured.output)
        self.assertNotIn(seeded_value, serialized)
        self.assertNotIn("holding", serialized)
        event = json.loads(captured.records[0].message)
        self.assertEqual(event["route"], "/v1/private/{resource_id}")
        self.assertRegex(event["request_id"], r"^[0-9a-f-]{36}$")
        self.assertEqual(
            set(event),
            {
                "duration_ms",
                "environment",
                "event",
                "method",
                "request_id",
                "route",
                "service",
                "status_code",
                "trace_id",
            },
        )
