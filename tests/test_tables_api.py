"""HTTP to real table service, with fake DB-API connections and no database IO."""
from datetime import date, datetime, timezone
from decimal import Decimal
import unittest
from unittest.mock import MagicMock, Mock
from urllib.parse import quote

import psycopg2
from fastapi.testclient import TestClient

from data_agent.api import create_app
from data_agent.services.table_browser import TableBrowser


class TablesApiTests(unittest.TestCase):
    def setUp(self):
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        self.connect = Mock(return_value=self.connection)
        self.runner = Mock(side_effect=AssertionError("Browsing must never invoke an agent"))
        browser = TableBrowser(connect=self.connect, settings=lambda: {})
        self.client = TestClient(create_app(runner=self.runner, browser=browser))
        self.addCleanup(self.client.close)

    def tearDown(self):
        self.runner.assert_not_called()

    def test_catalog_and_empty_catalog(self):
        for records in ([('users',), ('vehicles',)], []):
            with self.subTest(records=records):
                self.cursor.fetchall.return_value = records
                response = self.client.get('/api/tables')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"tables": [
                    {"id": f"public.{name}", "label": name.title()} for (name,) in records
                ]})
                query, parameters = self.cursor.execute.call_args.args
                self.assertIn("table_type = 'BASE TABLE'", query)
                self.assertEqual(parameters[0], "public")
                self.assertEqual(set(parameters[1]), {'users', 'vehicles', 'rides', 'payments', 'ratings'})

    def test_page_is_bounded_ordered_and_read_only(self):
        self.cursor.fetchall.side_effect = [[('user_id', 'integer')], [(5,), (6,), (7,)]]
        response = self.client.get('/api/tables/public.users/rows?limit=2&offset=4')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'table_id': 'public.users', 'columns': [{'name': 'user_id', 'type': 'integer'}],
            'rows': [[5], [6]], 'page': {'limit': 2, 'offset': 4, 'has_more': True},
        })
        metadata_query, metadata_parameters = self.cursor.execute.call_args_list[0].args
        self.assertIn("t.table_type = 'BASE TABLE'", metadata_query)
        self.assertEqual(metadata_parameters, ('public', 'users'))
        query, parameters = self.cursor.execute.call_args.args
        self.assertIn("Identifier('public', 'users')", repr(query))
        self.assertIn('ORDER BY', repr(query))
        self.assertEqual(parameters, (3, 4))
        self.connection.set_session.assert_called_once_with(readonly=True)
        self.connection.close.assert_called_once()
        self.connection.cursor.return_value.__exit__.assert_called_once()

    def test_invalid_table_and_injection_do_not_connect(self):
        for identifier in ('users', 'private.users', 'public.secrets',
                           'public.users; DROP TABLE public.users;--', 'public.users" OR "1"="1'):
            with self.subTest(identifier=identifier):
                response = self.client.get(f'/api/tables/{quote(identifier, safe="")}/rows')
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json()['error']['code'], 'TABLE_NOT_FOUND')
        self.connect.assert_not_called()

    def test_missing_approved_table_is_not_an_empty_table(self):
        self.cursor.fetchall.return_value = []
        response = self.client.get('/api/tables/public.users/rows')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.cursor.execute.call_count, 1)
        self.connection.close.assert_called_once()

    def test_empty_page_keeps_schema_and_defaults(self):
        self.cursor.fetchall.side_effect = [[('user_id', 'integer')], []]
        response = self.client.get('/api/tables/public.users/rows')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['columns'], [{'name': 'user_id', 'type': 'integer'}])
        self.assertEqual(body['rows'], [])
        self.assertEqual(body['page'], {'limit': 50, 'offset': 0, 'has_more': False})

    def test_invalid_pagination_never_connects(self):
        for query in ('limit=0', 'limit=101', 'limit=-1', 'offset=-1', 'offset=abc',
                      'limit=1.5', 'page=2', 'sort=name', 'limit=2&limit=3', 'offset=0&offset=1'):
            with self.subTest(query=query):
                response = self.client.get('/api/tables/public.users/rows?' + query)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()['error']['code'], 'INVALID_REQUEST')
        self.connect.assert_not_called()

    def test_database_values_are_frontend_safe(self):
        self.cursor.fetchall.side_effect = [[
            ('id', 'bigint'), ('amount', 'numeric'), ('day', 'date'), ('at', 'timestamp with time zone'),
            ('active', 'boolean'), ('optional', 'text'), ('details', 'jsonb'),
        ], [(2**60, Decimal('12.3400'), date(2026, 1, 2), datetime(2026, 1, 2, tzinfo=timezone.utc),
             True, None, {'label': 'example'})]]
        response = self.client.get('/api/tables/public.users/rows')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['rows'], [[str(2**60), '12.3400', '2026-01-02',
                                                  '2026-01-02T00:00:00+00:00', True, None,
                                                  '{"label": "example"}']])
        self.assertEqual([c['type'] for c in response.json()['columns']],
                         ['integer', 'number', 'date', 'datetime', 'boolean', 'string', 'json'])

    def test_database_errors_are_sanitized(self):
        self.cursor.execute.side_effect = psycopg2.OperationalError('PRIVATE credentials')
        for path in ('/api/tables', '/api/tables/public.users/rows'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()['error']['code'], 'UPSTREAM_UNAVAILABLE')
                self.assertNotIn('PRIVATE', response.text)
        self.assertEqual(self.connection.close.call_count, 2)
