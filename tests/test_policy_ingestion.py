"""Policy indexing tests use fake embeddings, never paid provider calls."""
from dataclasses import replace
from io import BytesIO
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from data_agent.config import PolicyIngestionSettings
from data_agent.llm import create_embeddings
from data_agent.services.policy_extraction import PolicyInputError, validate_document, extract_text, chunk_text
from data_agent.services.policy_ingestion import PolicyIngestor


class FakeVectors:
    def __init__(self):
        self.records = {}
        self.fail = False
        self.fail_delete = False

    def initialize(self): pass
    def close(self): pass

    def add_chunks(self, doc, gen, *, filename, chunks):
        ids = []
        for i, chunk in enumerate(chunks):
            key = f'{doc}:{gen}:{i}'
            self.records[key] = {'id': key, 'text': chunk['text'], 'doc': doc, 'gen': gen,
                                 'metadata': {'filename': filename, 'chunk_index': i,
                                              **{k: chunk[k] for k in ('page','section') if k in chunk}}}
            ids.append(key)
            if self.fail:
                raise RuntimeError('private vector error')
        return ids

    def get_chunks(self, *, document_id, generation_id, limit=100, offset=0):
        return [v for v in self.records.values() if v['doc'] == document_id and v['gen'] == generation_id][offset:offset+limit]

    def delete_generation(self, doc, gen):
        if self.fail_delete:
            raise RuntimeError('private deletion error')
        self.records = {k:v for k,v in self.records.items() if not(v['doc']==doc and v['gen']==gen)}


class PolicyIngestionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = PolicyIngestionSettings(embedding_model='fake', embedding_dimensions=3,
                                               chunk_tokens=30, overlap_tokens=5, embedding_batch_size=2)
        self.embeddings = Mock()
        self.embeddings.embed_documents.side_effect = lambda texts: [[1.,0.,0.] for _ in texts]
        self.factory = Mock(return_value=self.embeddings)
        self.vectors = FakeVectors()
        self.service = PolicyIngestor(root=Path(self.temp.name)/'policy', settings=self.settings,
                                     vectors=self.vectors, embeddings_factory=self.factory)
        self.service.initialize()

    def ingest(self, content=b'# Leave\n\nAnnual leave rules.\n\n## Work\n\nRemote work rules.', **kwargs):
        return self.service.ingest(filename='handbook.md', content=content, media_type='text/markdown', **kwargs)

    def test_valid_metadata_and_batched_embeddings(self):
        document = self.ingest(content=('# Leave\n\n' + 'Numbered rules apply to employees.\n\n'*40).encode())
        self.assertEqual(document['status'], 'ready')
        generation = document['generations'][0]
        self.assertGreater(generation['chunk_count'], 2)
        self.assertEqual(self.service.documents.active_generation_ids(), [generation['id']])
        self.assertTrue(all(1 <= len(c.args[0]) <= 2 for c in self.embeddings.embed_documents.call_args_list))
        self.assertTrue(any(len(c.args[0]) == 2 for c in self.embeddings.embed_documents.call_args_list))
        self.assertTrue(all(r['metadata']['section']=='Leave' for r in self.vectors.records.values()))
        self.assertTrue(all('page' not in r['metadata'] for r in self.vectors.records.values()))
        self.assertEqual((self.service.root/'originals'/generation['id']).read_bytes(),
                         ('# Leave\n\n' + 'Numbered rules apply to employees.\n\n'*40).encode())

    def test_invalid_uploads(self):
        cases = [('x.docx',b'x','application/octet-stream'), ('x.txt',b'','text/plain'),
                 ('../x.txt',b'x','text/plain'), ('C:\\x.txt',b'x','text/plain'),
                 ('NUL.txt',b'x','text/plain'), ('x.pdf',b'not pdf','application/pdf'),
                 ('x.txt',b'x','application/pdf'), ('x\x00.txt',b'x','text/plain')]
        for filename, content, mime in cases:
            with self.subTest(filename=filename), self.assertRaises(PolicyInputError):
                self.service.ingest(filename=filename,content=content,media_type=mime)
        with self.assertRaises(PolicyInputError):
            validate_document('x.txt',b'abc','text/plain',replace(self.settings,max_file_bytes=2))
        self.factory.assert_not_called()

    def test_empty_and_bad_text_fail_without_provider(self):
        for content in [b'  \n',b'\xff',b'a\x00b']:
            result = self.ingest(content)
            self.assertEqual(result['status'],'failed')
            self.assertIsNone(result['active_generation_id'])
        self.factory.assert_not_called()

    def test_chunk_boundaries_and_limits(self):
        import tiktoken
        text = '# Leave\n\n' + 'Employees may request annual leave. '*50 + '\n## Work\n\nRemote work.\n```\n# Not a heading\n```'
        segments = extract_text(text.encode(),'.md',self.settings)
        self.assertEqual([s['section'] for s in segments],['Leave','Work'])
        chunks = chunk_text(segments,self.settings)
        encoder = tiktoken.get_encoding(self.settings.encoding_name)
        self.assertTrue(all(len(encoder.encode(c['text'])) <= 30 for c in chunks))
        self.assertTrue(all('page' not in c for c in chunks))
        with self.assertRaises(PolicyInputError):
            chunk_text(segments,replace(self.settings,max_chunks=1))

    def test_embedding_failure_preserves_old_generation(self):
        old = self.ingest()
        self.embeddings.embed_documents.side_effect = RuntimeError('secret provider error')
        failed = self.ingest(b'New rules',document_id=old['id'])
        self.assertEqual(failed['status'],'failed')
        self.assertEqual(failed['error_code'],'EMBEDDING_FAILED')
        self.assertEqual(failed['active_generation_id'],old['active_generation_id'])
        self.assertNotIn('secret',str(failed))

    def test_index_failure_cleans_partial_and_preserves_old(self):
        old = self.ingest()
        ids = set(self.vectors.records)
        self.vectors.fail = True
        failed = self.ingest(b'New rules',document_id=old['id'])
        self.assertEqual(failed['error_code'],'INDEXING_FAILED')
        self.assertEqual(set(self.vectors.records),ids)
        self.assertEqual(failed['active_generation_id'],old['active_generation_id'])

    def test_reindex_removes_stale_vectors(self):
        old = self.ingest()
        new = self.ingest(b'# Updated\n\nReplacement rules.',document_id=old['id'])
        self.assertEqual(new['status'],'ready')
        self.assertNotEqual(new['active_generation_id'],old['active_generation_id'])
        self.assertTrue(all(r['gen']==new['active_generation_id'] for r in self.vectors.records.values()))
        self.assertFalse((self.service.root/'originals'/old['active_generation_id']).exists())

    def test_cleanup_failure_and_explicit_recovery(self):
        old = self.ingest()
        self.vectors.fail_delete = True
        new = self.ingest(b'Changed rules',document_id=old['id'])
        self.assertEqual(new['status'],'failed')
        self.assertEqual(new['error_code'],'CLEANUP_FAILED')
        self.assertNotEqual(new['active_generation_id'],old['active_generation_id'])
        self.vectors.fail_delete = False
        recovered = self.service.recover_document(old['id'])
        self.assertEqual(recovered['status'],'ready')
        self.assertEqual({r['gen'] for r in self.vectors.records.values()},{recovered['active_generation_id']})

    def test_interrupted_processing_recovery(self):
        doc,gen = self.service.documents.begin(None,'x.txt','text/plain','hash',1)
        self.service.documents.processing(doc,gen)
        with self.assertRaises(ValueError):
            self.ingest(document_id=doc)
        recovered = self.service.recover_document(doc)
        self.assertEqual(recovered['status'],'failed')
        self.assertEqual(recovered['error_code'],'INDEXING_INTERRUPTED')

    def test_embedding_factory_reuses_configuration(self):
        with patch('langchain_openai.OpenAIEmbeddings') as constructor:
            create_embeddings(self.settings)
        kwargs = constructor.call_args.kwargs
        self.assertEqual(kwargs['model'],'fake')
        self.assertEqual(kwargs['dimensions'],3)
        self.assertNotIn('api_key',kwargs)

    def test_pdf_extraction_and_parse_failures(self):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        writer = PdfWriter()
        page = writer.add_blank_page(width=612,height=792)
        font = DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})})
        stream = DecodedStreamObject()
        stream.set_data(b'BT /F1 12 Tf 50 700 Td (Annual leave rules.) Tj ET')
        page[NameObject('/Contents')] = stream
        output = BytesIO()
        writer.write(output)
        result = self.service.ingest(filename='handbook.pdf',content=output.getvalue(),media_type='application/pdf')
        self.assertEqual(result['status'],'ready')
        self.assertEqual(next(iter(self.vectors.records.values()))['metadata']['page'],1)
        failed = self.service.ingest(filename='bad.pdf',content=b'%PDF-corrupt',media_type='application/pdf')
        self.assertEqual(failed['error_code'],'PARSING_FAILED')
        blank = PdfWriter(); blank.add_blank_page(width=100,height=100)
        output = BytesIO(); blank.write(output)
        failed = self.service.ingest(filename='scan.pdf',content=output.getvalue(),media_type='application/pdf')
        self.assertEqual(failed['error_code'],'NO_EXTRACTABLE_TEXT')

    def test_real_chroma_insert_and_reindex_with_mocked_openai(self):
        code = '''
from data_agent.services.policy_ingestion import PolicyIngestor
from data_agent.config import PolicyIngestionSettings
from unittest.mock import Mock
import sys
embeddings=Mock()
embeddings.embed_documents.side_effect=lambda texts:[[1.,0.,0.] for _ in texts]
settings=PolicyIngestionSettings(embedding_model='fake',embedding_dimensions=3)
service=PolicyIngestor(root=sys.argv[1],settings=settings,embeddings_factory=lambda _:embeddings)
try:
    service.initialize()
    old=service.ingest(filename='a.txt',content=b'Old leave rules',media_type='text/plain')
    assert old['status']=='ready', old
    new=service.ingest(filename='b.txt',content=b'New leave rules',media_type='text/plain',document_id=old['id'])
    assert new['status']=='ready', new
    assert service.vectors.get_chunks(document_id=old['id'],generation_id=old['active_generation_id'])==[]
    found=service.vectors.query([1,0,0],generation_ids=service.documents.active_generation_ids())
    assert len(found)==1 and found[0]['text']=='New leave rules'
finally:
    service.close()
'''
        result = subprocess.run([sys.executable,'-c',code,str(Path(self.temp.name)/'real')],capture_output=True,text=True,timeout=90)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__ == '__main__':
    unittest.main()
