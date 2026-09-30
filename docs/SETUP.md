# Setup and development

Start with the [root README](../README.md) for a short introduction. Run backend commands from the repository root.

## Requirements

- Python 3.14 (the series selected by `.python-version`; the project declares Python 3.14 or newer).
- `uv` for Python dependencies and commands.
- Node.js 22.12+ and npm for the React frontend.
- PostgreSQL for business-data browsing and SQL questions.
- Anthropic and OpenAI API credentials, access to the configured models, and provider credits for the corresponding AI operations.

The router uses Anthropic even when it selects SQL or Policy. SQL and Policy use OpenAI; Policy also uses OpenAI embeddings. Local Chroma and SQLite do not require separate servers. Network access and writable local storage are needed for the relevant operations.

## Environment configuration

Create a `.env` file in the repository root with your own values:

```dotenv
ANTHROPIC_API_KEY=replace_with_your_key
OPENAI_API_KEY=replace_with_your_key
DB_HOST=127.0.0.1
DB_PORT=5432
DB_DATABASE=replace_with_your_database
DB_USERNAME=replace_with_your_database_user
DB_PASSWORD=replace_with_your_database_password
```

These are placeholders, not working credentials. The application does not create a PostgreSQL database or user for you. Set up the intended database and use credentials that can access it.

The API loads `.env` at startup, preserving existing process environment values. Database settings are read when database work is requested. Python hosts calling `run_request()` directly must arrange environment loading themselves.

`.env` is ignored by Git. There is no backend `.env.example`; create the file yourself. Never put credentials in frontend `VITE_*` variables, which are public browser configuration.

## Install and start

From the repository root:

```powershell
uv sync --locked
uv run uvicorn data_agent.api:app --host 127.0.0.1 --port 8000
```

Leave that terminal running. In a second terminal, starting at the repository root:

```powershell
cd frontend
npm ci
npm run dev
```

Open **http://127.0.0.1:5173**. The frontend development server forwards `/api` requests to the backend on port 8000. API endpoint documentation is available at **http://127.0.0.1:8000/docs**. Stop each server with Ctrl+C in its terminal.

These commands start the application; they do not seed PostgreSQL, upload policies, or verify provider access. Both servers bind to localhost. This remains a trusted/local application: SQL checking is model-based, and ETL can execute generated Python without a sandbox.

## Optional sample database

The repository includes ride-service CSVs for users, vehicles, rides, payments, and ratings. To load them into your configured disposable development database:

```powershell
uv run python scripts/seed_database.py
```

**This script runs `TRUNCATE ... CASCADE` before reloading the seed tables. It can remove existing and dependent data. Use it only against the database you intend to reset.** It is not a required startup command for an already populated database.

## Frontend routes and API URL

| Route | Purpose |
| --- | --- |
| `/` | Home: available datasets and honest provider-reporting states |
| `/data` | Dataset directory |
| `/data/:tableId` | Shared table page; Payments uses `/data/public.payments` when available |
| `/policy` | Upload and manage company documents |
| `/etl/files` | Saved ETL outputs |
| `/etl/files/:fileId` | File details and bounded preview |
| `/assistant` | Opens the global assistant and redirects to Home |

The sidebar's dataset links come from the API catalog for the approved development tables. Missing tables do not appear. The assistant's draft and visible response survive navigation and closing the panel, but reset on reload; each submitted question is independent.

The frontend API base URL defaults to `/api`. For a different backend, copy `frontend/.env.example` to `frontend/.env.local` and set `VITE_API_BASE_URL`, including the `/api` suffix. Restart Vite after changing it; a built frontend needs a rebuild.

Direct cross-origin requests also require `DATA_AGENT_CORS_ORIGINS`: a comma-separated list of explicit frontend origins. Set it in the server process environment before starting Uvicorn, because CORS configuration is read when the app is constructed, before startup loads `.env`. Setting it only in `.env` is insufficient. For example, in PowerShell:

```powershell
$env:DATA_AGENT_CORS_ORIGINS = "http://127.0.0.1:5173"
```

Restart the API after changing it. A wildcard is rejected. The default local proxy needs no separate CORS setting.

## Local storage

ETL outputs default to `var/etl/outputs/`, with a catalog at `var/etl/metadata.sqlite3`. Policy uses `var/policy/` for originals, its document catalog, and Chroma persistence. These defaults are ignored by Git.

`ETL_STORAGE_ROOT` and `POLICY_STORAGE_ROOT` override their respective roots. Relative settings use the application data root: the repository root in a recognized checkout, with a working-directory fallback when installed. Keep custom runtime locations outside version control too.

See the [ETL guide](ETL_AGENT.md) for file naming and persistence, and the [Policy guide](POLICY_AGENT.md) for embedding, chunking, and retrieval settings. Use one owning application process per Policy storage root; do not run independent ingestion against the active root.

## Tests and development commands

Backend checks, from the repository root:

```powershell
uv run python -m unittest discover -s tests -v
```

Frontend checks, from `frontend/`:

```powershell
npm test
npm run build
npx tsc --noEmit
```

The build already includes TypeScript checking. The standalone type command is useful when you do not need a bundle. No frontend lint script is configured. Build output is written to `frontend/dist/`; `npm run preview` serves it locally and still needs the backend for API requests.

Tests using fake providers verify application behavior, not live model quality or credentials. The ETL end-to-end test uses deterministic provider responses and a local HTTP source, creates real files, and checks persistence through separate backend processes.

For UI checks with deliberately synthetic fixture data, use this command **instead of** the normal API command:

```powershell
uv run python -m uvicorn tests.ui_fixture:app --host 127.0.0.1 --port 8000
```

This is a development fixture, not the real application or a source of company data.

## Other commands and their effects

| Command from repository root | What it does |
| --- | --- |
| `uv run data-agent` or `uv run python -m data_agent` | Runs the fixed Pokemon extraction example and prints internal graph state; it is not an interactive question prompt and can call providers and write files |
| `uv run python scripts/inspect_database.py` | Reads configured PostgreSQL schema/sample data and writes or replaces `test_schema_detail.txt` |
| `uv run python scripts/generate_graphs.py` | Builds graph definitions and renders PNGs under `artifacts/graphs/`; provider client configuration and external rendering access may be needed, but agent workflows are not invoked |

## Troubleshooting

- **PowerShell blocks npm or npx:** use `npm.cmd` and `npx.cmd` instead of the `.ps1` shims.
- **Port 5173 is busy:** stop the other development server or run `npm run dev -- --port 5174`. Open the port printed by Vite. The backend proxy still targets port 8000.
- **API requests fail:** check that the backend is running on port 8000 and that the API base URL includes `/api`.
- **SQL or table pages fail:** check PostgreSQL availability, `DB_*` settings, and the intended tables. Starting the API alone does not populate the database.
- **AI requests fail:** check both provider credentials, model access, and credits. Configured models are selected in `src/data_agent/llm.py`.
- **Policy indexing fails:** check the returned status/error, accepted file format, extractable text, and OpenAI access. Existing collection settings must match embedding and chunking settings; changing environment variables does not migrate stored vectors. Tokenizer data may download on first use.
- **ETL extraction fails:** the current extractor expects JSON with a `results` key. It is not an adapter for arbitrary APIs. CSV and JSON Lines are supported; Parquet writing also requires an optional pandas engine such as `pyarrow` or `fastparquet`, neither declared as a direct project dependency.
- **A request times out:** backend work may still be running. Check document status or ETL Files before repeating a write operation.

A future static frontend host needs a single-page-application fallback for direct route refresh and a route to the Python API. The current local setup is not a public deployment guide.

Return to the [documentation index](README.md).
