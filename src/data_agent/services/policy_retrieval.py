"""Policy evidence retrieval only; no answer generation or agent routing."""
from dataclasses import dataclass
import math
from pathlib import Path
from uuid import UUID

from data_agent.config import policy_chroma_path, policy_ingestion_settings, policy_retrieval_top_k
from data_agent.llm import create_embeddings
from data_agent.services.policy_documents import PolicyDocuments
from data_agent.services.policy_vectors import PolicyVectorStore


@dataclass(frozen=True)
class PolicyMatch:
    chunk_id: str
    text: str
    document_id: str
    generation_id: str
    filename: str
    chunk_index: int
    distance: float
    page: int | None = None
    section: str | None = None


class PolicyRetriever:
    """Explicit lifecycle, same configuration as ingestion, active versions only.

    Results are nearest candidates, not a claim that evidence answers the question.
    Provider/storage failures propagate; they are never disguised as empty results.
    Use the existing single-owner/idle-ingestion persistence boundary.
    """
    def __init__(self, *, root=None, settings=None, top_k=None, embeddings_factory=create_embeddings):
        self.settings = settings or policy_ingestion_settings()
        self.top_k = policy_retrieval_top_k() if top_k is None else top_k
        if type(self.top_k) is not int or not 1 <= self.top_k <= 100:
            raise ValueError('Invalid retrieval count')
        root = Path(root).expanduser().resolve() if root is not None else policy_chroma_path().parent
        self.documents = PolicyDocuments(root / 'metadata.sqlite3')
        self.vectors = PolicyVectorStore(path=root / 'chroma',
            embedding_model=self.settings.embedding_model,
            embedding_dimensions=self.settings.embedding_dimensions,
            chunking_version=self.settings.chunking_version)
        self.embeddings_factory = embeddings_factory
        self._initialized = False

    def initialize(self):
        self.vectors.initialize()  # Rejects incompatible model/dimensions/metric.
        try:
            self.documents.initialize()
        except Exception:
            self.vectors.close()
            raise
        self._initialized = True

    def close(self):
        self.vectors.close()
        self._initialized = False

    @staticmethod
    def _match(record, active):
        try:
            metadata = record['metadata']
            document = str(UUID(metadata['document_id']))
            generation = str(UUID(metadata['generation_id']))
            index = metadata['chunk_index']
            filename, text = metadata['filename'], record['text']
            distance = record['distance']
            if (generation not in active or type(index) is not int or index < 0
                    or record['id'] != f'{document}:{generation}:{index}'
                    or not isinstance(filename, str) or not filename.strip()
                    or not isinstance(text, str) or not text.strip()
                    or type(distance) not in (int, float) or not math.isfinite(distance)):
                return None
            page, section = metadata.get('page'), metadata.get('section')
            # Invalid optional attribution is omitted, never fabricated.
            if type(page) is not int or page < 1:
                page = None
            if not isinstance(section, str) or not section.strip():
                section = None
            return PolicyMatch(record['id'], text, document, generation, filename,
                               index, float(distance), page, section)
        except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
            return None

    def retrieve(self, question: str) -> list[PolicyMatch]:
        if not self._initialized:
            raise RuntimeError('Initialize policy retrieval first')
        if not isinstance(question, str) or not question.strip():
            raise ValueError('Policy question must be nonempty text')
        import tiktoken
        if len(tiktoken.get_encoding(self.settings.encoding_name).encode(
                question, disallowed_special=())) > 8000:
            raise ValueError('Policy question exceeds embedding token limit')
        active = self.documents.active_generation_ids()
        if not active or not self.vectors.count():
            return []
        embedding = self.embeddings_factory(self.settings).embed_query(question.strip())
        records = self.vectors.query(embedding, top_k=self.top_k, generation_ids=active)
        # Recheck activation after querying to discard versions superseded meanwhile.
        active = set(self.documents.active_generation_ids())
        matches = [match for record in records if (match := self._match(record, active)) is not None]
        return sorted(matches, key=lambda match: match.distance)[:self.top_k]
