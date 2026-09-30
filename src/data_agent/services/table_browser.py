"""Bounded reads of the five approved development tables; no LLM involved."""
from contextlib import closing
from datetime import date, datetime
from decimal import Decimal
import json
import math

import psycopg2
from psycopg2 import sql

from data_agent.api_models import Column, Page, TableCatalog, TableRows, TableSummary
from data_agent.config import database_config

# Deliberately explicit. This is not approval to browse arbitrary production tables.
ALLOWED_TABLES = {
    "payments": "payment_id",
    "ratings": "rating_id",
    "rides": "ride_id",
    "users": "user_id",
    "vehicles": "vehicle_id",
}


class TableNotFound(LookupError):
    pass


def json_cell(value):
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return value if abs(value) <= 2**53 - 1 else str(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def display_type(database_type):
    if database_type in ("smallint", "integer", "bigint"):
        return "integer"
    if database_type in ("numeric", "decimal", "real", "double precision"):
        return "number"
    if database_type == "boolean":
        return "boolean"
    if database_type == "date":
        return "date"
    if database_type.startswith("timestamp"):
        return "datetime"
    if database_type in ("json", "jsonb", "ARRAY"):
        return "json"
    return "string"


class TableBrowser:
    def __init__(self, *, connect=psycopg2.connect, settings=database_config):
        self.connect = connect
        self.settings = settings

    def list_tables(self) -> TableCatalog:
        with closing(self.connect(**self.settings())) as connection:
            connection.set_session(readonly=True)
            with connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = %s AND table_type = 'BASE TABLE' "
                    "AND table_name = ANY(%s) ORDER BY table_name",
                    ("public", list(ALLOWED_TABLES)),
                )
                return TableCatalog(tables=[
                    TableSummary(id=f"public.{name}", label=name.title())
                    for (name,) in cursor.fetchall()
                ])

    def rows(self, table_id: str, limit: int, offset: int) -> TableRows:
        table = table_id.removeprefix("public.")
        if table_id != f"public.{table}" or table not in ALLOWED_TABLES:
            raise TableNotFound()
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("Invalid pagination")
        with closing(self.connect(**self.settings())) as connection:
            connection.set_session(readonly=True)
            with connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT c.column_name, c.data_type FROM information_schema.columns AS c "
                    "WHERE c.table_schema = %s AND c.table_name = %s "
                    "AND EXISTS (SELECT 1 FROM information_schema.tables AS t "
                    "WHERE t.table_schema = c.table_schema AND t.table_name = c.table_name "
                    "AND t.table_type = 'BASE TABLE') ORDER BY c.ordinal_position",
                    ("public", table),
                )
                metadata = cursor.fetchall()
                if not metadata:
                    raise TableNotFound()
                columns = [Column(name=name, type=display_type(kind)) for name, kind in metadata]
                query = sql.SQL("SELECT {} FROM {} ORDER BY {} LIMIT %s OFFSET %s").format(
                    sql.SQL(", ").join(sql.Identifier(column.name) for column in columns),
                    sql.Identifier("public", table),
                    sql.Identifier(ALLOWED_TABLES[table]),
                )
                cursor.execute(query, (limit + 1, offset))
                records = cursor.fetchall()
                return TableRows(
                    table_id=table_id, columns=columns,
                    rows=[[json_cell(cell) for cell in row] for row in records[:limit]],
                    page=Page(limit=limit, offset=offset, has_more=len(records) > limit),
                )
