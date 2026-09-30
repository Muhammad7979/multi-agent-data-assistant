# API reference: ETL Files and Company Policy

These detailed contracts were moved from the root README. For the shared request journey, start with the [backend overview](BACKEND_OVERVIEW.md). For setup and API URL configuration, see [setup](SETUP.md). The local API also provides interactive endpoint documentation at `http://127.0.0.1:8000/docs` while running.

All endpoints retain the trusted/local application boundary. This reference does not imply authentication or public-deployment security.

## ETL Files API


The existing `/api/assistant` response now includes optional `files` and
`etl_status` fields for executed ETL operations. Each file contains its stable
`id`, stored `filename`, `format`, UTC `created_at`, `size_bytes`, and nullable
`row_count`. Multiple successful operations can return multiple files. The
floating assistant uses these IDs with the existing download API and configured
frontend API base URL; no additional assistant endpoint is involved.

Completion text is derived from tool/storage outcomes, not the model's claim.
`etl_status` is `completed`, `partial`, `failed`, or `response_failed` (a later
model response failed). Successfully saved files remain available in a partial
or response-generation failure. Extraction, transformation, and storage failures
are reported separately, with no automatic retry of identical tool operations
within one execution. SQL and Policy response fields are unchanged.

Transformation outputs now publish through the same staged file store and
catalog as extracted outputs. Generated transformation code still runs under
the existing trusted/local execution boundary. Transformation record counts are
omitted (`null`) unless reliably known; extraction counts come from the actual
normalized DataFrame. No transformation completion is claimed for extraction-only
requests. A later model failure does not confirm any still-unexecuted operations.

These read-only endpoints reuse the existing local/trusted FastAPI application:

| Endpoint | Result |
| --- | --- |
| `GET /api/etl/files?limit=50&offset=0` | `{files, page}` sorted newest first; limit 1–100 |
| `GET /api/etl/files/{file_id}` | Safe metadata for a verified available file |
| `GET /api/etl/files/{file_id}/preview` | Bounded CSV or JSON preview |
| `GET /api/etl/files/{file_id}/download` | Original bytes streamed as an attachment |

Metadata includes ID, filename, display name, format, UTC timestamp, size, known
row count, status and availability. Internal storage references and source URLs
are excluded. IDs must match registered 16-character hexadecimal IDs; paths are
never accepted. Filenames must match the managed naming convention and record ID.
Symlink/outside-root, nonregular and size-changed files cannot be opened. Downloads
use the verified open handle, not a subsequent path lookup. This remains trusted
local storage; same-size external file modifications are not detected by a checksum.

CSV preview returns columns and up to 50 rows, capped at 100 columns and 1,000
characters per cell. At most 256 KiB plus one sentinel byte is read. Oversized CSV
fields return `PREVIEW_LIMIT` rather than being labeled malformed. Empty files and
header-only CSVs return empty rows. Preview limits do not certify the rest of a file.

JSON objects, arrays and newline-delimited JSON are supported. Readable JSON text
is capped at 20,000 characters, with depth/breadth limits. Large files return a
bounded prefix marked `truncated=true`, `validation=unvalidated_prefix`; this text
is not represented as a complete valid JSON document. Parquet previews return 415
but original bytes remain downloadable. No additional text formats are introduced.

Downloads include a safe attachment filename, content length and nosniff header.
CSV/Parquet use their respective media types. A bounded JSON inspection distinguishes
ordinary JSON from NDJSON; unrecognizable prefixes use application/octet-stream.
Malformed preview content can still be downloaded unchanged for inspection.

Errors use `{error:{code,message},route:null}`: 400 invalid IDs/parameters, 404
unknown or physically missing files, 409 changed/unavailable/invalid references,
413 preview limits, 415 unsupported preview, 422 malformed content, and 503 storage
unavailable. Lists retain missing files as unavailable; details/preview/download
return the corresponding error. Unregistered legacy files are not served.
Run `uv run python -m unittest tests.test_etl_api -v` for endpoint checks.

## Company Policy document-management API


All routes use `/api/policy/documents` and the existing trusted/local API boundary.
No authentication or public-deployment security is added.

| Method | Path suffix | Result |
| --- | --- | --- |
| GET | (none) | Paginated `{documents, page}`; `limit=50` (1–100), `offset=0` |
| POST | (none) | Upload/index a file; 201 only after ready |
| GET | `/{id}` | Public document metadata |
| GET | `/{id}/status` | Same metadata with current processing state |
| PUT | `/{id}` | Replace file and re-index; 200 only after ready |
| DELETE | `/{id}` | Remove originals, vectors, and metadata; 204 on success |

POST/PUT accept **raw file bytes**, not multipart or JSON. Supply `X-Filename`
and the approved `Content-Type` (`text/plain`, `text/markdown`, `application/pdf`).
The server enforces the configured file-size limit while reading the body.
For example, from PowerShell:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/policy/documents -H "X-Filename: handbook.txt" -H "Content-Type: text/plain" --data-binary "@handbook.txt"
```

Responses include `id`, `name`, `type`, `status`, `created_at`, `updated_at`,
`size_bytes`, `chunk_count`, `has_indexed_version`, and `error_code`. Name/type/size
describe the latest attempt; chunk count describes the active indexed version.
No paths, embeddings, raw chunks, hashes, or generation records are exposed.
There is no original-file download endpoint.

Indexing is synchronous, with actual `pending`, `processing`, `ready`, and `failed`
states visible through metadata reads. Invalid files return 400/413/415; missing
documents return 404; unfinished processing/deletion blocks replacement with 409.
Extraction failures return 400 and embedding/index/storage failures return 503.
Failures after document creation include safe `document` metadata alongside the
standard `{error, route}` fields, so callers can inspect status. No automatic
upload retry is performed; retrying POST creates a new document.

Successful replacement removes old vectors. Failed preparation retains the previous
indexed version, indicated by `has_indexed_version`. Delete deactivates retrieval
first, then removes all document vectors, originals, and metadata. Failed cleanup
returns 503 and retains a failed document with `DELETE_PENDING`; retry DELETE.
This prevents an interrupted deletion from influencing subsequent Policy answers.
Storage operations span SQLite/Chroma/files and are not one atomic transaction.
Run `uv run python -m unittest tests.test_policy_management_api -v` for endpoint
tests, including real Chroma retrieval after replacement/deletion with mocked OpenAI.


Return to the [documentation index](README.md).
