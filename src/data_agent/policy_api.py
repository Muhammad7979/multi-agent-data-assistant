"""Policy document HTTP contracts; no agent routing or provider logic."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from data_agent.api_models import ErrorResponse, Page
from data_agent.services.policy_management import PolicyManagementError


class PolicyDocumentResponse(BaseModel):
    id: str
    name: str
    type: str
    status: Literal['pending', 'processing', 'ready', 'failed']
    created_at: str
    updated_at: str
    size_bytes: int
    chunk_count: int
    has_indexed_version: bool
    error_code: str | None


class PolicyDocumentList(BaseModel):
    documents: list[PolicyDocumentResponse]
    page: Page


class PolicyDocumentError(ErrorResponse):
    document: PolicyDocumentResponse | None = None


def policy_document_router(service):
    router = APIRouter(prefix='/api/policy/documents', tags=['Policy documents'])
    errors = {code: {'model': PolicyDocumentError} for code in (400, 404, 409, 413, 415, 503)}
    errors['4XX'] = {'model': ErrorResponse}

    async def call(method, *args):
        try:
            return await run_in_threadpool(method, *args)
        except PolicyManagementError:
            raise
        except Exception:
            raise PolicyManagementError(503, 'POLICY_STORAGE_UNAVAILABLE', 'Policy document storage is unavailable.') from None

    @router.get('', response_model=PolicyDocumentList, responses=errors)
    async def documents(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
        return await call(service.list, limit, offset)

    @router.get('/{document_id}', response_model=PolicyDocumentResponse, responses=errors)
    @router.get('/{document_id}/status', response_model=PolicyDocumentResponse, responses=errors)
    async def details(document_id: UUID):
        return await call(service.get, str(document_id))

    async def ingest(request, document_id=None):
        filename = request.headers.get('X-Filename', '')
        media_type = request.headers.get('Content-Type', '')
        maximum = service.max_file_bytes
        data = bytearray()
        async for part in request.stream():
            if len(data) + len(part) > maximum:
                raise PolicyManagementError(413, 'FILE_TOO_LARGE', 'The policy file exceeds the upload limit.')
            data.extend(part)
        result = await call(service.upload, filename, bytes(data), media_type, document_id)
        if result['status'] == 'failed':
            code = result['error_code']
            status = 503 if code in ('EMBEDDING_FAILED', 'INDEXING_FAILED', 'STORAGE_FAILED', 'ACTIVATION_FAILED', 'CLEANUP_FAILED') else 400
            return JSONResponse(status_code=status, content={'error': {'code': code, 'message': 'Policy indexing failed.'},
                'route': None, 'document': result})
        return result

    upload_schema = {'requestBody': {'required': True, 'content': {
        mime: {'schema': {'type': 'string', 'format': 'binary'}} for mime in ('text/plain', 'text/markdown', 'application/pdf')}},
        'parameters': [{'in': 'header', 'name': 'X-Filename', 'required': True, 'schema': {'type': 'string'}}]}

    @router.post('', response_model=PolicyDocumentResponse, status_code=201, responses=errors, openapi_extra=upload_schema)
    async def upload(request: Request):
        return await ingest(request)

    @router.put('/{document_id}', response_model=PolicyDocumentResponse, responses=errors, openapi_extra=upload_schema)
    async def replace(document_id: UUID, request: Request):
        return await ingest(request, str(document_id))

    @router.delete('/{document_id}', status_code=204, responses=errors)
    async def delete(document_id: UUID):
        await call(service.delete, str(document_id))
        return Response(status_code=204)

    return router
