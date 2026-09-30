# Local V1 interface

This is a retained historical V1 reference, not the current application contract. It contains earlier acceptance evidence and limitations that later Policy and ETL work superseded. For current behavior, use the [backend overview](BACKEND_OVERVIEW.md), [API reference](API_REFERENCE.md), and [setup guide](SETUP.md). The [historical frontend overview](history/FRONTEND_APPLICATION_OVERVIEW.md) records the earlier proposal. Statements below describe that earlier stage and must not be used as current feature or test-status claims.

## Scope and startup

React routes for Home (`/`), the dataset directory (`/data`), and shared dataset pages (`/data/:tableId`), plus `/assistant` compatibility navigation that opens the global assistant and redirects Home. Three HTTP endpoints; no authentication, conversation memory, charts, background jobs, cancellation, retries, or file delivery. Use only with trusted local development data. See the root README for setup, two-terminal startup, and API base URL configuration.

The persistent sidebar derives dataset links from the shared API catalog, including Payments when returned; a mobile navigation dialog replaces it on narrow screens. Home reports only the catalog count and client receipt time. Provider usage/cost/balance reporting is not integrated, and cards explicitly show that state. No payment sums or database row totals are available in the existing contract.

Dataset pages share one implementation with URL pagination (`?page=N`), loading/error/empty states, horizontal scrolling, accessible null values, and expandable long cells. The assistant is mounted once in the application shell. Its draft, response, and pending request persist across navigation and closing/reopening, but reset on reload. Closing does not cancel backend work. Escape dismisses the dialog, Tab remains within it, and Ctrl/Command+Enter submits. In-flight submissions are guarded and never automatically retried.

The API starts without building graphs or connecting to PostgreSQL. Environment loading happens at startup. A request invokes `run_request()`; the API returns only normalized DTOs. Synchronous handlers keep existing blocking workflows out of the ASGI event loop; this is not a job system or a cancellation guarantee.

Vite proxies relative `/api` requests to `127.0.0.1:8000` in development and local preview. No browser secrets or frontend environment variables are needed. Production hosting, access controls, and public deployment are not included.

For a development client that calls the API directly from another origin, optionally set `DATA_AGENT_CORS_ORIGINS` to a comma-separated list of exact origins **in the server process environment before starting Uvicorn**. For example, in PowerShell:

```powershell
$env:DATA_AGENT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
uv run uvicorn data_agent.api:app --host 127.0.0.1 --port 8000
```

This setting is read when the app is constructed, before lifespan startup loads `.env`; setting it only in `.env` is not sufficient. Restart the API after changing it. Empty/unset disables cross-origin access; wildcard origins are rejected. Only GET/POST and the Content-Type request header are enabled, without credentials. The current Vite proxy needs no change or CORS setting. CORS is a browser policy, not authentication or a public-deployment security boundary.

## Endpoints

| Method | Path | Contract |
| --- | --- | --- |
| POST | `/api/assistant` | Body: `{"question":"How many users are registered?"}`. Nonblank string, maximum 5,000 characters, no extra fields. |
| GET | `/api/tables` | No parameters. Returns `{"tables":[{"id":"public.users","label":"Users"}]}` for approved existing tables. |
| GET | `/api/tables/{table_id}/rows` | `limit` defaults to 50, range 1–100; `offset` defaults to 0, nonnegative. No other or duplicate parameters. |

Assistant response:

```json
{"answer":"An answer from the agent.","route":"sql","status":"answered"}
```

`route` is `sql`, `etl`, or `policy`; `status` is `answered`, `declined`, or `insufficient_evidence`. Policy responses include `sources`: a list of `{source_id, document_id, filename, page, section}` with nullable page/section. Insufficient policy evidence returns HTTP 200 with an honest answer and empty sources. SQL/ETL retain their original three-field response shape. Answered means a response was obtained, **not verified ETL completion**. SQL judge refusals use declined and HTTP 200. ETL responses display a prominent unverified-outcome notice. Tool observations, embeddings, retrieved chunks, prompts, graph state and SQL are not fields of this DTO. Terminal model prose remains generated content rather than a guarantee of correctness.

Table page example (illustrative column subset):

```json
{
  "table_id":"public.users",
  "columns":[{"name":"user_id","type":"integer"}],
  "rows":[[1],[2]],
  "page":{"limit":50,"offset":0,"has_more":false}
}
```

Columns retain database order; row arrays align with them. Empty pages retain columns. `has_more` is calculated using an extra fetched row; no total count is queried. Browsing uses explicit approved identifiers and a read-only transaction, independently of the SQL agent. Only the five seeded public tables are permitted by `ALLOWED_TABLES`; changes to this list require an explicit access decision. All existing development columns are included. This is not authorization to expose production data. Ordering assumes the seeded primary-key columns; schema drift can make reads fail. Concurrent mutations can shift offset pages.

Display types are string, integer, number, boolean, date, datetime, json. Null stays null; precision-sensitive Decimal/large integers become strings. Dates/timestamps use ISO text without inventing a timezone for naive values. Complex cells become JSON text; non-finite floats become strings. React renders structured cells as text. Assistant answers render Markdown through react-markdown and remark-gfm, with raw HTML ignored and default safe URL filtering retained. Images are not loaded. Links open in a new tab with noopener/noreferrer. Markdown tables and code blocks have keyboard-accessible horizontal scrolling; they do not replace the structured Data tables.

Errors use one envelope:

```json
{"error":{"code":"UPSTREAM_UNAVAILABLE","message":"A required provider or database is unavailable."},"route":null}
```

400 INVALID_REQUEST; 404 TABLE_NOT_FOUND; 503 UPSTREAM_UNAVAILABLE for recognized provider/database exceptions and Policy service failures; 504 REQUEST_TIMEOUT for recognized timeouts; 500 INTERNAL_ERROR for unexpected failures or unusable graph output. Route may be sql/etl/policy when known; otherwise null. Policy service errors are sanitized and mapped to 503, including wrapped provider failures. Raw exceptions are not sent to the browser. The API introduces no new execution timeout: a 504 translates an existing timeout, not guaranteed cancellation.

## Verification

`python -m unittest discover -s tests -v` checks normalization, HTTP contracts, table boundaries/serialization/cleanup, and real SQL/ETL graph wiring with fake external dependencies. `npm run build` performs TypeScript checking and builds the frontend. `tests/ui_fixture.py` provides synthetic HTTP responses for UI/proxy checks; it performs no database, LLM, extraction, or generated-code operations.

These checks do not establish live provider access, model availability, database contents, or ETL correctness. Live end-to-end validation remains separate.

Final V1 acceptance passed 38 backend tests and the TypeScript/production build. Isolated headless browser checks used Vite with the synthetic API on separate local ports and covered home/data navigation, blank and pending submissions, SQL/ETL answers, unverified ETL notices, refusal/timeout states, pagination, empty results/catalog, catalog/row failures, and mobile overflow. Test servers were stopped afterward. No live provider/database calls, seeding, generated-code execution, or ETL jobs were used.

Assistant structured results are not available in the approved V1 contract: the response contains only `answer`, `route`, and `status`. Consequently, structured Assistant rendering is not an acceptance claim; it remains deferred. Structured tables are provided by the Data page. Live provider/account and database readiness remain environment checks outside this synthetic acceptance run.

Frontend development uses system-installed Node.js and npm through the package scripts documented in the root README. No bundled runtime, custom launcher, or Python frontend server is required.

## Dependency scope

FastAPI and Uvicorn provide the HTTP interface. Pydantic is explicitly declared for the DTOs. OpenAI, Anthropic, and Starlette are also direct declarations because the API imports their exception types; their already-resolved versions were retained. HTTPX is a development dependency for in-process API tests. The existing unrelated dependency declarations were retained for later review.

React/React DOM render the UI, React Router provides application navigation, and Vite plus its React plugin builds/serves the frontend. TypeScript and React/Node type declarations check the frontend contracts/tooling. react-markdown renders assistant prose as React elements; remark-gfm adds Markdown tables and other GFM syntax. No raw-HTML or syntax-highlighting plugin is enabled. Native fetch, React state/context, local SVG icons, and shared CSS tokens require no HTTP client, state-management, icon, chart, or structured table-library dependency. The frontend currently configures build/dev/preview scripts only; there is no lint or automated frontend test script.

## Deferred existing issues

| Area | Existing limitation | Later phase |
| --- | --- | --- |
| DatabaseService | Failure paths may return None or fail during cursor cleanup | Correctness/reliability |
| SQL workflow | Stringified query results, no returned column metadata | Future assistant table feature |
| SQL execution | LLM judgment is not read-only enforcement; prompt limits are not hard limits | Security/reliability |
| ETL tool results | Text may claim success even when execution failed; output files are not verified | Correctness/reliability |
| Transformation | Generated Python uses unrestricted exec; code cleanup and requested format handling need review | Security/correctness |
| Extraction | Limited JSON shape, no pagination, no explicit timeout/response-size policy | Reliability |
| Graph state | Accumulated histories combined with additive reducers need review | Correctness |
| Dependencies | Existing pydentic declaration and other direct/transitive dependency coverage remain to review | Dependency cleanup |
| Execution lifecycle | Browser disconnect does not stop work; no rollback, deadlines, job queue, or retry guarantees | Reliability |
| Deployment | No user authentication/authorization or public-access protections are provided | Production/security |

None of these existing implementations was silently fixed. The new API rejects an unusable SQL None result rather than reporting it as an answered request. ETL output is explicitly labeled unverified; no heuristic prose parsing attempts to certify success.
