import unittest
from unittest.mock import Mock

import httpx
import openai
import psycopg2
from fastapi.testclient import TestClient

from data_agent.api import create_app
from data_agent.services.table_browser import TableNotFound


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.runner = Mock(return_value={"route_response": "sql", "messages": [{
            "is_safe": "Yes", "final_answer": "Two users", "sql_query_execution_result": "[(2,)]",
        }]})
        self.browser = Mock()
        self.browser.list_tables.return_value = {"tables": []}
        self.browser.rows.return_value = {
            "table_id": "public.users", "columns": [], "rows": [],
            "page": {"limit": 50, "offset": 0, "has_more": False},
        }
        self.client = TestClient(create_app(runner=self.runner, browser=self.browser), raise_server_exceptions=False)
        self.addCleanup(self.client.close)

    def test_assistant_contract(self):
        response = self.client.post('/api/assistant', json={"question": "How many?"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"answer": "Two users", "route": "sql", "status": "answered"})
        self.runner.assert_called_once_with("How many?")

    def test_invalid_questions_never_invoke_graph(self):
        for body in ({}, {"question": " "}, {"question": 123}, {"question": "x" * 5001},
                     {"question": "x", "route": "sql"}):
            with self.subTest(body=str(body)[:60]):
                response = self.client.post('/api/assistant', json=body)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()['error']['code'], "INVALID_REQUEST")
        self.runner.assert_not_called()

    def test_table_defaults_and_unknown_parameters(self):
        self.assertEqual(self.client.get('/api/tables').json(), {"tables": []})
        self.assertEqual(self.client.get('/api/tables?schema=private').status_code, 400)
        self.assertEqual(self.client.get('/api/tables/public.users/rows').status_code, 200)
        self.browser.rows.assert_called_once_with("public.users", 50, 0)
        for query in ('limit=101', 'offset=-1', 'limit=abc', 'sort=name', 'limit=2&limit=3'):
            self.assertEqual(self.client.get('/api/tables/public.users/rows?' + query).status_code, 400)
        self.assertEqual(self.browser.rows.call_count, 1)

    def test_errors_are_sanitized(self):
        cases = [
            (psycopg2.OperationalError('secret host password'), 503, "UPSTREAM_UNAVAILABLE"),
            (TimeoutError('private'), 504, "REQUEST_TIMEOUT"),
            (RuntimeError('private traceback'), 500, "INTERNAL_ERROR"),
            (openai.APIConnectionError(request=httpx.Request('POST', 'https://example.invalid')), 503, "UPSTREAM_UNAVAILABLE"),
        ]
        for error, status, code in cases:
            with self.subTest(error=type(error).__name__):
                self.runner.side_effect = error
                response = self.client.post('/api/assistant', json={"question": "test"})
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json()['error']['code'], code)
                self.assertNotIn('private', response.text)
                self.assertNotIn('password', response.text)

    def test_missing_table(self):
        self.browser.rows.side_effect = TableNotFound()
        response = self.client.get('/api/tables/public.nope/rows')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['error']['code'], "TABLE_NOT_FOUND")
