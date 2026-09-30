"""Foundation checks only: no real requests to models, tools, or databases."""
import json
import os
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from data_agent.api import app, create_app
from data_agent.api_models import AssistantResponse, Column, Page, TableRows
from data_agent.config import development_cors_origins


class ApiFoundationTests(unittest.TestCase):
    def test_startup_and_route_registration_do_not_invoke_services(self):
        runner, browser = Mock(), Mock()
        with patch.dict(os.environ, {"DATA_AGENT_CORS_ORIGINS": ""}), \
                patch("data_agent.api.load_environment") as load_environment:
            application = create_app(runner=runner, browser=browser)
            with TestClient(application) as client:
                response = client.get("/openapi.json")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(set(response.json()["paths"]), {
                    "/api/assistant", "/api/tables", "/api/tables/{table_id}/rows",
                    "/api/policy/documents", "/api/policy/documents/{document_id}",
                    "/api/policy/documents/{document_id}/status",
                    "/api/etl/files", "/api/etl/files/{file_id}",
                    "/api/etl/files/{file_id}/preview", "/api/etl/files/{file_id}/download",
                })
            load_environment.assert_called_once_with()
        runner.assert_not_called()
        self.assertEqual(browser.mock_calls, [])
        self.assertTrue(callable(app))

    def test_public_schema_serialization(self):
        answer = AssistantResponse(answer="Example", route="etl", status="answered")
        self.assertEqual(json.loads(answer.model_dump_json()), {
            "answer": "Example", "route": "etl", "status": "answered",
        })
        page = TableRows(table_id="public.users", columns=[Column(name="value", type="string")],
                         rows=[[None], ["1.20"]], page=Page(limit=50, offset=0, has_more=False))
        self.assertEqual(json.loads(page.model_dump_json())["rows"], [[None], ["1.20"]])

    def test_openapi_errors_match_runtime_validation(self):
        runner = Mock()
        with TestClient(create_app(runner=runner, browser=Mock())) as client:
            schema = client.get("/openapi.json").json()
            for path, method in (("/api/assistant", "post"), ("/api/tables/{table_id}/rows", "get")):
                responses = schema["paths"][path][method]["responses"]
                self.assertNotIn("422", responses)
                self.assertEqual(responses["400"]["content"]["application/json"]["schema"],
                                 {"$ref": "#/components/schemas/ErrorResponse"})
            invalid = client.post("/api/assistant", json={"question": ""})
            self.assertEqual(invalid.status_code, 400)
            self.assertEqual(set(invalid.json()), {"error", "route"})
        runner.assert_not_called()

    def test_cors_preflight_does_not_run_assistant(self):
        origin = "http://localhost:5173"
        runner = Mock()
        with patch.dict(os.environ, {"DATA_AGENT_CORS_ORIGINS": origin}):
            with TestClient(create_app(runner=runner, browser=Mock())) as client:
                response = client.options("/api/assistant", headers={
                    "Origin": origin, "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "Content-Type",
                })
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["access-control-allow-origin"], origin)
                self.assertNotIn("access-control-allow-credentials", response.headers)
                denied = client.options("/api/assistant", headers={
                    "Origin": "http://other.invalid", "Access-Control-Request-Method": "POST",
                })
                self.assertEqual(denied.status_code, 400)
                self.assertNotIn("access-control-allow-origin", denied.headers)
        runner.assert_not_called()

    def test_cors_on_validation_and_unexpected_errors(self):
        origin = "http://localhost:5173"
        with patch.dict(os.environ, {"DATA_AGENT_CORS_ORIGINS": origin}):
            runner = Mock(side_effect=RuntimeError("private details"))
            with TestClient(create_app(runner=runner, browser=Mock())) as client:
                for body, expected_status in [({}, 400), ({"question": "test"}, 500)]:
                    response = client.post("/api/assistant", json=body, headers={"Origin": origin})
                    self.assertEqual(response.status_code, expected_status)
                    self.assertEqual(response.headers["access-control-allow-origin"], origin)
                    self.assertNotIn("private details", response.text)

    def test_cors_defaults_and_explicit_configuration(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(development_cors_origins(), [])
        with patch.dict(os.environ, {"DATA_AGENT_CORS_ORIGINS": " http://localhost:5173, http://127.0.0.1:5173 "}):
            self.assertEqual(development_cors_origins(), ["http://localhost:5173", "http://127.0.0.1:5173"])
        with patch.dict(os.environ, {"DATA_AGENT_CORS_ORIGINS": "*"}):
            with self.assertRaises(ValueError):
                development_cors_origins()
