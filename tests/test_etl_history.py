from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from data_agent.services.etl_files import ETLFileStore
from data_agent.services.etl_history import ETLHistory


class ETLHistoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        env = patch.dict(os.environ, {'ETL_STORAGE_ROOT':'var/etl'})
        env.start(); self.addCleanup(env.stop)
        self.store = ETLFileStore(data_root=self.root)

    def write(self):
        return self.store.write(source='https://user:SECRET@example.org/private/token?key=SECRET#SECRET',
            format='csv', suggested_name='Customer orders', row_count=1,
            writer=lambda path:path.write_text('id\n1\n'))

    def test_independent_records_and_restart(self):
        first, second = self.write(), self.write()
        rows = self.store.history.list()['files']
        self.assertEqual([row['id'] for row in rows], [second.id,first.id])
        self.assertTrue(first.path.is_file() and second.path.is_file())
        self.assertEqual(rows[0]['size_bytes'],second.path.stat().st_size)
        self.assertEqual(rows[0]['row_count'],1)
        self.assertEqual(rows[0]['source'],'example.org')
        self.assertIsNone(rows[0]['source_url'])
        self.assertIsNone(rows[0]['run_id'])
        self.assertIsNone(rows[0]['description'])
        self.assertNotIn('storage_reference',rows[0])
        self.assertNotIn('SECRET',json.dumps(rows))
        self.assertNotIn(str(self.root),json.dumps(rows))
        code = "from data_agent.services.etl_history import ETLHistory; import sys,json; print(json.dumps(ETLHistory(sys.argv[1]).list()))"
        result = subprocess.run([sys.executable,'-c',code,str(self.store.root)],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['files'],rows)

    def test_pagination_missing_and_changed_file(self):
        first, second = self.write(), self.write()
        self.assertTrue(self.store.history.list(limit=1)['has_more'])
        self.assertEqual(self.store.history.list(limit=1,offset=1)['files'][0]['id'],first.id)
        first.path.unlink()
        second.path.write_text('externally changed')
        for row in self.store.history.list()['files']:
            self.assertEqual(row['status'],'failed'); self.assertFalse(row['available'])
        self.assertIsNone(self.store.history.get('missing'))
        with self.assertRaises(ValueError): self.store.history.list(limit=0)

    def test_metadata_failure_rolls_back_new_output(self):
        prior = self.write()
        with patch.object(self.store.history,'insert',side_effect=OSError('disk full')):
            with self.assertRaisesRegex(RuntimeError,'rolled back'): self.write()
        self.assertEqual(list(self.store.root.glob('*.csv')),[prior.path])
        self.assertEqual(len(self.store.history.list()['files']),1)

    def test_empty_and_failed_writer_have_no_ready_record(self):
        self.assertEqual(self.store.history.list()['files'],[])
        self.assertFalse(self.store.root.exists())
        def fail(path):
            path.write_text('partial'); raise OSError('write failed')
        with self.assertRaises(OSError):
            self.store.write(source='',format='csv',writer=fail)
        self.assertEqual(self.store.history.list()['files'],[])


if __name__ == '__main__': unittest.main()
