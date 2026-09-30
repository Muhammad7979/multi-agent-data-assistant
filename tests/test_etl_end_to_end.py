"""Real HTTP extraction and process-restart audit; provider decisions are faked."""
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from data_agent.agents.etl import build_etl_graph
from data_agent.agents.router import build_data_agent
from data_agent.api import create_app
from data_agent.main import run_request
from data_agent.services.etl_browser import ETLBrowser
from data_agent.services.etl_files import ETLFileStore


class ETLEndToEndTests(unittest.TestCase):
    def test_two_full_runs_and_api_process_restart(self):
        class Source(BaseHTTPRequestHandler):
            calls = 0

            def do_GET(self):
                Source.calls += 1
                body = json.dumps({'results': [{'id': 1}, {'id': 2}]}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.dict(os.environ, {'ETL_STORAGE_ROOT': str(root / 'etl')}):
                source = ThreadingHTTPServer(('127.0.0.1', 0), Source)
                thread = threading.Thread(target=source.serve_forever, daemon=True)
                thread.start()
                try:
                    store = ETLFileStore(data_root=root)
                    files = []
                    for _ in range(2):
                        model = Mock()
                        step = 0

                        def decide(prompt):
                            nonlocal step
                            step += 1
                            if step == 1:
                                return AIMessage(content='', tool_calls=[dict(name='extract_load_tool', id='extract', type='tool_call', args=dict(
                                    url=f'http://127.0.0.1:{source.server_port}/orders?key=PRIVATE_TOKEN',
                                    output_folder='ignored', format='csv', filename_stem='customer_orders'))])
                            if step == 2:
                                record = store.history.list()['files'][0]
                                return AIMessage(content='', tool_calls=[dict(name='transform_load_tool', id='transform', type='tool_call', args=dict(
                                    input_file_path=str(store.root / record['filename']), output_folder='ignored', output_format='csv', user_question='Keep first row'))])
                            return AIMessage(content='Done')

                        def generate(prompt):
                            destination = re.search(r'save the data at (.+) in csv format', prompt).group(1)
                            input_path = re.search(r'file : (.+)\n', prompt).group(1).strip()
                            # Starts with "output": catches the old lstrip('python') bug.
                            return AIMessage(content=f"output = {destination}\nimport pandas as pd\npd.read_csv({input_path!r}).head(1).to_csv(output, index=False)")

                        model.bind_tools.return_value.invoke.side_effect = decide
                        model.invoke.side_effect = generate
                        router = Mock()
                        router.with_structured_output.return_value.invoke.return_value.model_dump.return_value = {'answer': 'etl', 'comments': 'Extraction and transformation'}
                        graph = build_data_agent(llm_factory=lambda _: router, sql_graph=Mock(),
                            etl_graph=build_etl_graph(data_root=root, llm_factory=lambda _: model))
                        with TestClient(create_app(runner=lambda q: run_request(q, agent=graph), etl_browser=ETLBrowser(history=store.history))) as client:
                            response = client.post('/api/assistant', json={'question': 'Extract orders and keep the first row.'})
                            self.assertEqual(response.status_code, 200, response.text)
                            body = response.json()
                            self.assertEqual(body['route'], 'etl')
                            self.assertEqual(body['etl_status'], 'completed')
                            self.assertEqual(len(body['files']), 2)
                            self.assertIn('Extraction completed', body['answer'])
                            self.assertIn('Transformation completed', body['answer'])
                            self.assertNotIn('PRIVATE_TOKEN', response.text)
                            self.assertNotIn(str(root), response.text)
                            for file in body['files']:
                                path = store.root / file['filename']
                                self.assertTrue(path.is_file())
                                self.assertTrue(file['created_at'].endswith('+00:00'))
                                file['bytes'] = path.read_bytes()
                                files.append(file)
                    self.assertEqual(Source.calls, 2)
                    self.assertEqual(len({file['id'] for file in files}), 4)
                    self.assertEqual(len({file['filename'] for file in files}), 4)
                    self.assertEqual(files[0]['bytes'], files[2]['bytes'])
                    self.assertEqual(files[1]['bytes'], files[3]['bytes'])
                    self.assertEqual(files[1]['bytes'], b'id\r\n1\r\n')
                finally:
                    source.shutdown(); source.server_close(); thread.join(timeout=5)

                # Start and stop two genuinely separate backend processes on the same catalog.
                for _ in range(2):
                    with socket.socket() as sock:
                        sock.bind(('127.0.0.1', 0))
                        port = sock.getsockname()[1]
                    with tempfile.TemporaryFile() as log:
                        process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'data_agent.api:app', '--host', '127.0.0.1', '--port', str(port)],
                            env=os.environ.copy(), stdout=log, stderr=log)
                        try:
                            url = f'http://127.0.0.1:{port}/api/etl/files'
                            deadline = time.monotonic() + 90
                            while True:
                                try:
                                    response = requests.get(url, timeout=2)
                                    if response.status_code == 200:
                                        break
                                except requests.RequestException:
                                    pass
                                if process.poll() is not None or time.monotonic() > deadline:
                                    log.seek(0)
                                    self.fail('Audit backend did not start: ' + log.read().decode(errors='replace'))
                                time.sleep(.1)
                            self.assertEqual(len(response.json()['files']), 4)
                            for file in files:
                                base = url + '/' + file['id']
                                self.assertEqual(requests.get(base, timeout=5).json()['filename'], file['filename'])
                                self.assertEqual(requests.get(base + '/preview', timeout=5).status_code, 200)
                                self.assertEqual(requests.get(base + '/download', timeout=5).content, file['bytes'])
                        finally:
                            process.terminate()
                            try:
                                process.wait(timeout=10)
                            except subprocess.TimeoutExpired:
                                process.kill(); process.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
