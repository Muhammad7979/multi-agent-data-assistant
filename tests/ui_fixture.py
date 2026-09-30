"""Explicit local UI fixture: no database, LLM, HTTP extraction, or generated code.

Run with: uv run python -m uvicorn tests.ui_fixture:app --host 127.0.0.1 --port 8000
Use only for manual UI/contract checks; it deliberately returns synthetic data.
"""
import time

from langchain_core.messages import AIMessage

from data_agent.api import create_app
from data_agent.services.table_browser import TableNotFound


def fake_request(question):
    time.sleep(0.5)
    if question == "failure":
        raise TimeoutError("Synthetic timeout")
    if question == "etl":
        return {"route_response": "etl", "messages": [{"messages": [AIMessage(content="The tool reported a saved file.")]}]}
    return {"route_response": "sql", "messages": [{
        "final_answer": "Request declined." if question == "decline" else "There are 51 example users.",
        "is_safe": "No" if question == "decline" else "Yes",
        "sql_query_execution_result": "[(51,)]",
    }]}


class FakeTables:
    def list_tables(self):
        return {"tables": [{"id": "public.users", "label": "Users"}, {"id": "public.rides", "label": "Rides"}]}

    def rows(self, table_id, limit, offset):
        if table_id not in ("public.users", "public.rides"):
            raise TableNotFound()
        records = [[i, f"Example user {i}", None, True] for i in range(1, 52)] if table_id == "public.users" else []
        return {
            "table_id": table_id,
            "columns": [{"name": "user_id", "type": "integer"}, {"name": "name", "type": "string"},
                        {"name": "city", "type": "string"}, {"name": "is_active", "type": "boolean"}],
            "rows": records[offset:offset + limit],
            "page": {"limit": limit, "offset": offset, "has_more": len(records) > offset + limit},
        }


app = create_app(runner=fake_request, browser=FakeTables())
