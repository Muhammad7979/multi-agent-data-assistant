"""Controlled query vectors, real Chroma ranking, no paid provider calls."""
from dataclasses import asdict
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from data_agent.config import PolicyIngestionSettings, policy_retrieval_top_k
from data_agent.services.policy_retrieval import PolicyRetriever


class PolicyRetrievalTests(unittest.TestCase):
    def test_configuration_and_no_constructor_io(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'absent'
            PolicyRetriever(root=root)
            self.assertFalse(root.exists())
        with patch.dict(os.environ, {'POLICY_RETRIEVAL_TOP_K': '7'}):
            self.assertEqual(policy_retrieval_top_k(), 7)
        for value in (0, 101, True, '5'):
            with self.assertRaises(ValueError):
                PolicyRetriever(top_k=value)

    def test_metadata_and_no_embedding_in_contract(self):
        doc, gen = str(uuid4()), str(uuid4())
        record = dict(id=f'{doc}:{gen}:0', text='Leave rules', distance=0.1,
                      metadata=dict(document_id=doc, generation_id=gen, filename='a.pdf',
                                    chunk_index=0, page=2, section='Leave'))
        match = PolicyRetriever._match(record, {gen})
        self.assertEqual(match.page, 2)
        self.assertEqual(match.section, 'Leave')
        self.assertNotIn('embedding', asdict(match))
        self.assertIsNone(PolicyRetriever._match(record, set()))
        for metadata in (None, {}, {'document_id': 'bad'}):
            self.assertIsNone(PolicyRetriever._match({**record, 'metadata': metadata}, {gen}))
        self.assertIsNone(PolicyRetriever._match({**record, 'distance': float('nan')}, {gen}))
        record['metadata'].update(page='invented', section=[])
        match = PolicyRetriever._match(record, {gen})
        self.assertIsNone(match.page)
        self.assertIsNone(match.section)

    def test_empty_validation_failures_and_same_embedding_settings(self):
        settings = PolicyIngestionSettings()
        factory = Mock()
        service = PolicyRetriever(settings=settings, embeddings_factory=factory)
        service._initialized = True
        service.documents = Mock()
        service.vectors = Mock()
        service.documents.active_generation_ids.return_value = []
        self.assertEqual(service.retrieve('Leave?'), [])
        factory.assert_not_called()
        for question in ('', '  ', None, 'word ' * 9000):
            with self.assertRaises(ValueError):
                service.retrieve(question)
        gen = str(uuid4())
        service.documents.active_generation_ids.return_value = [gen]
        service.vectors.count.return_value = 1
        service.vectors.query.return_value = []
        factory.return_value.embed_query.return_value = [1, 0, 0]
        self.assertEqual(service.retrieve('Leave?'), [])
        factory.assert_called_once_with(settings)
        service.vectors.query.assert_called_once_with([1, 0, 0], top_k=5, generation_ids=[gen])
        factory.return_value.embed_query.side_effect = RuntimeError('Provider failed')
        with self.assertRaises(RuntimeError):
            service.retrieve('Leave?')

    def test_real_ranking_top_k_delete_replace_and_incompatible_configuration(self):
        code = '''
import sys
from dataclasses import replace
from unittest.mock import Mock
from data_agent.config import PolicyIngestionSettings
from data_agent.services.policy_ingestion import PolicyIngestor
from data_agent.services.policy_retrieval import PolicyRetriever
settings=PolicyIngestionSettings(embedding_model='controlled', embedding_dimensions=3)
embedding=Mock()
embedding.embed_documents.side_effect=lambda texts: [[1.,0.,0.] if 'leave' in t.lower() else [0.,1.,0.] for t in texts]
embedding.embed_query.return_value=[1.,0.,0.]
factory=lambda _:embedding
ingestor=PolicyIngestor(root=sys.argv[1],settings=settings,embeddings_factory=factory)
ingestor.initialize()
a=ingestor.ingest(filename='leave.txt',content=b'Annual leave entitlement',media_type='text/plain')
b=ingestor.ingest(filename='office.txt',content=b'Office parking',media_type='text/plain')
assert a['status']==b['status']=='ready'
ingestor.close()
r=PolicyRetriever(root=sys.argv[1],settings=settings,embeddings_factory=factory)
r.initialize()
matches=r.retrieve('Leave?')
assert len(matches)==2
assert matches[0].document_id==a['id'] and matches[1].document_id==b['id']
assert abs(matches[0].distance)<0.0001 and abs(matches[1].distance-1)<0.0001
r.top_k=1
assert len(r.retrieve('Leave?'))==1
r.close()
ingestor.initialize()
new=ingestor.ingest(filename='leave.txt',content=b'Updated leave entitlement',media_type='text/plain',document_id=a['id'])
assert new['status']=='ready'
ingestor.vectors.delete_document_chunks(b['id'])
ingestor.close()
r.initialize()
matches=r.retrieve('Leave?')
assert len(matches)==1 and matches[0].text=='Updated leave entitlement'
assert matches[0].generation_id!=a['active_generation_id']
r.vectors.delete_document_chunks(a['id'])
assert r.retrieve('Leave?')==[]
r.close()
bad=PolicyRetriever(root=sys.argv[1],settings=replace(settings,embedding_model='incompatible'),embeddings_factory=factory)
try:
    bad.initialize()
except ValueError:
    pass
else:
    raise AssertionError('Incompatible model accepted')
'''
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run([sys.executable, '-c', code, folder],
                                    capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
