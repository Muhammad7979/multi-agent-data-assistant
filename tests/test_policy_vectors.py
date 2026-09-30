"""Real local Chroma with deterministic vectors; no embedding/provider calls.

Run persistent clients in child processes to verify restart persistence and isolate
native resources, without using Chroma's private shutdown APIs.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

from data_agent.config import policy_chroma_path
from data_agent.services.policy_vectors import PolicyVectorStore


PRELUDE = '''
import sys
from unittest.mock import patch
from data_agent.services.policy_vectors import PolicyVectorStore
from uuid import uuid4
store = PolicyVectorStore(path=sys.argv[1], embedding_model="fake-v1", embedding_dimensions=3)
store.initialize()
doc = "11111111-1111-4111-8111-111111111111"
gen = "22222222-2222-4222-8222-222222222222"
other = "33333333-3333-4333-8333-333333333333"
chunks = [{"text": "Leave rules", "embedding": [1, 0, 0], "page": 2, "section": "Leave"},
          {"text": "Remote work", "embedding": [0, 1, 0]}]
'''


class PolicyVectorTests(unittest.TestCase):
    def run_code(self, path, code):
        result = subprocess.run([sys.executable, "-c", PRELUDE + textwrap.dedent(code) + "\nstore.close()\n", str(path)],
                                capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_explicit_initialization_and_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve() / "not-created"
            with patch.dict(os.environ, {"POLICY_STORAGE_ROOT": str(root)}):
                store = PolicyVectorStore(embedding_model="fake", embedding_dimensions=3)
                self.assertEqual(store.path, root / "chroma")
                self.assertFalse(root.exists())
                with self.assertRaises(RuntimeError):
                    store.count()
                self.assertFalse(root.exists())
            with patch.dict(os.environ, {"POLICY_STORAGE_ROOT": ""}), \
                    patch("data_agent.config.default_data_root", return_value=Path(folder).resolve()):
                self.assertEqual(policy_chroma_path(), Path(folder).resolve() / "var/policy/chroma")

    def test_empty_collection_and_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            self.run_code(folder, '''
                store.initialize()
                assert store.count() == 0
                assert store.get_chunks() == []
                assert store.query([1, 0, 0]) == []
                store.close()
                store.close()
                store.initialize()
                assert store.count() == 0
                store.delete_document_chunks(doc)
                assert store.count() == 0
                for model, dimensions in [("wrong", 3), ("fake-v1", 2)]:
                    try:
                        PolicyVectorStore(path=sys.argv[1], embedding_model=model,
                                          embedding_dimensions=dimensions).initialize()
                    except ValueError:
                        pass
                    else:
                        raise AssertionError("Incompatible collection accepted")
            ''')

    def test_add_metadata_filter_query_and_persistence(self):
        with tempfile.TemporaryDirectory() as folder:
            self.run_code(folder, '''
                ids = store.add_chunks(doc, gen, filename="handbook.txt", chunks=chunks)
                assert ids == [f"{doc}:{gen}:0", f"{doc}:{gen}:1"]
                store.add_chunks(doc, gen, filename="handbook.txt", chunks=chunks)
                store.add_chunks(other, gen, filename="handbook.txt", chunks=chunks[:1])
                assert store.count() == 3
                records = store.get_chunks(document_id=doc)
                assert len(records) == 2
                first = next(r for r in records if r["metadata"]["chunk_index"] == 0)
                assert first["embedding"] == [1, 0, 0]
                assert first["metadata"]["page"] == 2
                assert first["metadata"]["section"] == "Leave"
                assert first["text"] == "Leave rules"
                second = next(r for r in records if r["metadata"]["chunk_index"] == 1)
                assert "page" not in second["metadata"]
                result = store.query([1, 0, 0], document_id=doc, generation_ids=[gen], top_k=2)
                assert result[0]["id"] == ids[0]
                assert abs(result[0]["distance"]) < 0.00001
                assert store.query([1, 0, 0], generation_ids=[]) == []
                assert store.query([1, 0, 0], generation_ids=[str(uuid4())]) == []
            ''')
            # A fresh process opens the same persistent collection.
            self.run_code(folder, '''
                assert store.count() == 3
                assert len(store.get_chunks(document_id=doc)) == 2
                assert store.query([0, 1, 0], document_id=doc)[0]["text"] == "Remote work"
            ''')

    def test_replace_and_document_deletion(self):
        with tempfile.TemporaryDirectory() as folder:
            self.run_code(folder, '''
                store.add_chunks(doc, gen, filename="same.txt", chunks=chunks)
                store.add_chunks(other, gen, filename="same.txt", chunks=chunks)
                fresh = str(uuid4())
                replacement = [{"text": "New policy", "embedding": [0, 0, 1]}]
                store.replace_document_chunks(doc, fresh, filename="new.txt", chunks=replacement)
                records = store.get_chunks(document_id=doc)
                assert len(records) == 1
                assert records[0]["metadata"]["generation_id"] == fresh
                assert records[0]["text"] == "New policy"
                assert len(store.get_chunks(document_id=other)) == 2
                assert store.get_chunks(document_id=doc, generation_id=gen) == []
                store.delete_document_chunks(doc)
                assert store.get_chunks(document_id=doc) == []
                assert store.count() == 2
                store.delete_generation(other, gen)
                assert store.count() == 0
            ''')

    def test_validation_and_failed_replace_preserve_old_chunks(self):
        with tempfile.TemporaryDirectory() as folder:
            self.run_code(folder, '''
                store.add_chunks(doc, gen, filename="handbook.txt", chunks=chunks)
                for bad in [[], [{"text": "", "embedding": [1,0,0]}],
                            [{"text": "x", "embedding": [1,0]}],
                            [{"text": "x", "embedding": [True,0,0]}],
                            [{"text": "x", "embedding": [float("nan"),0,0]}],
                            [{"text": "x", "embedding": [0,0,0]}],
                            [{"text": "x", "embedding": [1,0,0], "page": -1}]]:
                    try:
                        store.replace_document_chunks(doc, str(uuid4()), filename="x", chunks=bad)
                    except ValueError:
                        pass
                    else:
                        raise AssertionError("Invalid chunks accepted")
                    assert store.count() == 2
                try:
                    store.replace_document_chunks(doc, gen, filename="x", chunks=chunks)
                except ValueError:
                    pass
                else:
                    raise AssertionError("Reused replacement generation accepted")
                with patch.object(store, "_upsert", side_effect=RuntimeError("simulated write failure")):
                    try:
                        store.replace_document_chunks(doc, str(uuid4()), filename="x", chunks=chunks)
                    except RuntimeError:
                        pass
                assert store.count() == 2
                assert len(store.get_chunks(document_id=doc, generation_id=gen)) == 2
                staged = str(uuid4())
                original_upsert = store._upsert
                def partial_write(records):
                    original_upsert(records[:1])
                    raise RuntimeError("simulated interruption after a partial write")
                with patch.object(store, "_upsert", side_effect=partial_write):
                    try:
                        store.replace_document_chunks(doc, staged, filename="x", chunks=chunks)
                    except RuntimeError:
                        pass
                    else:
                        raise AssertionError("Expected write failure")
                assert store.count() == 3
                assert len(store.get_chunks(document_id=doc, generation_id=gen)) == 2
                assert len(store.query([1,0,0], generation_ids=[gen])) == 2
                store.delete_generation(doc, staged)
                assert store.count() == 2
            ''')


if __name__ == "__main__":
    unittest.main()
