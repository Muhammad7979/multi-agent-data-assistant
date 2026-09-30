import json
import io
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from data_agent.api import create_app
from data_agent.services.etl_browser import ETLBrowser, PREVIEW_BYTES
from data_agent.services.etl_files import ETLFileStore


class ETLApiTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name).resolve()
        env = patch.dict('os.environ', {'ETL_STORAGE_ROOT':'var/etl'})
        env.start(); self.addCleanup(env.stop)
        self.store = ETLFileStore(data_root=self.root)
        self.browser = ETLBrowser(history=self.store.history)
        self.client = TestClient(create_app(etl_browser=self.browser))
        self.client.__enter__(); self.addCleanup(self.client.__exit__,None,None,None)
        self.url = '/api/etl/files'

    def write(self, content=b'id,name\n1,Alice\n', format='csv'):
        return self.store.write(source='https://user:SECRET@example.com/token?key=SECRET',format=format,
                                writer=lambda p:p.write_bytes(content),suggested_name='same name')

    def test_list_details_download_and_independent_files(self):
        self.assertEqual(self.client.get(self.url).json()['files'],[])
        a,b = self.write(),self.write(b'id,name\n2,Bob\n')
        result = self.client.get(self.url+'?limit=1').json()
        self.assertEqual(result['files'][0]['id'],b.id)
        self.assertTrue(result['page']['has_more'])
        self.assertEqual(self.client.get(self.url+'?limit=1&offset=1').json()['files'][0]['id'],a.id)
        for file in (a,b):
            details=self.client.get(f'{self.url}/{file.id}')
            self.assertEqual(details.status_code,200)
            self.assertNotIn('storage_reference',details.json())
            self.assertNotIn('SECRET',details.text)
            self.assertNotIn(str(self.root),details.text)
            response=self.client.get(f'{self.url}/{file.id}/download')
            self.assertEqual(response.content,file.path.read_bytes())
            self.assertIn(file.path.name,response.headers['content-disposition'])
            self.assertIn('text/csv',response.headers['content-type'])

    def test_csv_empty_malformed_and_bounded(self):
        cases=[(b'',200,[]),(b'id,name\n',200,[]),(b'id,name\n1,Alice\n',200,[['1','Alice']]),
               (b'id,name\n1\n',422,None),(b'id,name\n"unterminated',422,None),(b'\xff',422,None)]
        for content,status,rows in cases:
            file=self.write(content)
            response=self.client.get(f'{self.url}/{file.id}/preview')
            self.assertEqual(response.status_code,status,response.text)
            if rows is not None: self.assertEqual(response.json()['rows'],rows)
        file=self.write(b'id,name\n'+b'1,Alice\n'*10000)
        result=self.client.get(f'{self.url}/{file.id}/preview').json()
        self.assertEqual(len(result['rows']),50)
        self.assertTrue(result['truncated'])

    def test_json_objects_arrays_lines_and_limits(self):
        for content in (b'{"name":"Alice"}',b'[{"id":1},{"id":2}]',b'{"id":1}\n{"id":2}\n'):
            file=self.write(content,'json')
            response=self.client.get(f'{self.url}/{file.id}/preview')
            self.assertEqual(response.status_code,200,response.text)
            json.loads(response.json()['text'])
            self.assertFalse(response.json()['truncated'])
            download = self.client.get(f'{self.url}/{file.id}/download')
            self.assertEqual(download.content,content)
            self.assertIn('application/x-ndjson' if content.count(b'\n') > 1 else 'application/json',download.headers['content-type'])
        file=self.write(b'{broken','json')
        self.assertEqual(self.client.get(f'{self.url}/{file.id}/preview').status_code,422)
        file=self.write(br'{"value":"\ud800"}','json')
        response=self.client.get(f'{self.url}/{file.id}/preview')
        self.assertEqual(response.status_code,422)
        self.assertEqual(response.json()['error']['code'],'FILE_CORRUPT')
        file=self.write(json.dumps({'nested':[[['x'*5000]]]}).encode(),'json')
        self.assertTrue(self.client.get(f'{self.url}/{file.id}/preview').json()['truncated'])
        file=self.write(b'["'+b'x'*(PREVIEW_BYTES*2)+b'"]','json')
        response=self.client.get(f'{self.url}/{file.id}/preview').json()
        self.assertEqual(response['validation'],'unvalidated_prefix')
        self.assertLessEqual(len(response['text']),20000)

    def test_unsupported_preview_downloads_original(self):
        file=self.write(b'PAR1-fixture','parquet')
        self.assertEqual(self.client.get(f'{self.url}/{file.id}/preview').status_code,415)
        response=self.client.get(f'{self.url}/{file.id}/download')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.content,b'PAR1-fixture')
        self.assertIn('parquet',response.headers['content-type'])

    def test_missing_changed_invalid_and_unsafe_reference(self):
        file=self.write()
        file.path.unlink()
        for suffix in ('','/preview','/download'):
            self.assertEqual(self.client.get(f'{self.url}/{file.id}{suffix}').status_code,404)
        self.assertFalse(self.client.get(self.url).json()['files'][0]['available'])
        file=self.write(); file.path.write_text('changed')
        self.assertEqual(self.client.get(f'{self.url}/{file.id}/download').status_code,409)
        for value in ('bad','%2e%2e%5csecret.txt',"x%27%20OR%201=1"):
            self.assertEqual(self.client.get(f'{self.url}/{value}/download').status_code,400)
        self.assertEqual(self.client.get(self.url+'/0000000000000000').status_code,404)
        outside=self.root/'private.txt'; outside.write_text('PRIVATE_SECRET')
        with closing(sqlite3.connect(self.store.history.path)) as conn, conn:
            conn.execute('UPDATE etl_files SET storage_reference=? WHERE id=?',(str(outside),file.id))
        response=self.client.get(f'{self.url}/{file.id}/download')
        self.assertEqual(response.status_code,409)
        self.assertNotIn('PRIVATE_SECRET',response.text)
        self.assertNotIn(str(outside),response.text)
        self.assertNotIn(str(outside),self.client.get(self.url).text)

    def test_query_validation_and_storage_failure(self):
        for query in ('limit=0','offset=-1','path=secret','limit=1&limit=2'):
            self.assertEqual(self.client.get(self.url+'?'+query).status_code,400)
        with patch.object(self.store.history,'list',side_effect=sqlite3.DatabaseError('PRIVATE')):
            response=self.client.get(self.url)
            self.assertEqual(response.status_code,503)
            self.assertNotIn('PRIVATE',response.text)

    def test_preview_reads_only_a_bounded_prefix(self):
        class BoundedFile(io.BytesIO):
            def read(self, size=-1):
                self_read = size
                if not 0 <= self_read <= PREVIEW_BYTES + 1:
                    raise AssertionError('Unbounded file read')
                return super().read(size)
        handle = BoundedFile(b'["' + b'x' * (PREVIEW_BYTES * 2) + b'"]')
        with patch.object(self.browser, 'open', return_value=({'format':'json'},handle)):
            result = self.browser.preview('unused')
        self.assertTrue(result['truncated'])
        file = self.write(b'value\n' + b'x' * 200000 + b'\n')
        response = self.client.get(f'{self.url}/{file.id}/preview')
        self.assertEqual(response.status_code,413)
        self.assertEqual(response.json()['error']['code'],'PREVIEW_LIMIT')


if __name__ == '__main__': unittest.main()
