"""Public HTTP contracts, independent of LangGraph state."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator
from data_agent.agents.policy import PolicySource

Route = Literal["sql", "etl", "policy"]
Cell = str | int | float | bool | None


class AssistantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: StrictStr = Field(min_length=1, max_length=5000)

    @field_validator("question")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Question must not be blank")
        return value


class ETLOutput(BaseModel):
    id: str = Field(pattern=r'^[0-9a-f]{16}$')
    filename: str
    format: Literal['csv', 'json', 'parquet']
    created_at: str
    size_bytes: int = Field(ge=0)
    row_count: int | None = Field(default=None, ge=0)


class AssistantResponse(BaseModel):
    answer: str
    route: Route
    status: Literal["answered", "declined", "insufficient_evidence"]
    sources: list[PolicySource] | None = Field(default=None, exclude_if=lambda value: value is None)
    files: list[ETLOutput] | None = Field(default=None, exclude_if=lambda value: value is None)
    etl_status: Literal['completed', 'partial', 'failed', 'response_failed'] | None = Field(default=None, exclude_if=lambda value: value is None)


class TableSummary(BaseModel):
    id: str
    label: str


class TableCatalog(BaseModel):
    tables: list[TableSummary]


class Column(BaseModel):
    name: str
    type: Literal["string", "integer", "number", "boolean", "date", "datetime", "json"]


class Page(BaseModel):
    limit: int
    offset: int
    has_more: bool


class TableRows(BaseModel):
    table_id: str
    columns: list[Column]
    rows: list[list[Cell]]
    page: Page


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
    route: Route | None = None
