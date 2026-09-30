"""Document management using existing ingestion and public vector-store services."""
from contextlib import contextmanager

from data_agent.config import policy_chroma_path, policy_ingestion_settings
from data_agent.services.policy_documents import PolicyDocuments
from data_agent.services.policy_ingestion import PolicyIngestor
from data_agent.services.policy_extraction import PolicyInputError
from data_agent.services.policy_runtime import policy_operation_lock


class PolicyManagementError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)


class PolicyManagement:
    def __init__(self, *, ingestor_factory=PolicyIngestor, documents=None, settings=None):
        self.ingestor_factory = ingestor_factory
        self.documents = documents
        self.settings = settings

    def metadata(self):
        # Resolve environment at request time, after application startup loading.
        documents = self.documents or PolicyDocuments(policy_chroma_path().parent / 'metadata.sqlite3')
        documents.initialize()
        return documents

    @property
    def max_file_bytes(self):
        return (self.settings or policy_ingestion_settings()).max_file_bytes

    @staticmethod
    def public(document):
        latest = document['generations'][-1]
        active = next((g for g in document['generations'] if g['id'] == document['active_generation_id']), None)
        return dict(id=document['id'], name=latest['filename'], type=latest['media_type'],
                    status=document['status'], created_at=document['created_at'], updated_at=document['updated_at'],
                    size_bytes=latest['size_bytes'], chunk_count=active['chunk_count'] if active else 0,
                    has_indexed_version=active is not None, error_code=document['error_code'])

    def get(self, document_id):
        document = self.metadata().get(document_id)
        if document is None:
            raise PolicyManagementError(404, 'DOCUMENT_NOT_FOUND', 'This policy document is not available.')
        return self.public(document)

    def list(self, limit, offset):
        metadata = self.metadata()
        # A deletion can finish between listing IDs and reading their metadata.
        rows = [metadata.get(key) for key in metadata.list_ids(limit + 1, offset)]
        rows = [row for row in rows if row is not None]
        return dict(documents=[self.public(row) for row in rows[:limit]],
                    page=dict(limit=limit, offset=offset, has_more=len(rows) > limit))

    @contextmanager
    def writer(self):
        with policy_operation_lock:
            service = self.ingestor_factory()
            try:
                service.initialize()
                yield service
            finally:
                service.close()

    def upload(self, filename, content, media_type, document_id=None):
        with self.writer() as service:
            if document_id is not None:
                existing = service.documents.get(document_id)
                if existing is None:
                    raise PolicyManagementError(404, 'DOCUMENT_NOT_FOUND', 'This policy document is not available.')
                if existing['status'] in ('pending', 'processing') or existing['error_code'] == 'DELETE_PENDING':
                    raise PolicyManagementError(409, 'DOCUMENT_BUSY', 'Document processing or deletion requires completion first.')
            try:
                document = service.ingest(filename=filename, content=content, media_type=media_type, document_id=document_id)
            except PolicyInputError as exc:
                status = 413 if exc.code == 'FILE_TOO_LARGE' else 415 if exc.code in ('UNSUPPORTED_TYPE', 'TYPE_MISMATCH') else 400
                raise PolicyManagementError(status, exc.code, 'The policy file is invalid or unsupported.') from None
            return self.public(document)

    def delete(self, document_id):
        with self.writer() as service:
            document = service.documents.get(document_id)
            if document is None:
                raise PolicyManagementError(404, 'DOCUMENT_NOT_FOUND', 'This policy document is not available.')
            # Keep metadata and original IDs until all cleanup succeeds, so DELETE is retryable.
            service.delete_document(document_id)
