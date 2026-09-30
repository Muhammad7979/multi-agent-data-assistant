from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage, HumanMessage
from data_agent.agents.etl import build_etl_graph
from data_agent.services.etl_files import ETLFileStore, filename_stem
from data_agent.services.extraction import extract_load


class ETLFileTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.env = patch.dict('os.environ', {'ETL_STORAGE_ROOT': 'var/etl'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.store = ETLFileStore(data_root=self.root)

    def test_names_fallback_and_configuration(self):
        self.assertFalse(self.store.root.exists())
        self.assertEqual(self.store.root, self.root/'var/etl/outputs')
        self.assertEqual(filename_stem('Customer Orders', 'https://test.invalid/orders'), 'customer_orders')
        for suggestion in (None, '', '!!!', '../../bad', 'C:\\escape', '/tmp/file'):
            self.assertEqual(filename_stem(suggestion, 'https://test.invalid/orders?token=SECRET'), 'orders')
        self.assertEqual(filename_stem('CON', ''), 'dataset_con')
        self.assertLessEqual(len(filename_stem('x'*1000, '')), 64)
        self.assertEqual(filename_stem(None, ''), 'dataset')

    def test_repeated_and_concurrent_writes(self):
        def write(_):
            return self.store.write(source='https://test.invalid/orders', format='csv',
                suggested_name='Customer Orders', writer=lambda path: path.write_text('id\n1\n'))
        with patch('data_agent.services.etl_files.datetime') as clock, ThreadPoolExecutor(max_workers=8) as pool:
            clock.now.return_value = datetime(2026, 9, 30, 11, 25, 30, tzinfo=timezone.utc)
            files = list(pool.map(write, range(24)))
        self.assertEqual(len({f.path for f in files}),24)
        for record in files:
            self.assertEqual(record.path.read_text(), 'id\n1\n')
            self.assertRegex(record.path.name, r'^customer_orders_\d{8}_\d{6}_\d{6}Z_[0-9a-f]{16}\.csv$')
            self.assertTrue(record.created_at.endswith('+00:00'))
        self.assertEqual(list((self.store.root/'.staging').iterdir()), [])

    def test_failed_write_never_publishes(self):
        def fail(path):
            path.write_text('partial')
            raise OSError('disk failure')
        with self.assertRaises(OSError):
            self.store.write(source='',format='csv',writer=fail)
        self.assertEqual(list(self.store.root.glob('*.csv')), [])
        self.assertEqual(list((self.store.root/'.staging').iterdir()), [])

    def test_existing_target_is_not_overwritten(self):
        import os
        real_link = os.link
        def collision(source,target):
            if not hasattr(collision,'called'):
                collision.called=True
                Path(target).write_text('older output')
            real_link(source,target)
        with patch('data_agent.services.etl_files.os.link',side_effect=collision):
            record=self.store.write(source='',format='csv',writer=lambda p:p.write_text('new output'))
        self.assertEqual(record.path.read_text(),'new output')
        self.assertEqual(sorted(p.read_text() for p in self.store.root.glob('*.csv')),['new output','older output'])

    def test_extraction_formats_and_repetition(self):
        response=Mock(); response.json.return_value={'results':[{'id':1,'name':'A'}]}
        with patch('data_agent.services.extraction.requests.get',return_value=response):
            for format in ('csv','csv','json'):
                result=extract_load('https://test.invalid/orders','../../ignored',format,data_root=self.root)
                self.assertTrue(result.startswith('Data successfully'),result)
            self.assertEqual(len(list(self.store.root.glob('*.csv'))),2)
            self.assertIn('"id":1',next(self.store.root.glob('*.json')).read_text())
            with patch('pandas.DataFrame.to_parquet',side_effect=lambda path,**kwargs:Path(path).write_bytes(b'PAR1fixture')) as writer:
                self.assertTrue(extract_load('https://test.invalid/orders','ignored','parquet',data_root=self.root).startswith('Data successfully'))
                writer.assert_called_once()
            with patch('pandas.DataFrame.to_csv',side_effect=OSError('private')):
                self.assertTrue(extract_load('https://test.invalid/orders','','csv',data_root=self.root).startswith('Failed'))
            self.assertEqual(len(list(self.store.root.glob('*.csv'))),2)

    def test_repeated_tool_calls_deduplicate_only_within_execution(self):
        model=Mock()
        call=lambda id,name:{'name':'extract_load_tool','args':{'url':'https://test.invalid/orders','output_folder':'ignored','format':'csv','filename_stem':name},'id':id,'type':'tool_call'}
        model.bind_tools.return_value.invoke.side_effect=[
            AIMessage(content='',tool_calls=[call('a','orders'),call('b','same orders')]), AIMessage(content='Done'),
            AIMessage(content='',tool_calls=[call('c','orders')]), AIMessage(content='Done')]
        graph=build_etl_graph(data_root=self.root,llm_factory=lambda _:model)
        response=Mock(); response.json.return_value={'results':[{'id':1}]}
        with patch('data_agent.services.extraction.requests.get',return_value=response) as fetch:
            for _ in range(2): graph.invoke({'messages':[HumanMessage(content='Extract orders')]})
            self.assertEqual(fetch.call_count,2)
        self.assertEqual(len(list(self.store.root.glob('*.csv'))),2)


if __name__ == '__main__': unittest.main()
