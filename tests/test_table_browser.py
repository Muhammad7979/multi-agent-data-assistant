from datetime import datetime, date
from decimal import Decimal
import unittest
from unittest.mock import MagicMock

from data_agent.services.table_browser import TableBrowser, TableNotFound, json_cell


class TableBrowserTests(unittest.TestCase):
    def browser(self, batches):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.side_effect = batches
        connect = MagicMock(return_value=connection)
        return TableBrowser(connect=connect, settings=lambda: {}), connection, cursor, connect

    def test_catalog_filters_at_database_boundary_and_closes_connection(self):
        browser, connection, cursor, _ = self.browser([[('users',)]])
        self.assertEqual(browser.list_tables().model_dump(), {"tables": [{"id": "public.users", "label": "Users"}]})
        parameters = cursor.execute.call_args.args[1]
        self.assertEqual(parameters[0], "public")
        self.assertEqual(set(parameters[1]), {"users", "vehicles", "rides", "payments", "ratings"})
        connection.set_session.assert_called_once_with(readonly=True)
        connection.close.assert_called_once()

    def test_pagination_and_safe_identifiers(self):
        browser, connection, cursor, _ = self.browser([
            [("user_id", "integer"), ("amount", "numeric")],
            [(1, Decimal('10.20')), (2, Decimal('5.00')), (3, Decimal('1.00'))],
        ])
        response = browser.rows("public.users", 2, 4)
        self.assertEqual(response.rows, [[1, "10.20"], [2, "5.00"]])
        self.assertTrue(response.page.has_more)
        query, parameters = cursor.execute.call_args.args
        self.assertEqual(parameters, (3, 4))
        self.assertIn("Identifier('public', 'users')", repr(query))
        self.assertIn("Identifier('user_id')", repr(query))
        connection.close.assert_called_once()

    def test_rejects_unapproved_identifier_before_connection(self):
        browser, _, _, connect = self.browser([])
        for identifier in ("users", "private.users", "public.secrets", 'public.users; DROP TABLE users'):
            with self.subTest(identifier=identifier), self.assertRaises(TableNotFound):
                browser.rows(identifier, 50, 0)
        connect.assert_not_called()

    def test_empty_table_preserves_columns(self):
        browser, _, _, _ = self.browser([[("user_id", "integer")], []])
        result = browser.rows("public.users", 50, 0)
        self.assertEqual(result.rows, [])
        self.assertEqual(result.columns[0].name, "user_id")
        self.assertFalse(result.page.has_more)

    def test_missing_table_and_failures_close_connection(self):
        browser, connection, _, _ = self.browser([[]])
        with self.assertRaises(TableNotFound):
            browser.rows("public.users", 50, 0)
        connection.close.assert_called_once()
        browser, connection, cursor, _ = self.browser([])
        cursor.execute.side_effect = RuntimeError("database failure")
        with self.assertRaises(RuntimeError):
            browser.list_tables()
        connection.close.assert_called_once()

    def test_json_precision_nulls_and_dates(self):
        values = [None, True, 2**60, Decimal("1.2300"), date(2026, 1, 2), datetime(2026, 1, 2, 3, 4), float('inf')]
        self.assertEqual([json_cell(value) for value in values],
                         [None, True, str(2**60), "1.2300", "2026-01-02", "2026-01-02T03:04:00", "inf"])
