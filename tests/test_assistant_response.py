import unittest
from unittest.mock import Mock

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from data_agent.agents.router import build_data_agent
from data_agent.agents.sql import build_sql_graph
from data_agent.agents.etl import build_etl_graph
from data_agent.main import run_request
from data_agent.services.assistant_response import assistant_response, InvalidAssistantResult


class AssistantResponseTests(unittest.TestCase):
    def test_sql_contract_excludes_internal_state(self):
        result = {"route_response": "sql", "messages": [HumanMessage(content="question"), {
            "final_answer": "Two users", "is_safe": "Yes",
            "sql_query_execution_result": "[(2,)]", "generated_sql_query": "secret query",
        }]}
        self.assertEqual(assistant_response(result).model_dump(), {
            "answer": "Two users", "route": "sql", "status": "answered",
        })

    def test_decline_does_not_require_execution_result(self):
        result = {"route_response": "sql", "messages": [{"final_answer": "Declined", "is_safe": "No"}]}
        self.assertEqual(assistant_response(result).status, "declined")

    def test_missing_sql_result_is_not_success(self):
        with self.assertRaises(InvalidAssistantResult):
            assistant_response({"route_response": "sql", "messages": [
                {"final_answer": "Looks good", "is_safe": "Yes", "sql_query_execution_result": None},
            ]})

    def test_etl_only_returns_terminal_text_blocks(self):
        result = {"route_response": "etl", "messages": [{"messages": [
            ToolMessage(content="private generated code", tool_call_id="1"),
            AIMessage(content=[{"type": "thinking", "thinking": "private"},
                               {"type": "text", "text": "Tool reported an outcome."}]),
        ]}]}
        response = assistant_response(result)
        self.assertEqual(response.answer, "Tool reported an outcome.")
        self.assertEqual(response.status, "answered")

    def test_malformed_results_rejected(self):
        for result in ({}, {"route_response": "etl", "messages": []},
                       {"route_response": "etl", "messages": [{"messages": [HumanMessage(content="x")]}]}):
            with self.subTest(result=result), self.assertRaises(InvalidAssistantResult):
                assistant_response(result)

    def test_real_sql_graph_with_fake_dependencies(self):
        model = Mock()
        model.invoke.return_value = AIMessage(content="Two users")
        model.with_structured_output.return_value.invoke.return_value.model_dump.return_value = {
            "answer": "Yes", "comments": "Allowed",
        }
        database = Mock()
        database.schema_detail.return_value = "users(user_id integer)"
        database.execute_sql.return_value = "[(2,)]"
        child = build_sql_graph(llm_factory=lambda level: model,
                                database_factory=lambda settings: database,
                                database_settings=lambda: {})
        router = Mock()
        router.with_structured_output.return_value.invoke.return_value.model_dump.return_value = {
            "answer": "sql", "comments": "Database question",
        }
        parent = build_data_agent(llm_factory=lambda level: router, sql_graph=child, etl_graph=Mock())
        response = assistant_response(run_request("How many users?", agent=parent))
        self.assertEqual(response.answer, "Two users")
        database.execute_sql.assert_called_once()

    def test_real_etl_graph_with_fake_model_no_tools_executed(self):
        model = Mock()
        model.bind_tools.return_value.invoke.return_value = AIMessage(content="Please specify an API URL.")
        child = build_etl_graph(data_root=".", llm_factory=lambda level: model)
        router = Mock()
        router.with_structured_output.return_value.invoke.return_value.model_dump.return_value = {
            "answer": "etl", "comments": "Extraction",
        }
        parent = build_data_agent(llm_factory=lambda level: router, sql_graph=Mock(), etl_graph=child)
        response = assistant_response(run_request("Extract data", agent=parent))
        self.assertEqual(response.route, "etl")
        self.assertEqual(response.answer, "Please specify an API URL.")
