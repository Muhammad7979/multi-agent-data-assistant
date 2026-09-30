"""Real router wiring and HTTP boundary; classifier/provider decisions are mocked."""
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from data_agent.agents.policy import PolicyAnswer, PolicySource, PolicyAgentError, run_policy_question
from data_agent.agents.router import build_data_agent, ROUTING_INSTRUCTIONS
from data_agent.agents.state import RouterSchema
from data_agent.api import create_app
from data_agent.main import run_request


class PolicyRoutingTests(unittest.TestCase):
    def setup_graph(self, route):
        router, sql, etl, policy = Mock(), Mock(), Mock(), Mock()
        router.with_structured_output.return_value.invoke.return_value = RouterSchema(answer=route, comments='PRIVATE')
        sql.invoke.return_value = {'is_safe': 'Yes', 'sql_query_execution_result': '[]', 'final_answer': 'No records'}
        etl.invoke.return_value = {'messages': [AIMessage(content='ETL response')]}
        policy.return_value = PolicyAnswer(answer='20 days [1]', status='answered', sources=[
            PolicySource(source_id=1, document_id='doc', filename='handbook.pdf', page=2)])
        graph = build_data_agent(llm_factory=lambda _: router, sql_graph=sql, etl_graph=etl, policy_runner=policy)
        return graph, router, sql, etl, policy

    def test_representative_intents_and_delegation(self):
        cases = [('Show employee payments this month.', 'sql'), ('Which customers spent the most?', 'sql'),
                 ('Extract payments from an API and save CSV.', 'etl'), ('Transform reimbursement CSV data.', 'etl'),
                 ('What is our annual leave policy?', 'policy'),
                 ('What does the employee handbook say about remote work?', 'policy'),
                 ("What are the company's reimbursement rules?", 'policy'),
                 ('Show reimbursement payments.', 'sql'),
                 ('What does company policy say about reimbursements?', 'policy')]
        for question, route in cases:
            with self.subTest(question=question):
                graph, router, sql, etl, policy = self.setup_graph(route)
                result = run_request(question, agent=graph)
                self.assertEqual(result['route_response'], route)
                self.assertEqual(sql.invoke.call_count, int(route == 'sql'))
                self.assertEqual(etl.invoke.call_count, int(route == 'etl'))
                self.assertEqual(policy.call_count, int(route == 'policy'))
                messages = router.with_structured_output.return_value.invoke.call_args.args[0]
                self.assertEqual(messages[0].type, 'system')
                self.assertIn('Use intent, not keyword matching', messages[0].content)
                self.assertEqual(messages[1].content, question)
                self.assertIn(f'{question} -> {route}', ROUTING_INSTRUCTIONS)

    def test_policy_http_sources_and_no_internal_state(self):
        graph, _, _, _, policy = self.setup_graph('policy')
        with patch('data_agent.main.build_data_agent', return_value=graph):
            with TestClient(create_app(browser=Mock())) as client:
                result = client.post('/api/assistant', json={'question': 'Leave policy?'})
                self.assertEqual(result.status_code, 200)
                self.assertEqual(set(result.json()), {'answer', 'route', 'status', 'sources'})
                self.assertEqual(result.json()['sources'][0]['filename'], 'handbook.pdf')
                self.assertNotIn('PRIVATE', result.text)
                policy.return_value = PolicyAnswer(answer='Not enough evidence', status='insufficient_evidence', sources=[])
                result = client.post('/api/assistant', json={'question': 'Missing policy?'})
                self.assertEqual(result.json()['status'], 'insufficient_evidence')
                self.assertEqual(result.json()['sources'], [])
                policy.side_effect = PolicyAgentError('PRIVATE failure')
                result = client.post('/api/assistant', json={'question': 'Leave?'})
                self.assertEqual(result.status_code, 503)
                self.assertEqual(result.json()['route'], 'policy')
                self.assertNotIn('PRIVATE', result.text)

    def test_default_policy_delegation_is_lazy(self):
        graph, router, sql, etl, _ = self.setup_graph('sql')
        with patch('data_agent.agents.router.run_policy_question') as runner:
            graph = build_data_agent(llm_factory=lambda _: router, sql_graph=sql, etl_graph=etl)
            run_request('Payments', agent=graph)
            runner.assert_not_called()
            router.with_structured_output.return_value.invoke.return_value = RouterSchema(answer='policy', comments='')
            runner.return_value = PolicyAnswer(answer='Unavailable', status='insufficient_evidence', sources=[])
            run_request('Leave?', agent=graph)
            self.assertEqual(runner.call_args.args, ('Leave?',))

    def test_request_scoped_retriever_closes_on_success_and_failure(self):
        retriever = Mock()
        retriever.retrieve.return_value = []
        self.assertEqual(run_policy_question('Leave?', retriever_factory=lambda: retriever).status, 'insufficient_evidence')
        retriever.close.assert_called_once()
        retriever.reset_mock()
        retriever.initialize.side_effect = RuntimeError('PRIVATE')
        with self.assertRaisesRegex(PolicyAgentError, 'Policy retrieval failed'):
            run_policy_question('Leave?', retriever_factory=lambda: retriever)
        retriever.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
