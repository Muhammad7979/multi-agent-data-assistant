import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from data_agent.api import create_app
from data_agent.config import PolicyIngestionSettings
from data_agent.services.policy_ingestion import PolicyIngestor
from data_agent.services.policy_management import PolicyManagement
from tests.test_policy_ingestion import FakeVectors


class PolicyManagementApiTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.vectors = FakeVectors()
        def delete(doc):
            if self.vectors.fail_delete:
                raise RuntimeError('PRIVATE')
            self.vectors.records = {k:v for k,v in self.vectors.records.items() if v['doc'] != doc}
        self.vectors.delete_document_chunks = delete
        self.embeddings = Mock()
        self.embeddings.embed_documents.side_effect = lambda texts: [[1.,0.,0.] for _ in texts]
        settings = PolicyIngestionSettings(embedding_model='fake', embedding_dimensions=3, max_file_bytes=100)
        self.ingestor = PolicyIngestor(root=Path(temp.name), settings=settings, vectors=self.vectors,
                                      embeddings_factory=lambda _: self.embeddings)
        management = PolicyManagement(ingestor_factory=lambda: self.ingestor,
                                      documents=self.ingestor.documents, settings=settings)
        self.client = TestClient(create_app(policy_management=management))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.url = '/api/policy/documents'

    def upload(self, content=b'Leave is 20 days.', name='policy.txt', mime='text/plain', url=None):
        return self.client.request('PUT' if url else 'POST', url or self.url, content=content,
                                   headers={'X-Filename': name, 'Content-Type': mime})

    def test_crud_status_and_public_contract(self):
        self.assertEqual(self.client.get(self.url).json()['documents'], [])
        response = self.upload()
        self.assertEqual(response.status_code, 201, response.text)
        document = response.json()
        self.assertEqual(document['status'], 'ready')
        self.assertEqual(set(document), {'id','name','type','status','created_at','updated_at',
                                       'size_bytes','chunk_count','has_indexed_version','error_code'})
        url = self.url + '/' + document['id']
        self.assertEqual(self.client.get(url).json(), document)
        self.assertEqual(self.client.get(url+'/status').json(), document)
        self.assertEqual(len(self.client.get(self.url).json()['documents']), 1)
        self.assertEqual(self.upload(b'New leave policy', url=url).status_code, 200)
        self.assertEqual({v['text'] for v in self.vectors.records.values()}, {'New leave policy'})
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertEqual(self.vectors.records, {})
        self.assertEqual(self.ingestor.documents.active_generation_ids(), [])
        self.assertEqual(list((self.ingestor.root/'originals').iterdir()), [])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)

    def test_validation_missing_and_pagination(self):
        for content, name, mime, status in [(b'', 'x.txt','text/plain',400),
                (b'x','x.docx','application/octet-stream',415),(b'x','../x.txt','text/plain',400),
                (b'x'*101,'x.txt','text/plain',413),(b'x','x.pdf','application/pdf',415)]:
            self.assertEqual(self.upload(content,name,mime).status_code,status)
        missing = self.url+'/'+str(uuid4())
        self.assertEqual(self.upload(url=missing).status_code,404)
        self.assertEqual(self.client.get(missing+'/status').status_code,404)
        self.assertEqual(self.client.get(self.url+'/invalid').status_code,400)
        self.assertEqual(self.client.get(self.url+'?limit=0').status_code,400)
        self.upload(); self.upload()
        self.assertTrue(self.client.get(self.url+'?limit=1').json()['page']['has_more'])
        self.assertEqual(self.client.get(self.url+'?offset=10').json()['documents'],[])

    def test_processing_failures_and_old_version_preservation(self):
        document = self.upload().json()
        url = self.url+'/'+document['id']
        self.embeddings.embed_documents.side_effect = RuntimeError('PRIVATE')
        result = self.upload(url=url)
        self.assertEqual(result.status_code,503)
        self.assertEqual(result.json()['document']['status'],'failed')
        self.assertTrue(result.json()['document']['has_indexed_version'])
        self.assertNotIn('PRIVATE',result.text)
        self.embeddings.embed_documents.side_effect = lambda texts: [[1.,0.,0.] for _ in texts]
        self.vectors.fail = True
        self.assertEqual(self.upload().json()['error']['code'],'INDEXING_FAILED')
        result = self.upload(b'   ')
        self.assertEqual(result.status_code,400)
        self.assertEqual(result.json()['error']['code'],'NO_EXTRACTABLE_TEXT')
        self.assertEqual(self.upload(b'\xff').status_code,400)

    def test_delete_failure_deactivates_and_is_retryable(self):
        doc = self.upload().json()
        url = self.url+'/'+doc['id']
        self.vectors.fail_delete = True
        result = self.client.delete(url)
        self.assertEqual(result.status_code,503)
        self.assertNotIn('PRIVATE',result.text)
        self.assertEqual(self.ingestor.documents.active_generation_ids(),[])
        self.assertEqual(self.client.get(url+'/status').json()['error_code'],'DELETE_PENDING')
        self.assertEqual(self.upload(url=url).status_code,409)
        self.vectors.fail_delete = False
        self.assertEqual(self.client.delete(url).status_code,204)

    def test_pending_processing_status_and_parse_failure(self):
        self.ingestor.initialize()
        doc, gen = self.ingestor.documents.begin(None, 'pending.txt', 'text/plain', 'hash', 1)
        url = self.url+'/'+doc
        self.assertEqual(self.client.get(url+'/status').json()['status'], 'pending')
        self.ingestor.documents.processing(doc, gen)
        self.assertEqual(self.client.get(url+'/status').json()['status'], 'processing')
        self.assertEqual(self.upload(url=url).status_code, 409)
        self.ingestor.close()
        with patch('data_agent.services.policy_ingestion.extract_text', side_effect=ValueError('PRIVATE parser')):
            result = self.upload()
        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.json()['error']['code'], 'PARSING_FAILED')
        self.assertNotIn('PRIVATE', result.text)

    def test_real_chroma_retrieval_after_http_replace_delete(self):
        code = '''
import sys
from pathlib import Path
from unittest.mock import Mock
from fastapi.testclient import TestClient
from data_agent.api import create_app
from data_agent.config import PolicyIngestionSettings
from data_agent.services.policy_ingestion import PolicyIngestor
from data_agent.services.policy_retrieval import PolicyRetriever
from data_agent.services.policy_management import PolicyManagement
settings=PolicyIngestionSettings(embedding_model='fake',embedding_dimensions=3)
emb=Mock()
emb.embed_documents.side_effect=lambda texts:[[1.,0.,0.] for _ in texts]
emb.embed_query.return_value=[1.,0.,0.]
service=PolicyIngestor(root=sys.argv[1],settings=settings,embeddings_factory=lambda _:emb)
management=PolicyManagement(ingestor_factory=lambda:service,documents=service.documents,settings=settings)
retriever=PolicyRetriever(root=sys.argv[1],settings=settings,embeddings_factory=lambda _:emb)
def query():
    try:
        retriever.initialize()
        return retriever.retrieve('Leave?')
    finally:
        retriever.close()
with TestClient(create_app(policy_management=management)) as client:
    headers={'X-Filename':'rules.txt','Content-Type':'text/plain'}
    response=client.post('/api/policy/documents',content=b'Old leave rules',headers=headers)
    assert response.status_code==201,response.text
    url='/api/policy/documents/'+response.json()['id']
    assert query()[0].text=='Old leave rules'
    assert client.put(url,content=b'New leave rules',headers=headers).status_code==200
    assert [r.text for r in query()]==['New leave rules']
    assert client.delete(url).status_code==204
    assert query()==[]
'''
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run([sys.executable,'-c',code,folder],capture_output=True,text=True,timeout=90)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__ == '__main__':
    unittest.main()
