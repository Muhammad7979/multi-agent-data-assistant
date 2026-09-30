"""Assistant HTTP contract through the existing invocation and real graph wiring."""
import unittest
from unittest.mock import Mock, patch

import anthropic
import httpx
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage

from data_agent.api import create_app
from data_agent.agents.etl import build_etl_graph
from data_agent.agents.router import build_data_agent
from data_agent.agents.sql import build_sql_graph


class AssistantApiTests(unittest.TestCase):
    def test_invalid_inputs_do_not_invoke_agent(self):
        runner = Mock()
        with TestClient(create_app(runner=runner, browser=Mock())) as client:
            for body in ({}, None, [], {"question": ""}, {"question": " \t\n"},
                         {"question": None}, {"question": True}, {"question": []},
                         {"question": "x" * 5001}, {"question": "test", "messages": []}):
                with self.subTest(body=str(body)[:70]):
                    response = client.post("/api/assistant", json=body)
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(set(response.json()), {"error", "route"})
            malformed = client.post("/api/assistant", content='{broken', headers={"Content-Type": "application/json"})
            self.assertEqual(malformed.status_code, 400)
        runner.assert_not_called()

    def test_maximum_length_and_unicode_serialization(self):
        runner = Mock(return_value={"route_response": "sql", "messages": [{
            "is_safe": "Yes", "sql_query_execution_result": "[]", "final_answer": "No rows \u2014 \u2713",
            "prompt_query_context": "PRIVATE", "comments": "PRIVATE", "generated_sql_query": "PRIVATE",
        }]})
        with TestClient(create_app(runner=runner, browser=Mock())) as client:
            response = client.post("/api/assistant", json={"question": "x" * 5000})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"answer": "No rows \u2014 \u2713", "route": "sql", "status": "answered"})
        self.assertNotIn("PRIVATE", response.text)
        runner.assert_called_once_with("x" * 5000)

    def test_unusable_results_are_errors_not_answers(self):
        incomplete = AIMessage(content="Unusable", invalid_tool_calls=[{
            "name": "extract_load_tool", "args": "{", "id": "call1", "error": "invalid JSON",
        }])
        results = [None, {}, {"route_response": "sql", "messages": []},
                   {"route_response": "etl", "messages": [{"messages": [HumanMessage(content="test")]}]},
                   {"route_response": "etl", "messages": [{"messages": [incomplete]}]}]
        results.extend({"route_response": "sql", "messages": [{
            "is_safe": "Yes", "final_answer": "Apparently done", "sql_query_execution_result": value,
        }]} for value in (None, "", " \n"))
        for result in results:
            with self.subTest(result=repr(result)[:70]), TestClient(create_app(runner=lambda _: result, browser=Mock())) as client:
                response = client.post("/api/assistant", json={"question": "test"})
                self.assertEqual(response.status_code, 500)
                self.assertEqual(response.json()["error"]["code"], "INTERNAL_ERROR")
                self.assertNotIn("answer", response.json())

    def test_provider_rejection_is_sanitized(self):
        error = anthropic.BadRequestError(
            "PRIVATE account details", response=httpx.Response(400, request=httpx.Request("POST", "https://example.invalid")),
            body={"message": "PRIVATE"},
        )
        with TestClient(create_app(runner=Mock(side_effect=error), browser=Mock())) as client:
            response = client.post("/api/assistant", json={"question": "test"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "UPSTREAM_UNAVAILABLE")
        self.assertNotIn("PRIVATE", response.text)

    def test_http_to_existing_invocation_and_sql_graph(self):
        for safe in ("Yes", "No"):
            with self.subTest(safe=safe):
                model = Mock()
                model.invoke.return_value = AIMessage(content="Two users")
                model.with_structured_output.return_value.invoke.return_value.model_dump.return_value = {
                    "answer": safe, "comments": "Judge decision",
                }
                database = Mock()
                database.schema_detail.return_value = "users(user_id integer)"
                database.execute_sql.return_value = "[(2,)]"
                child = build_sql_graph(llm_factory=lambda _: model, database_factory=lambda _: database,
                                        database_settings=lambda: {})
                router = Mock()
                router.with_structured_output.return_value.invoke.return_value.model_dump.return_value = {
                    "answer": "sql", "comments": "PRIVATE routing explanation",
                }
                graph = build_data_agent(llm_factory=lambda _: router, sql_graph=child, etl_graph=Mock())
                # Keep create_app's default run_request; replace only graph construction/dependencies.
                with patch("data_agent.main.build_data_agent", return_value=graph) as builder:
                    with TestClient(create_app(browser=Mock())) as client:
                        response = client.post("/api/assistant", json={"question": "How many users?"})
                    builder.assert_called_once_with()
                self.assertEqual(response.status_code, 200)
                self.assertEqual(set(response.json()), {"answer", "route", "status"})
                self.assertEqual(response.json()["status"], "answered" if safe == "Yes" else "declined")
                self.assertEqual(response.json()["route"], "sql")
                self.assertNotIn("PRIVATE", response.text)
                if safe == "Yes":
                    database.execute_sql.assert_called_once()
                else:
                    database.execute_sql.assert_not_called()

    def test_http_to_existing_invocation_and_etl_graph(self):
        model = Mock()
        model.bind_tools.return_value.invoke.return_value = AIMessage(content=[
            {"type": "thinking", "thinking": "PRIVATE"},
            {"type": "text", "text": "Please provide an API URL."},
        ])
        child = build_etl_graph(data_root=".", llm_factory=lambda _: model)
        router = Mock()
        router.with_structured_output.return_value.invoke.return_value.model_dump.return_value = {
            "answer": "etl", "comments": "PRIVATE",
        }
        graph = build_data_agent(llm_factory=lambda _: router, sql_graph=Mock(), etl_graph=child)
        with patch("data_agent.main.build_data_agent", return_value=graph):
            with TestClient(create_app(browser=Mock())) as client:
                response = client.post("/api/assistant", json={"question": "Extract data"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"answer": "Please provide an API URL.", "route": "etl", "status": "answered"})
