import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage

from data_agent.agents.etl import build_etl_graph
from data_agent.api import create_app
from data_agent.services.assistant_response import assistant_response
from data_agent.services.etl_browser import ETLBrowser
from data_agent.services.etl_files import ETLFileStore


class ETLAssistantTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        env = patch.dict('os.environ', {'ETL_STORAGE_ROOT': 'var/etl'})
        env.start()
        self.addCleanup(env.stop)
        self.store = ETLFileStore(data_root=self.root)
        self.model = Mock()
        self.fetch = Mock()
        self.fetch.json.return_value = {'results': [{'id': 1}, {'id': 2}]}

    def extract(self, identifier='extract'):
        return dict(name='extract_load_tool', id=identifier, type='tool_call', args=dict(
            url='https://example.test/orders?token=SECRET', output_folder='ignored', format='csv', filename_stem='orders'))

    def run_graph(self, responses):
        self.model.bind_tools.return_value.invoke.side_effect = responses
        graph = build_etl_graph(data_root=self.root, llm_factory=lambda _: self.model)
        with patch('data_agent.services.extraction.requests.get', return_value=self.fetch) as fetch:
            child = graph.invoke({'messages': [HumanMessage(content='Extract and transform orders')]})
        return {'route_response': 'etl', 'messages': [child]}, fetch.call_count

    def test_saved_file_survives_summary_failure_and_is_accessible(self):
        result, calls = self.run_graph([
            AIMessage(content='', tool_calls=[self.extract(), self.extract('again')]),
            RuntimeError('PRIVATE provider error'),
        ])
        response = assistant_response(result)
        self.assertEqual(calls, 1)
        self.assertEqual(response.etl_status, 'response_failed')
        self.assertEqual(len(response.files), 1)
        file = response.files[0]
        self.assertEqual(file.row_count, 2)
        self.assertNotIn('SECRET', response.model_dump_json())
        self.assertNotIn(str(self.root), response.model_dump_json())
        self.assertIn('Saved files are preserved', response.answer)
        with TestClient(create_app(runner=lambda _: result, etl_browser=ETLBrowser(history=self.store.history))) as client:
            body = client.post('/api/assistant', json={'question': 'Extract'}).json()
            self.assertEqual(body['files'][0]['id'], file.id)
            metadata = client.get('/api/etl/files/' + file.id).json()
            self.assertEqual(metadata['filename'], file.filename)
            self.assertEqual(metadata['size_bytes'], file.size_bytes)
            self.assertEqual(client.get('/api/etl/files/' + file.id + '/download').content, b'id\r\n1\r\n2\r\n')

    def test_model_claims_do_not_override_failed_extraction_or_write(self):
        for stage in ('api', 'write'):
            with self.subTest(stage=stage):
                self.fetch.raise_for_status.side_effect = RuntimeError('SECRET') if stage == 'api' else None
                with patch('pandas.DataFrame.to_csv', side_effect=OSError('PRIVATE')):
                    result, calls = self.run_graph([AIMessage(content='', tool_calls=[self.extract()]), AIMessage(content='Everything saved!')])
                response = assistant_response(result)
                self.assertEqual(response.etl_status, 'failed')
                self.assertEqual(response.files, [])
                self.assertIn('API extraction failed' if stage == 'api' else 'File writing', response.answer)
                self.assertNotIn('Everything saved', response.answer)
                self.assertEqual(calls, 1)

    def test_transformation_success_failure_and_missing_output(self):
        source = self.root / 'input.csv'
        source.write_text('id\n1\n2\n')
        call = dict(name='transform_load_tool', id='transform', type='tool_call', args=dict(
            input_file_path=str(source), output_folder='ignored', output_format='csv', user_question='Keep one row'))
        for mode in ('success', 'empty', 'error', 'missing', 'write_error'):
            with self.subTest(mode=mode):
                def generate(prompt):
                    destination = re.search(r'save the data at (.+) in csv format', prompt).group(1)
                    if mode == 'error':
                        code = "raise ValueError('PRIVATE')"
                    elif mode == 'missing':
                        code = 'pass'
                    elif mode == 'write_error':
                        code = "raise OSError('PRIVATE')"
                    elif mode == 'empty':
                        code = f"from pathlib import Path\nPath({destination}).write_bytes(b'')"
                    else:
                        code = f"import pandas as pd\npd.DataFrame({{'id':[1]}}).to_csv({destination}, index=False)"
                    return AIMessage(content=code)
                self.model.invoke.side_effect = generate
                result, _ = self.run_graph([AIMessage(content='', tool_calls=[call]), AIMessage(content='Saved!')])
                response = assistant_response(result)
                self.assertEqual(response.etl_status, 'completed' if mode in ('success', 'empty') else 'failed')
                self.assertNotIn('PRIVATE', response.answer)
                if mode in ('success', 'empty'):
                    self.assertEqual(len(response.files), 1)
                    self.assertIsNone(response.files[0].row_count)
                    self.assertIn('Transformation completed', response.answer)
                    self.assertTrue(self.store.history.get(response.files[0].id)['available'])
                else:
                    self.assertEqual(response.files, [])
                self.assertEqual(source.read_text(), 'id\n1\n2\n')

    def test_partial_failure_retains_extraction_file(self):
        call = dict(name='transform_load_tool', id='transform', type='tool_call', args=dict(
            input_file_path=str(self.root / 'missing.csv'), output_folder='ignored', output_format='csv', user_question='Transform'))
        result, _ = self.run_graph([AIMessage(content='', tool_calls=[self.extract(), call]), AIMessage(content='Done')])
        response = assistant_response(result)
        self.assertEqual(response.etl_status, 'partial')
        self.assertEqual(len(response.files), 1)
        self.assertIn('Transformation failed', response.answer)


if __name__ == '__main__':
    unittest.main()
