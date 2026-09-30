"""Local Chroma boundary for supplied policy vectors; no parsing or provider calls.

One owning service/process per directory. Call initialize() explicitly. Document
activation belongs to the application metadata layer, not to this vector collection.
"""
import math
from pathlib import Path
from threading import RLock
from uuid import UUID

from data_agent.config import policy_chroma_path


COLLECTION_NAME = "company_policy_chunks_v1"


def _uuid(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        raise ValueError("Document and generation IDs must be UUIDs") from None


class PolicyVectorStore:
    def __init__(self, *, embedding_model: str, embedding_dimensions: int,
                 chunking_version: str = "v1", path=None):
        if not isinstance(embedding_model, str) or not embedding_model.strip():
            raise ValueError("Embedding model is required")
        if type(embedding_dimensions) is not int or embedding_dimensions < 1:
            raise ValueError("Embedding dimensions must be a positive integer")
        if not isinstance(chunking_version, str) or not chunking_version.strip():
            raise ValueError("Chunking version is required")
        self.path = Path(path).expanduser().resolve() if path is not None else policy_chroma_path()
        self._metadata = {"embedding_model": embedding_model,
                          "embedding_dimensions": embedding_dimensions,
                          "chunking_version": chunking_version}
        self._client = None
        self._collection = None
        self._lock = RLock()

    def initialize(self):
        """Open/create the collection using public Chroma APIs only."""
        import chromadb
        from chromadb.config import Settings

        with self._lock:
            if self._collection is not None:
                return
            client = chromadb.PersistentClient(path=str(self.path),
                settings=Settings(anonymized_telemetry=False))
            try:
                collection = client.get_or_create_collection(
                    name=COLLECTION_NAME, embedding_function=None,
                    metadata=self._metadata, configuration={"hnsw": {"space": "cosine"}})
                if any((collection.metadata or {}).get(k) != v for k, v in self._metadata.items()):
                    raise ValueError("Policy collection embedding/chunking configuration mismatch")
                if collection.configuration.get("hnsw", {}).get("space") != "cosine":
                    raise ValueError("Policy collection must use cosine distance")
            except Exception:
                client.close()
                raise
            self._client, self._collection = client, collection

    def close(self):
        """Release the owning client's resources through Chroma's public API."""
        with self._lock:
            if self._client is not None:
                self._client.close()
                self._client = self._collection = None

    def _ready(self):
        if self._collection is None:
            raise RuntimeError("Initialize policy vector storage before use")
        return self._collection

    def _vector(self, vector):
        if not isinstance(vector, (list, tuple)) or len(vector) != self._metadata["embedding_dimensions"]:
            raise ValueError("Embedding dimension mismatch")
        try:
            if any(type(v) not in (int, float) for v in vector):
                raise ValueError()
            result = [float(v) for v in vector]
            if not all(math.isfinite(v) for v in result) or not any(result):
                raise ValueError()
        except (ValueError, OverflowError):
            raise ValueError("Embedding must contain finite numbers and be nonzero") from None
        return result

    @staticmethod
    def _where(document_id=None, generation_id=None):
        clauses = []
        if document_id is not None:
            clauses.append({"document_id": _uuid(document_id)})
        if generation_id is not None:
            clauses.append({"generation_id": _uuid(generation_id)})
        return {"$and": clauses} if len(clauses) > 1 else clauses[0] if clauses else None

    def _prepare(self, document_id, generation_id, filename, chunks):
        document_id, generation_id = _uuid(document_id), _uuid(generation_id)
        if not isinstance(filename, str) or not filename.strip():
            raise ValueError("Source filename is required")
        records = []
        for index, chunk in enumerate(chunks):
            text = chunk.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ValueError("Chunk text must be nonempty")
            metadata = {"document_id": document_id, "generation_id": generation_id,
                        "filename": filename, "chunk_index": index}
            if chunk.get("page") is not None:
                if type(chunk["page"]) is not int or chunk["page"] < 1:
                    raise ValueError("Page must be a positive integer")
                metadata["page"] = chunk["page"]
            if chunk.get("section") is not None:
                if not isinstance(chunk["section"], str) or not chunk["section"].strip():
                    raise ValueError("Section must be nonempty text")
                metadata["section"] = chunk["section"]
            records.append((f"{document_id}:{generation_id}:{index}", text,
                            self._vector(chunk["embedding"]), metadata))
        if not records:
            raise ValueError("At least one chunk is required")
        return records

    def _upsert(self, records):
        collection = self._ready()
        batch_size = self._client.get_max_batch_size()
        for start in range(0, len(records), batch_size):
            batch = records[start:start + batch_size]
            collection.upsert(ids=[r[0] for r in batch], documents=[r[1] for r in batch],
                              embeddings=[r[2] for r in batch], metadatas=[r[3] for r in batch])

    def add_chunks(self, document_id, generation_id, *, filename, chunks):
        """Upsert a complete supplied batch; identical IDs make retries idempotent.

        This does not remove other records or mark a generation active. A failed
        multi-batch write may leave staged chunks; delete_generation() cleans them.
        """
        records = self._prepare(document_id, generation_id, filename, chunks)
        with self._lock:
            self._upsert(records)
        return [r[0] for r in records]

    def get_chunks(self, *, document_id=None, generation_id=None, limit=100, offset=0):
        if type(limit) is not int or not 1 <= limit <= 1000 or type(offset) is not int or offset < 0:
            raise ValueError("Invalid chunk pagination")
        with self._lock:
            result = self._ready().get(where=self._where(document_id, generation_id),
                limit=limit, offset=offset, include=["documents", "metadatas", "embeddings"])
            return [{"id": key, "text": result["documents"][i], "metadata": result["metadatas"][i],
                     "embedding": result["embeddings"][i].tolist()}
                    for i, key in enumerate(result["ids"])]

    def count(self):
        with self._lock:
            return self._ready().count()

    def delete_document_chunks(self, document_id):
        with self._lock:
            self._ready().delete(where=self._where(document_id))

    def delete_generation(self, document_id, generation_id):
        with self._lock:
            self._ready().delete(where=self._where(document_id, generation_id))

    def replace_document_chunks(self, document_id, generation_id, *, filename, chunks):
        """Write a fresh generation before deleting older document generations.

        Not a cross-call transaction: an interruption can leave both generations.
        Document lifecycle code stages with add_chunks(), activates in
        metadata, and then delete_generation(). Never run concurrent owners.
        """
        document_id, generation_id = _uuid(document_id), _uuid(generation_id)
        records = self._prepare(document_id, generation_id, filename, chunks)
        with self._lock:
            collection = self._ready()
            if collection.get(where=self._where(document_id, generation_id), limit=1)["ids"]:
                raise ValueError("Replacement requires a fresh generation ID")
            self._upsert(records)  # Failure leaves old records intact.
            collection.delete(where={"$and": [{"document_id": document_id},
                                               {"generation_id": {"$ne": generation_id}}]})
        return [r[0] for r in records]

    def query(self, embedding, *, top_k=5, document_id=None, generation_ids=None):
        """Return cosine distances, not confidence scores; no Python similarity scan.

        The document layer supplies active generation_ids. Omitting them
        searches all stored generations, including staged ones.
        """
        vector = self._vector(embedding)
        if type(top_k) is not int or not 1 <= top_k <= 100:
            raise ValueError("Invalid result count")
        where = self._where(document_id)
        if generation_ids is not None:
            ids = [_uuid(value) for value in generation_ids]
            if not ids:
                self._ready()
                return []
            generations = {"generation_id": {"$in": ids}}
            where = {"$and": [where, generations]} if where else generations
        with self._lock:
            collection = self._ready()
            count = collection.count()
            if not count:
                return []
            result = collection.query(query_embeddings=[vector], n_results=min(top_k, count),
                where=where, include=["documents", "metadatas", "distances"])
            return [{"id": key, "text": result["documents"][0][i],
                     "metadata": result["metadatas"][0][i], "distance": result["distances"][0][i]}
                    for i, key in enumerate(result["ids"][0])]
