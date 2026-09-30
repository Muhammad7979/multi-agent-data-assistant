# Company Policy RAG audit — 2026-09-29

Scope: trusted/local, single-process application. No new feature work. SQL and
ETL implementations remain unchanged; classification includes the additive Policy route.

## Validation evidence

- 78 Python tests passed, including real Chroma temporary persistence across
  processes, filtering, replacement/deletion, ingestion, document endpoints,
  source validation, and SQL/ETL graphs with mocked external dependencies.
- Five frontend contract/render tests passed. TypeScript and Vite build passed.
  No lint script is configured.
- Headless Chrome with synthetic HTTP responses passed document upload,
  validation, details, replacement, deletion/failure, empty/backend-error states,
  processing-to-ready polling, focus restoration and mobile navigation.
- Checked 1920×1080, 1366×768, 820×1180 and 390×844: no page-level horizontal
  overflow; tables scroll; the existing assistant panel fits the viewport.
- The existing assistant rendered SQL, ETL, Policy, Markdown, genuine returned
  source metadata and insufficient evidence. No second chat or route selector.

## Live provider checks

Only synthetic policy documents in temporary storage were sent to the configured
providers. No business SQL queries or ETL jobs were executed.

Actual router classifications:

| Question | Route |
| --- | --- |
| Which customers spent the most? | sql |
| Extract payments from an API and save CSV. | etl |
| What is our annual leave policy? | policy |
| Show reimbursement payments. | sql |
| What does company policy say about reimbursements? | policy |

Live OpenAI document/query embeddings ranked the known annual-leave policy first:
cosine distance 0.2749, versus instruction-like text at 0.6863 and unrelated
parking policy at 0.7954. Lower distance means closer. No threshold was invented.

With all three chunks available, the Policy Agent answered the known fact
(23 annual-leave days) with the correct document source. It returned insufficient
evidence and no sources for an unsupported dental-insurance allowance question.
The controlled instruction-like text did not change the answer to unlimited leave.
This is one adversarial sample, not proof of immunity to prompt injection.

An additional live FastAPI TestClient check used the default application composition:
POST document returned 201/ready; POST assistant returned 200, route policy,
23-day answer and genuine source; DELETE document returned 204. This exercised
the HTTP boundary, existing router, retrieval, and answer generation together.
Browser checks separately used synthetic responses. Temporary policy storage was removed.

## Small corrections

- Corrected failed-indexing UI wording to say an indexed version remains available:
  after activation followed by cleanup failure, it need not be the previous version.
- Updated current README documentation for the management page and frontend tests.
- Removed stale “future metadata layer” wording from Chroma service docstrings.

## Boundaries and remaining limitations

- Chroma uses public APIs only. Separate application-owned SQLite holds lifecycle
  metadata, not vectors or Chroma internals. One embedding factory and one vector
  service centralize configuration; no new provider settings were introduced.
- No hardcoded credentials, new machine-specific application paths, policy debug
  logs, duplicate retrieval implementation, or new audit dependencies were added.
- The shared LLM factory emits a non-blocking warning about `reasoning_effort`
  being supplied in `model_kwargs`; live answering succeeded. It was left unchanged
  to avoid unrelated SQL/ETL configuration changes.
- The UI currently requires plain upload filenames. This restriction and the
  10 MiB limit are documented. No document editing/download is implemented.
- Cross-store writes are not atomic. Generation activation, cleanup flags, explicit
  recovery and deletion deactivation mitigate interrupted operations. Uploads are
  synchronous; a disconnected browser does not cancel indexing. Use one API process.
- Exact quote checks establish provenance, not complete semantic entailment.
  Live examples do not establish broad model accuracy or universal injection safety.
- This is not an authentication or public-deployment security audit.

Decision: **B. CHROMA COMPANY POLICY RAG COMPLETE WITH MINOR NON-BLOCKING ISSUES**.
