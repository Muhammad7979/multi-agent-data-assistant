"""Read-only HTTP access to registered ETL outputs."""
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

from data_agent.api_models import ErrorResponse, Page
from data_agent.services.etl_browser import ETLFileError


class ETLFileMetadata(BaseModel):
    id: str
    filename: str
    display_name: str
    format: str
    created_at: str
    size_bytes: int
    row_count: int | None
    status: Literal['ready', 'failed']
    available: bool


class ETLFileList(BaseModel):
    files: list[ETLFileMetadata]
    page: Page


class ETLPreview(BaseModel):
    format: Literal['csv', 'json']
    columns: list[str]
    rows: list[list[str]]
    text: str | None
    truncated: bool
    validation: Literal['preview_only', 'unvalidated_prefix']


def etl_file_router(service):
    router = APIRouter(prefix='/api/etl/files', tags=['ETL files'])
    errors = {code: {'model': ErrorResponse} for code in (400,404,409,413,415,422,503)}

    def parameters(request, allowed=()):
        if any(key not in allowed or len(request.query_params.getlist(key)) != 1 for key in request.query_params):
            raise ETLFileError(400, 'INVALID_REQUEST', 'Unsupported query parameters.')

    @router.get('', response_model=ETLFileList, responses=errors)
    def files(request: Request, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
        parameters(request, ('limit','offset'))
        return service.list(limit, offset)

    @router.get('/{file_id}', response_model=ETLFileMetadata, responses=errors)
    def details(file_id: str, request: Request):
        parameters(request)
        return service.details(file_id)

    @router.get('/{file_id}/preview', response_model=ETLPreview, responses=errors)
    def preview(file_id: str, request: Request):
        parameters(request)
        return service.preview(file_id)

    @router.get('/{file_id}/download', response_class=StreamingResponse, responses=errors)
    def download(file_id: str, request: Request):
        parameters(request)
        row, handle = service.open(file_id)
        try:
            media_type = service.content_type(row, handle)
        except Exception:
            handle.close()
            raise ETLFileError(503, 'ETL_STORAGE_UNAVAILABLE', 'The ETL file could not be read.') from None
        def chunks():
            try:
                while block := handle.read(64 * 1024):
                    yield block
            finally:
                handle.close()
        return StreamingResponse(chunks(), media_type=media_type,
            headers={'Content-Disposition': f"attachment; filename*=UTF-8''{quote(row['filename'])}",
                     'Content-Length': str(row['size_bytes']), 'X-Content-Type-Options': 'nosniff'},
            background=BackgroundTask(handle.close))

    return router
