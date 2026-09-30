"""Synchronous Company Policy indexing, independent of agents and HTTP uploads."""
from hashlib import sha256
from pathlib import Path
from threading import RLock
from uuid import UUID

from data_agent.config import policy_chroma_path, policy_ingestion_settings
from data_agent.llm import create_embeddings
from data_agent.services.policy_documents import PolicyDocuments
from data_agent.services.policy_extraction import PolicyInputError, validate_document, extract_text, chunk_text
from data_agent.services.policy_vectors import PolicyVectorStore


class PolicyIngestor:
    """One owning process per policy root. Constructing this service performs no IO.

    Call initialize(), then ingest(filename=..., content=bytes, media_type=...).
    Pass document_id to replace. Failures after validation return persisted failed
    status; invalid uploads raise PolicyInputError without creating records.
    """
    def __init__(self, *, root=None, settings=None, embeddings_factory=create_embeddings, vectors=None):
        self.settings = settings or policy_ingestion_settings()
        self.root = Path(root).expanduser().resolve() if root is not None else policy_chroma_path().parent
        self.documents = PolicyDocuments(self.root / 'metadata.sqlite3')
        self.vectors = vectors or PolicyVectorStore(path=self.root / 'chroma',
            embedding_model=self.settings.embedding_model, embedding_dimensions=self.settings.embedding_dimensions,
            chunking_version=self.settings.chunking_version)
        self.embeddings_factory = embeddings_factory
        self._lock = RLock()
        self._initialized = False

    def initialize(self):
        with self._lock:
            self.vectors.initialize()
            self.documents.initialize()
            (self.root / 'originals').mkdir(parents=True, exist_ok=True)
            self._initialized = True

    def close(self):
        self.vectors.close()
        self._initialized = False

    def _original(self, generation):
        # No user-provided path or filename is used for filesystem access.
        path = self.root / 'originals' / str(UUID(generation))
        if path.resolve().parent != (self.root / 'originals').resolve():
            raise ValueError('Unsafe original file location')
        return path

    def _cleanup(self, document_id):
        document = self.documents.get(document_id)
        for generation in document['generations']:
            if generation['cleanup_pending'] and generation['id'] != document['active_generation_id']:
                self.vectors.delete_generation(document_id, generation['id'])
                self._original(generation['id']).unlink(missing_ok=True)
                self.documents.cleanup_done(generation['id'])

    def recover_document(self, document_id):
        """Explicit recovery after interruption, only when no ingestion is running.

        Inactive incomplete generations are discarded. A verified active generation
        is retained; interrupted cleanup is retried. No provider calls are made.
        """
        with self._lock:
            if not self._initialized:
                raise RuntimeError('Initialize ingestion first')
            document = self.documents.get(document_id)
            if document is None:
                raise KeyError('Document not found')
            for generation in document['generations']:
                if generation['status'] in ('pending', 'processing'):
                    self.documents.fail(document_id, generation['id'], 'INDEXING_INTERRUPTED')
            self._cleanup(document_id)
            if document['active_generation_id']:
                self.documents.finish(document_id)
            return self.documents.get(document_id)

    def delete_document(self, document_id):
        with self._lock:
            if not self._initialized:
                raise RuntimeError('Initialize ingestion first')
            document = self.documents.get(document_id)
            if document is None:
                raise KeyError('Document not found')
            self.documents.deactivate_for_delete(document_id)
            self.vectors.delete_document_chunks(document_id)
            for generation in document['generations']:
                self._original(generation['id']).unlink(missing_ok=True)
            self.documents.delete(document_id)

    def ingest(self, *, filename, content, media_type, document_id=None):
        with self._lock:
            if not self._initialized:
                raise RuntimeError('Initialize ingestion first')
            extension = validate_document(filename, content, media_type, self.settings)
            document_id, generation = self.documents.begin(document_id, filename, media_type,
                                                           sha256(content).hexdigest(), len(content))
            stage = 'STORAGE_FAILED'
            try:
                self.documents.processing(document_id, generation)
                with self._original(generation).open('xb') as original:
                    original.write(content)
                stage = 'PARSING_FAILED'
                segments = extract_text(content, extension, self.settings)
                stage = 'CHUNKING_FAILED'
                chunks = chunk_text(segments, self.settings)
                stage = 'EMBEDDING_FAILED'
                embeddings = self.embeddings_factory(self.settings)
                size = self.settings.embedding_batch_size
                for start in range(0, len(chunks), size):
                    batch = chunks[start:start + size]
                    vectors = embeddings.embed_documents([chunk['text'] for chunk in batch])
                    if len(vectors) != len(batch):
                        raise ValueError('Embedding count mismatch')
                    for chunk, vector in zip(batch, vectors):
                        chunk['embedding'] = vector
                stage = 'INDEXING_FAILED'
                expected = self.vectors.add_chunks(document_id, generation, filename=filename, chunks=chunks)
                actual = []
                for offset in range(0, len(expected) + 1, 100):
                    actual.extend(record['id'] for record in self.vectors.get_chunks(
                        document_id=document_id, generation_id=generation, limit=100, offset=offset))
                if len(expected) != len(chunks) or set(actual) != set(expected) or len(actual) != len(expected):
                    raise ValueError('Index verification failed')
                stage = 'ACTIVATION_FAILED'
                self.documents.activate(document_id, generation, len(chunks))
                stage = 'CLEANUP_FAILED'
                self._cleanup(document_id)
                self.documents.finish(document_id)
            except Exception as exc:
                code = exc.code if isinstance(exc, PolicyInputError) else stage
                self.documents.fail(document_id, generation, code)
                # Cleanup is best effort; durable flags retain work for recovery.
                try:
                    self._cleanup(document_id)
                except Exception:
                    pass
            return self.documents.get(document_id)
