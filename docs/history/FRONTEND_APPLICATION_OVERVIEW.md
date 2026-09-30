# Data Agent — Frontend Application Overview

> Implementation note: this document records the pre-implementation analysis and proposal. The local V1 now exists; see [current interface documentation](../V1_INTERFACE.md) and [startup instructions](../../README.md). V1 uses text-only assistant responses with `answered`/`declined`, and structured records only on the Data page. Statements below that describe missing APIs refer to the inspected pre-implementation baseline.

## 1. Executive Summary

The current application is a Python/LangGraph backend with SQL and ETL workflows. It has one application package, but no HTTP server, browser interface, or JSON API. React cannot communicate directly with it today.

The recommended first frontend has two pages: **Assistant** for one natural-language request and its answer, and **Data** for selecting a PostgreSQL table and viewing a bounded page of records. Charts, conversational memory, streaming, uploads, and file downloads are not necessary for the first release.

This document separates **VERIFIED** source behavior, **PROPOSED** future contracts, and **UNKNOWN** runtime facts. All API schemas and frontend structures below are proposals, not existing capabilities. Inspection was static: no application, database, provider, extraction, transformation, or seed workflow was executed. Database contents, model availability, credentials, permissions, and successful end-to-end execution remain unverified.

Only this document is created by this task. Implementation requires separate approval.

## 2. What the Backend Does Today

Verified capabilities:

- Classify a natural-language request as SQL or ETL.
- Generate PostgreSQL SQL using schema and sample-row context, obtain an LLM safety judgment, execute or decline it, and generate a natural-language answer.
- Extract an HTTP JSON response containing a `results` member into a local data file.
- Generate and execute Python/Pandas code to transform a local file.
- Return the parent graph state to a Python caller.

There is no generic dataset catalog, table-browsing service, persistent conversation store, or automated test suite in the inspected repository. ETL writes files; it does not currently provide a general database-loading workflow.

Primary evidence: [entry point](../../src/data_agent/main.py), [router](../../src/data_agent/agents/router.py), [SQL graph](../../src/data_agent/agents/sql.py), [ETL graph](../../src/data_agent/agents/etl.py), [tools](../../src/data_agent/agents/etl_tools.py), [state](../../src/data_agent/agents/state.py), and [project configuration](../../pyproject.toml).

The root README describes the general structure, but its final known-issues paragraph is partly stale: current source consistently uses `sql_query_execution_result`, calls `with_structured_output`, and calls `level.lower()` in model selection. Older documentation is not evidence that those defects remain.

## 3. Current Application Architecture

```text
src/data_agent/
├── __init__.py                 Package declaration
├── __main__.py                 Module entry point
├── main.py                     Example runner and run_request()
├── config.py                   Environment, database settings, data root
├── llm.py                      Provider/model selection
├── agents/
│   ├── __init__.py
│   ├── router.py               Parent graph and routing nodes
│   ├── sql.py                  SQL graph, nodes, prompts
│   ├── etl.py                  Tool-calling graph and prompt
│   ├── etl_tools.py            Tool definitions and code-generation coordination
│   └── state.py                Graph states and structured decisions
└── services/
    ├── __init__.py
    ├── database.py             PostgreSQL schema inspection/query execution
    ├── extraction.py           HTTP extraction and file writing
    └── transformation.py       File preview and generated-code execution
```

Graphs are constructed through `build_data_agent`, `build_sql_graph`, and `build_etl_graph`. Services perform operations; agents coordinate them. No structural reorganization is needed to plan the frontend.

[LLM configuration](../../src/data_agent/llm.py) currently selects OpenAI model strings `gpt-5.6-luna` for `low`, `gpt-5.6-terra` for `medium`, and `gpt-5.6-sol` for `high`; `claude` selects Anthropic `claude-sonnet-5`. These are source literals, not a claim about provider availability. Router and ETL use `claude`; SQL uses `low` and `medium`. Therefore even a SQL request goes through an Anthropic router first.

[Configuration](../../src/data_agent/config.py) explicitly loads environment settings. PostgreSQL uses `DB_HOST`, `DB_PORT`, `DB_DATABASE`, `DB_USERNAME`, and `DB_PASSWORD`. Provider clients use their provider credentials; no credential belongs in React. The default data root is the repository when its project/data directories exist, otherwise the working directory.

## 4. User Request Flow

```text
main(): load environment; use EXAMPLE_REQUEST; print result
                         │
                 run_request(question)
                         │
        Parent state: HumanMessage + empty route_response
                         │
                    router_node
                  /             \
              sql_node         etl_node
                 │                 │
           SQL child graph    ETL child graph
                  \               /
              Child state appended to parent messages
                         │
                Full parent state returned
```

| Stage | Input | Responsibility | Output / destination |
| --- | --- | --- | --- |
| `main` | Hardcoded example | Load environment and invoke request | Print full returned state |
| `run_request` | Question string, optional supplied graph | Build graph if absent; invoke fresh state | Parent graph |
| `router_node` | Latest message content | Structured LLM classification | `route_response` becomes `sql` or `etl` |
| `sql_node` | Latest request | Populate required SQL state and invoke child | Child dictionary appended to parent messages |
| `etl_node` | Latest request | Wrap in a HumanMessage and invoke child | Child dictionary appended to parent messages |
| Parent completion | Updated state | No additional response formatting node | Python caller receives full graph state |

The parent declares no outgoing edge from its specialist nodes; there is no final parent answer-normalization stage. Child states are embedded as dictionaries among message objects. This is not a browser-ready response. The normal entry point initializes a new request rather than maintaining a conversation.

## 5. Router Workflow

`build_data_agent` creates both specialist graphs unless supplied and creates a structured router client. `RouterSchema` contains an `answer` restricted to `sql` or `etl` and `comments`.

- **SQL:** answer a database question through the SQL workflow.
- **ETL:** coordinate extraction or file transformation through tools.
- Only `answer` is retained as `route_response`; router comments are discarded.
- The conditional edge raises for an unsupported route. There is no third general-chat route.

The frontend should send a question, not attempt its own classification. A small SQL/ETL badge can display the completed response route. Route selection, model choice, routing comments, and raw graph state should remain backend concerns. Selecting a table on the Data page does not currently constrain assistant queries.

## 6. SQL Workflow

| Node | Responsibility | Next node |
| --- | --- | --- |
| `curate_ques` | Rephrase the question using the low-tier LLM | `prompt_query_context` |
| `prompt_query_context` | Get `public` schema details and samples; compose generation prompt | `generate_sql` |
| `generate_sql` | Generate SQL using the medium-tier LLM | `is_safe_sql` |
| `is_safe_sql` | Obtain structured Yes/No judgment and comments | Conditional execution/cancellation |
| `canceled_sql` | Produce refusal text and AIMessage | END |
| `execute_sql` | Execute through DatabaseService and store returned result | `represent_final_answer` |
| `represent_final_answer` | Generate user-facing text from question/result | END |

The generation prompt asks for a default limit of 10 rows. That instruction is not a database-enforced limit. The LLM judgment is not proof of read-only execution.

In this table, “available” means present in the returned child state, nested inside parent messages. **None is currently available over HTTP.**

| Information | Generated By | Available to Frontend? | Useful to Display? | Notes |
| --- | --- | --- | --- | --- |
| Original question | Caller / `sql_node` | Yes, child `user_question` | Yes, already held by UI | Need not echo in API |
| Curated question | `curate_ques` | Yes, `curated_ques` | Usually no | Internal interpretation |
| Schema/sample prompt | `prompt_query_context` | Yes, combined prompt field | No | Includes database context/sample data |
| Generated SQL | `generate_sql` | Yes, `generated_sql_query` | Optional developer view | Omit from minimal user DTO |
| Safety decision | `is_safe_sql` | Yes, `is_safe` | As a declined status | Do not advertise guaranteed safety |
| Judge explanation | `is_safe_sql` | Yes, `comments` | Limited user explanation | Internal details need normalization |
| Query result | `execute_sql` | Yes, `sql_query_execution_result` | Potential table | Currently a string of Python rows, not structured JSON |
| Final answer | Final-answer or cancellation node | Yes, `final_answer` | Yes: TEXT | Main response content |
| Column metadata | Not retained by query method | No | Yes for TABLE | Requires backend work |
| Execution failure/status | No dedicated model | No reliable typed outcome | Yes: STATUS | Exceptions and string/None results need review |

Do not reconstruct records by evaluating the string result. Structured rows and column names must be captured before stringification if assistant tables are included.

## 7. ETL Workflow

The graph starts at `llm_node`, passes a prompt containing the message history to a tool-bound Anthropic model, and appends its response. Tool calls route to `tool_node`; calls are executed sequentially and their observations appended as ToolMessages. Processing returns to `llm_node` until a response contains no tool calls, then ends.

| Tool | Arguments | Current operation | Returned information |
| --- | --- | --- | --- |
| `extract_load_tool` | `url`, `output_folder`, `format` | Call extraction service | Success/failure text containing output location |
| `transform_load_tool` | `input_file_path`, `output_folder`, `output_format`, `user_question` | Preview file; generate Python; execute it | Text containing claimed location/format, generated code, execution result |

[Extraction](../../src/data_agent/services/extraction.py) performs one GET, expects `response.json()['results']`, normalizes that value with Pandas, and writes fixed-name `extracted_data.<format>`. Supported branches are CSV, newline-delimited JSON, and Parquet. It does not follow pagination or provide a dataset registry. Repeated writes to the same destination can replace the previous output. Relative output folders are joined to the configured data root.

[Transformation](../../src/data_agent/services/transformation.py) reads CSV, JSON lines, or Parquet, then presents the first three rows as text. The tool asks an LLM to generate Pandas code, cleans its text, and passes it to `exec`. Input paths are used as supplied. The requested `output_format` is not included in the code-generation prompt, and there is no independent generated-file validation. A tool message claiming success is not sufficient evidence that a file was produced.

ETL has only a messages state: no dedicated `final_answer`, file manifest, structured success flag, row count, preview, or download URL. A future adapter would normalize the terminal assistant content rather than expose all tool observations and generated code.

| Output | Visualization | V1 treatment |
| --- | --- | --- |
| Terminal assistant answer | TEXT | Show normalized text |
| Verified operation outcome | STATUS | Requires reliable backend outcome first |
| Extracted/transformed file | FILE | Local file exists only if operation succeeds; no browser delivery yet |
| Structured preview | TABLE | Not returned today; defer unless specifically approved |
| Numeric aggregates | OPTIONAL FUTURE CHART | No chart specification exists; defer |

Untrusted web access to arbitrary URLs, file paths, or generated Python execution requires a separate security decision before enabling ETL through a public frontend.

## 8. Current State / Data Contracts

All listed fields are required in their Pydantic models. Each `messages` field uses `Annotated[list, add]` with unconstrained elements; it is not a typed API message list.

| Model / owner | Field | Type | Purpose | Frontend treatment |
| --- | --- | --- | --- | --- |
| `DataAgentSchema` / router | `messages` | Annotated list with additive reducer | Parent input and nested child results | Internal only |
| Same | `route_response` | str | Selected route | Normalize to route enum |
| `RouterSchema` / routing output | `answer` | Literal sql/etl | LLM route decision | Source of route |
| Same | `comments` | str | Classification explanation | Discarded by current node; internal |
| `AgentSchema` / SQL | `messages` | Annotated list with additive reducer | SQL processing messages | Internal |
| Same | `user_question` | str | Original request | Useful; UI already has it |
| Same | `curated_ques` | str | Rephrased question | Internal |
| Same | `prompt_query_context` | str | Prompt including schema/samples | Internal |
| Same | `generated_sql_query` | str | Generated statement | Developer-only optional |
| Same | `is_safe` | Literal Yes/No | Judge decision | Translate decline outcome |
| Same | `comments` | str | Judge explanation | Normalize if shown |
| Same | `sql_query_execution_result` | str | Stringified rows | Not a table contract |
| Same | `final_answer` | str | Final natural-language response | User-facing answer |
| `JudgeSchema` / SQL output | `answer` | Literal Yes/No | Structured judgment | Internal |
| Same | `comments` | str | Judgment explanation | Internal/source for decline |
| `ETLAgentSchema` / ETL | `messages` | Annotated list with additive reducer | Assistant/tool observations | Normalize terminal answer only |

No schema defines HTTP requests, JSON table cells, pagination, downloadable files, or API errors. Preserve internal state ownership; React should depend on a separate small DTO rather than these models.

## 9. Database Capabilities

[DatabaseService](../../src/data_agent/services/database.py) uses PostgreSQL through psycopg2. Construction opens a connection. Its schema/query methods close cursor and connection after their operation; there is no pool or long-lived browsing session. Connection/cleanup edge cases remain a later review item.

`schema_detail(schema_name)` queries information_schema for tables and columns, fetches five sample rows per table, and concatenates everything into prompt text. SQL currently asks for `public`. `execute_sql(query)` runs a statement, fetches all rows, commits, and returns `str(result)`; failure paths can return None or raise.

| Data-page capability | Classification | Current support versus addition needed |
| --- | --- | --- |
| List tables | PARTIALLY EXISTS | Discovery SQL exists inside schema text builder; structured catalog missing |
| List columns/types | PARTIALLY EXISTS | Metadata read for prompts; standalone JSON schema missing |
| Fetch rows | PARTIALLY EXISTS | Query primitive and sample fetch exist; bounded browser response missing |
| Pagination | MISSING | No limit/offset page contract or continuation metadata |
| Sorting | MISSING | No browsing API; generated SQL may sort but is not a deterministic UI control |
| Filtering/search | MISSING | No validated filter/search contract |
| Row count | PARTIALLY EXISTS | Seed script prints counts; no catalog/count service |
| Dataset selection | MISSING | No allowlisted dataset IDs or selector API |
| Arbitrary table browsing | MISSING | No safe identifier selection and records endpoint |
| Local file browsing | MISSING | Reading/writing known files is not a dataset catalog |

The seed script and CSVs describe `users`, `vehicles`, `rides`, `payments`, and `ratings` in `public`, with relationships defined in seed DDL. They do not establish which tables exist in the live database. Frontend choices should come from an approved server catalog rather than hardcoding this list.

For V1, recommend PostgreSQL tables only on the Data page. Extracted files belong to a separate future dataset/download contract unless the user explicitly prioritizes them.

## 10. Current Backend Interface

- The configured console command `data-agent` targets `data_agent.main:main`.
- `python -m data_agent` uses `__main__.py` to call the same function.
- In a prepared uv environment, `uv run data-agent` and `uv run python -m data_agent` structurally select those entry points. Neither was executed here.
- Both run the hardcoded `EXAMPLE_REQUEST`, currently a Pokemon API extraction request, and print the full result. They are not interactive question-input interfaces.
- Python callers can call `run_request(question, agent=...)`; the hosting process must load environment configuration appropriately.

**Can React communicate with the backend as it exists today? No.** There is no HTTP listener, request endpoint, CORS policy, JSON response contract, or browser-accessible file service. React cannot import Python modules. Spawning the example CLI per browser request is not the proposed integration.

## 11. React Integration Gaps

1. An HTTP host must accept questions and invoke the existing Python entry function/graph.
2. Parent/child state must be mapped to a stable DTO, not exposed directly.
3. Outcome and error handling must distinguish successful work, declined SQL, and failures.
4. Table discovery and reads need structured, bounded results independent of LLM generation.
5. PostgreSQL values and message content need explicit JSON serialization.
6. Same-origin hosting/proxying or a restricted cross-origin policy must be selected.
7. The deployment trust boundary must address SQL execution and ETL operations before exposing them.

No React implementation can compensate for missing columns, unreliable success reporting, or arbitrary code execution. These are separate backend tasks, not changes made by this document.

## 12. Proposed Minimal API

**DESIGN ONLY — none of these endpoints exists.**

| Method | Endpoint | Purpose | Request | Response | Backend mapping |
| --- | --- | --- | --- | --- | --- |
| POST | `/api/assistant` | Run one request | JSON question | Normalized answer/route/status; optional table | Existing `run_request`, plus new adapter/error handling |
| GET | `/api/tables` | List approved PostgreSQL tables | No body | Array of table IDs and labels | New structured discovery using the metadata capability already present |
| GET | `/api/tables/{table_id}/rows` | Read selected table page | `limit`, `offset` | Columns, rows, page metadata | New bounded read operation; do not route through an LLM |

Proposed defaults: nonblank question up to 5,000 characters; records page size 50 with maximum 100; nonnegative offset. These are design defaults for approval, not current limits. Table IDs are server-issued identifiers resolved against an allowlist, not SQL supplied by the browser.

Start with request/response HTTP if approved execution deadlines fit observed request durations. Do not add job queues or streaming without evidence they are needed. The future host must avoid blocking other requests with synchronous work; its execution strategy is an implementation decision. Do not automatically retry assistant POSTs, because ETL can have side effects.

Use one origin through a development/production proxy where practical. If separate origins are required, configure a specific allowed frontend origin. CORS is not authentication or an execution safety boundary. No seed, raw SQL, arbitrary file, or shell endpoint is proposed.

## 13. Assistant API Contract

Proposed request:

```json
{"question":"How many users are registered?"}
```

Proposed response shape; illustrative content, not an observed database result:

```json
{
  "answer": "Payment methods are shown below.",
  "route": "sql",
  "status": "completed",
  "table": {
    "columns": [{"name": "payment_method", "type": "string"}],
    "rows": [["card"], ["cash"]],
    "truncated": false
  }
}
```

| Field | Proposed contract |
| --- | --- |
| `answer` | Normalized user-facing text; SQL final_answer or terminal ETL assistant content |
| `route` | `sql` or `etl` |
| `status` | `completed` or `declined`; only after backend outcome verification |
| `table` | Null when unavailable; otherwise columns, ordered row arrays, and truncation flag |

V1 may launch with `table: null` for assistant answers while the Data page supplies real tables. Showing assistant SQL tables requires retaining structured results and metadata in a separately approved backend change. A null table means unavailable; an empty rows array means an available result containing zero rows.

Proposed error body:

```json
{
  "error": {
    "code": "UPSTREAM_UNAVAILABLE",
    "message": "The assistant could not complete this request."
  },
  "route": null
}
```

Route may be sql/etl if already known, otherwise null. Proposed HTTP outcomes: 400 invalid input, 404 unknown table, 503 unavailable dependency, 504 deadline exceeded, 500 unexpected failure. A normal SQL refusal is HTTP 200 with `status: declined`, not a transport error. Provider traceback, credentials, SQL/sample context, and filesystem paths must not leak through error text.

**User-facing:** answer, route badge, verified status, optional structured table, safe error message. **Internal/developer-only:** prompts, generated SQL, judge diagnostics, generated Python, raw tool messages, full state, provider configuration, local paths. Do not include a generic metadata dump. Download links are deferred until validated artifact delivery exists.

## 14. Data/Table API Contract

Proposed catalog example; actual entries come from the server:

```json
{
  "tables": [
    {"id": "public.users", "label": "Users"},
    {"id": "public.rides", "label": "Rides"}
  ]
}
```

Example records request: `GET /api/tables/public.users/rows?limit=50&offset=0`.

Illustrative records response with a reduced example column set, not a statement of the full live schema:

```json
{
  "table_id": "public.users",
  "columns": [
    {"name": "user_id", "type": "integer"},
    {"name": "city", "type": "string"}
  ],
  "rows": [[1, "Example City"]],
  "page": {"limit": 50, "offset": 0, "has_more": false}
}
```

Rows are arrays aligned with ordered columns; this also accommodates duplicate column labels in assistant query results. Proposed display types are string, integer, number, boolean, date, datetime, and json. Null stays JSON null. Serialize dates/timestamps as ISO text with an explicit timezone policy; serialize precision-sensitive decimals and integers outside JavaScript's safe range as strings. Complex JSON cells need a consistent display representation. Never infer authoritative column metadata from an LLM answer.

The server must validate table IDs and quote resolved identifiers using database facilities, not interpolate a browser-provided identifier. Apply an approved table/column policy. Browse queries need a deterministic order (prefer a known primary key), bounded limit/offset, and one extra row to calculate `has_more`. A count query is unnecessary for Previous/Next. Concurrent database changes can shift offset pages; a snapshot guarantee is outside V1.

Return columns even when rows are empty. Empty catalogs and empty tables are successful states, distinct from unknown table and database failure. Tables without a suitable ordering key require an explicit browsing policy before inclusion.

## 15. Frontend Information Architecture

```text
/       Assistant: question → answer → optional structured result
/data   Data: select approved table → view page of records
```

One application shell and two navigation links suffice. No dashboard, separate workflow configuration page, or chat-session sidebar is justified. The initial trust assumption is a local/internal tool for approved users; this is a proposal requiring confirmation, not an established security boundary.

## 16. Assistant Page

**V1 essential:** labeled multiline question input, Send button, empty-state guidance, submitting state, disabled duplicate submission, response text, SQL/ETL badge when known, decline/error state, and a conditional table. Keep the submitted question visible. Support keyboard access and accessible loading/error announcements.

Use plain text initially rather than rendering arbitrary HTML from model output. Distinguish a missing table from a zero-row table. Display completion only from verified API outcomes. There is no need for token streaming or a progress timeline: the current backend returns a final result, not progress events.

**Optional:** copy answer, a few example questions, and a local previous-result display. Persistent chat history and conversation memory are not current capabilities. ETL submission must follow the approved trust/safety decision; excluding it from V1 is a product decision, not an implicit removal of backend functionality.

## 17. Data Page

**V1 required:** table selector populated from the catalog; loading, empty, and error states; header/row rendering; horizontal scrolling for wide tables; Previous/Next controls using offset and has_more. Reset the page when selection changes. No editable cells or raw SQL input.

This UI is compatible with PostgreSQL data but depends on the new catalog and paged-read operations. It cannot be built reliably by parsing schema prompt text or asking the agent to browse tables.

**Later:** sorting, filters, search, total counts, CSV export, extracted-file datasets, and larger-grid virtualization. Add only after basic browsing is useful and measured constraints justify them.

## 18. Suggested React Components

| Component/module | Responsibility |
| --- | --- |
| `App` | Shell, navigation, and two routes |
| `AssistantPage` | Input, request state, answer/error/status, optional table |
| `DataPage` | Catalog, selected table, page controls, records state |
| `ResultTable` | Shared read-only columns/rows rendering and empty state |
| `api.ts` | Three fetch calls, response checks, error normalization |
| `types.ts` | Approved API DTO types |

Keep buttons, labels, loading text, and the simple selector inside their page until actual reuse makes extraction useful. A separate component for every visual element would add needless fragmentation.

## 19. Frontend State Requirements

| Area | State |
| --- | --- |
| Assistant | Draft question, submitted question, loading flag, response, error |
| Data | Table catalog, selected table ID, columns/rows, offset, limit, has_more, loading/error states |
| Navigation | Current route managed by router |

React hooks and page-local state are sufficient. Derived values such as “Previous enabled” need not be stored separately. Abort or disregard stale Data-page fetch responses when selection changes. Aborting a browser request does not guarantee backend ETL cancellation; avoid claiming otherwise. No Redux, Zustand, persistence layer, or server-state library is required for three endpoints.

## 20. Suggested React Project Structure

**PROPOSED, not created:** keep the frontend as a sibling of the Python source, with its own package metadata and lockfile.

```text
frontend/
├── package.json
├── index.html
├── vite.config.ts
├── tsconfig.json
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── pages/
    │   ├── AssistantPage.tsx
    │   └── DataPage.tsx
    ├── components/
    │   └── ResultTable.tsx
    ├── api.ts
    ├── types.ts
    └── styles.css
```

Existing `src/data_agent`, scripts, data, artifacts, docs, and Python configuration remain in place. Do not place React inside the Python package. Backend credentials remain server-side; browser configuration may contain only public settings such as an API base URL. Exact generated scaffold files and Node requirements should be checked when implementation is approved.

## 21. Suggested Frontend Technologies

| Choice | Reason |
| --- | --- |
| React + React DOM | Interactive form, response, and table rendering |
| Vite + React plugin | Small client application development/build setup; no SSR need demonstrated |
| TypeScript | Makes nullable tables, route/status unions, and API response shapes explicit; not a replacement for runtime validation |
| React Router, declarative mode | Two real URLs, browser history, and navigation; no framework/server mode needed |
| Native fetch | Adequate for three endpoints; check HTTP status and normalize errors centrally |
| Plain CSS | Sufficient for two pages; no component library or design system required |

JavaScript is possible, but TypeScript is preferable for this contract-focused integration. No Axios, advanced table library, charting package, or global state dependency is justified for V1.

These choices align with official guidance for a small client-built React app: [React build-from-scratch guidance](https://react.dev/learn/build-a-react-app-from-scratch), [Vite guide](https://vite.dev/guide/), [React Router declarative installation](https://reactrouter.com/start/declarative/installation), and [Fetch usage](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch). Select compatible versions and verify Node requirements at implementation time; no frontend dependencies were installed or selected as lockfile versions here.

## 22. Backend Work Required Before React

These are future tasks, not authorization to implement them.

| Classification | Capability | Why needed |
| --- | --- | --- |
| BLOCKER | HTTP host and assistant endpoint | Browser has no current transport |
| BLOCKER | State-to-DTO mapping and error contract | Full graph state is not a stable user response |
| BLOCKER | Verify actual graph outcomes and provider/database readiness | A UI cannot turn a failing workflow into success |
| BLOCKER for Data page | Structured approved table catalog and bounded records endpoint | No existing browse contract |
| BLOCKER for untrusted access | SQL enforcement and ETL execution/path/network trust review | Current execution capabilities must not be exposed blindly |
| REQUIRED | JSON-safe serialization | Database values/message content need explicit conversion |
| REQUIRED | Stable paging and ordering policy | Predictable bounded table reads |
| REQUIRED | Input validation and execution deadline policy | Bound requests and distinguish invalid input/failure |
| REQUIRED | Same-origin proxy or restricted CORS configuration | Browser connectivity under selected deployment |
| REQUIRED if ETL enabled | Machine-verifiable tool outcomes | Success prose alone is unreliable |
| OPTIONAL | Structured SQL assistant tables | Text-only assistant can precede this; Data page still needs structured rows |
| OPTIONAL | File manifest and download endpoint | Needed only if downloads enter scope |
| OPTIONAL / requirement-dependent | Authentication and roles | Required if deployment/access/data policy demands them |
| OPTIONAL / requirement-dependent | Background jobs, streaming, persistent conversations | Only if duration/product needs justify them |

Deferred code-review observations: `DatabaseService` connection/cleanup paths (RELIABILITY); additive message reducers with accumulated histories (CORRECTNESS); stringified query results and absent column metadata (API CONTRACT); unrestricted SQL/exec/path/network access (SECURITY); extraction JSON shape, pagination and absent timeout (RELIABILITY); transformation format omission and code-text cleaning (CORRECTNESS); optimistic tool success text (CORRECTNESS); `pydentic` declaration, transitive imports and Parquet engine availability (DEPENDENCIES). Review these in the approved next phase, without assuming historical bugs still exist. No fixes are included here.

## 23. V1 Scope

- Two pages and simple navigation.
- One assistant request at a time, normalized final answer, route/status, and safe errors.
- Optional assistant table only when reliable structured results exist.
- Approved PostgreSQL table selection and read-only paged records.
- Loading, empty, error, and basic accessible interaction states.
- Internal/local deployment only if explicitly approved and appropriate to the data/execution boundary.

Do not silently narrow the backend to SQL-only. Decide whether ETL is included in the first connected UI; if deferred, communicate that supported UI scope explicitly while retaining the backend implementation.

## 24. Features to Defer

Charts, analytics dashboards, editable tables, raw SQL consoles, uploads, arbitrary file browsing, file downloads, saved conversations, account systems without an access requirement, background job infrastructure, WebSockets, token streaming, advanced search/filtering, table virtualization, design systems, global state frameworks, and micro-frontends.

Data files and diagrams are not web assets by default. No direct exposure of repository paths or artifact directories is proposed.

## 25. Recommended Development Order

1. Approve V1 scope, trust boundary, tables/columns, ETL inclusion, and DTOs.
2. Perform a separately approved correctness review focused on request execution and reliable outcomes; assess exposure risks before web access.
3. Implement the smallest HTTP host and assistant normalization layer around the existing package, without reorganizing it.
4. Add approved catalog, bounded row reads, JSON serialization, error handling, and origin configuration.
5. Verify contracts with controlled test doubles and deterministic fixtures; live checks require separate authorization/configuration.
6. Scaffold the sibling React application using approved compatible tooling.
7. Build Assistant UI against the agreed contract, then connect it.
8. Build Data UI against the agreed catalog/page contract, then connect it.
9. Verify loading, empty, decline, dependency failure, stale response, and pagination behavior; make small UX improvements.

Frontend mock work can proceed once contracts are approved, but integration cannot be declared complete until backend capabilities exist. No full backend rewrite is required by this plan.

## 26. Open Questions

1. Is V1 local/internal for trusted users, or accessible to untrusted/public users?
2. Which PostgreSQL tables and columns may users inspect? Does any data require masking or access controls?
3. Should the Data page cover only database tables, or are extracted files a launch requirement?
4. Must ETL extraction/transformation be enabled in V1, or should its UI exposure wait for execution-boundary review?
5. Are SQL result tables essential in assistant responses at launch, or can text answers plus the Data page ship first?
6. Where will frontend/API run, and what request duration is acceptable before a timeout?
7. Are downloadable ETL files essential, or is verified completion text sufficient initially?
8. Should the current provider assignments remain? Source currently requires Anthropic routing even for OpenAI SQL processing; usable accounts/models were not verified.

These decisions affect contracts and exposure. They are not reasons to reorganize existing Python files.

## 27. Final Recommendation

**React needs:** an HTTP transport, normalized assistant response/errors, approved table catalog, paged structured rows, and safe JSON/origin handling.

**Already exists:** one Python package, a callable request entry point, router, SQL and ETL graphs, database schema/query primitives, extraction/transformation services, seed inputs, and graph-rendering scripts.

**Missing:** the web interface, browser DTOs, reliable typed outcomes, table-browsing contract, structured assistant query metadata, and any file-delivery contract. Live readiness and access safety remain unverified.

**Minimum frontend:** Assistant and Data pages, built-in React state, native fetch, a shared read-only table, and clear loading/empty/error states. Charts and persistent chat are unnecessary.

**Implementation order:** approve scope/contracts → focused backend readiness review → minimal API and contract verification → React Assistant → React Data → UX validation.

Stop here for approval. This document does not authorize API/frontend implementation, correctness fixes, dependencies, or further structural refactoring.
