"""HTTP interface for local, trusted development. No public-deployment guarantee."""
from contextlib import asynccontextmanager

import anthropic
import openai
import psycopg2
from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException

from data_agent.api_models import (
    AssistantRequest, AssistantResponse, ErrorDetail, ErrorResponse, TableCatalog, TableRows,
)
from data_agent.config import development_cors_origins, load_environment
from data_agent.main import run_request
from data_agent.services.assistant_response import assistant_response, InvalidAssistantResult
from data_agent.services.table_browser import TableBrowser, TableNotFound
from data_agent.agents.policy import PolicyAgentError
from data_agent.policy_api import policy_document_router
from data_agent.services.policy_management import PolicyManagement, PolicyManagementError
from data_agent.etl_api import etl_file_router
from data_agent.services.etl_browser import ETLBrowser, ETLFileError


def error_response(status, code, message, route=None):
    body = ErrorResponse(error=ErrorDetail(code=code, message=message), route=route)
    return JSONResponse(status_code=status, content=body.model_dump())


def create_app(*, runner=run_request, browser=None, policy_management=None, etl_browser=None) -> FastAPI:
    browser = browser if browser is not None else TableBrowser()

    @asynccontextmanager
    async def lifespan(app):
        load_environment()
        yield

    app = FastAPI(title="Data Agent — Local Development", lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return error_response(400, "INVALID_REQUEST", "Check the request fields and pagination.")

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error_response(exc.status_code, "INVALID_REQUEST", "The request is not supported.")

    async def failure(request, exc):
        if isinstance(exc, ETLFileError):
            return error_response(exc.status, exc.code, exc.message)
        if isinstance(exc, PolicyManagementError):
            return error_response(exc.status, exc.code, exc.message)
        if isinstance(exc, PolicyAgentError):
            return error_response(503, "UPSTREAM_UNAVAILABLE", "Company policy service is unavailable.", "policy")
        if isinstance(exc, TableNotFound):
            return error_response(404, "TABLE_NOT_FOUND", "This table is not available.")
        if isinstance(exc, (TimeoutError, openai.APITimeoutError, anthropic.APITimeoutError,
                            psycopg2.errors.QueryCanceled)):
            return error_response(504, "REQUEST_TIMEOUT", "The request timed out. Backend work may still be running.")
        if isinstance(exc, (openai.APIError, anthropic.APIError, psycopg2.Error)):
            return error_response(503, "UPSTREAM_UNAVAILABLE", "A required provider or database is unavailable.")
        return error_response(500, "INTERNAL_ERROR", "The backend could not return a usable response.",
                              exc.route if isinstance(exc, InvalidAssistantResult) else None)

    @app.middleware("http")
    async def handle_failures(request, call_next):
        # Keep sanitized failures inside CORS so the browser can read error responses too.
        try:
            return await call_next(request)
        except Exception as exc:
            return await failure(request, exc)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=development_cors_origins(),
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "X-Filename"],
        allow_credentials=False,
    )

    errors = {code: {"model": ErrorResponse} for code in (400, 404, 500, 503, 504)}
    # Validation is normalized to 400; suppress FastAPI's automatic 422 schema.
    errors["4XX"] = {"model": ErrorResponse}

    @app.post("/api/assistant", response_model=AssistantResponse, responses=errors)
    def assistant(body: AssistantRequest):
        return assistant_response(runner(body.question))

    @app.get("/api/tables", response_model=TableCatalog, responses=errors)
    def tables(request: Request):
        if request.query_params:
            return error_response(400, "INVALID_REQUEST", "The table catalog takes no query parameters.")
        return browser.list_tables()

    @app.get("/api/tables/{table_id}/rows", response_model=TableRows, responses=errors)
    def rows(request: Request, table_id: str, limit: int = Query(50, ge=1, le=100),
             offset: int = Query(0, ge=0)):
        keys = list(request.query_params.keys())
        if any(key not in ("limit", "offset") or len(request.query_params.getlist(key)) != 1 for key in keys):
            return error_response(400, "INVALID_REQUEST", "Only limit and offset are supported.")
        return browser.rows(table_id, limit, offset)

    app.include_router(policy_document_router(policy_management if policy_management is not None else PolicyManagement()))
    app.include_router(etl_file_router(etl_browser if etl_browser is not None else ETLBrowser()))
    return app


app = create_app()
