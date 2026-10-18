# PolicyLens

A local compliance research workspace built with **React, Python/FastAPI, and SQLite**. Add your policies, assess transactions, ask policy questions, and record human reviews with the original evidence attached.

No Docker, Milvus, GPU, embedding downloads, paid API requirement, demo decisions, provider switching, or fabricated fallback answers.

## Start locally

Install **Python 3.11+** and **Node.js 22.12+**, then run from the repository root:

```sh
python run.py
```

The launcher creates `.venv`, installs dependencies, builds the React app, and serves both frontend and API at **http://127.0.0.1:8000**. Dependency installation is skipped on subsequent starts unless the manifests change. Stop with Ctrl+C.

1. Create a [free Groq API key](https://console.groq.com/keys).
2. Set `GROQ_API_KEY` in `backend/.env` (created by the launcher). Restart after changing it.
3. Open **Data sources → Connect & sync** to fetch the complete official OFAC SDN feed.
4. Add your actual compliance documents in **Policy library**.
5. Run an evaluation or ask the **Policy assistant** a question.

The app opens with an empty policy library and assessment history. It can manage documents without an AI key; AI operations explicitly require one. Keys stay in the backend and are excluded from Git. Never place API keys in frontend code or chat messages.

## What works

- **Policy library:** searchable titles/topics; paste text or upload UTF-8 TXT, text-based PDF, or DOCX (including tables). Maximum 5 MB and 300,000 characters; PDFs are limited to 300 pages. Scanned PDFs need OCR before uploading.
- **Policy updates:** new version numbers replace the searchable current document. Existing assessments preserve their original policy excerpts and citations.
- **Retrieval:** SQLite FTS5 with BM25 ranking is the primary retrieval engine. It is lexical search, not semantic vector search; use terminology present in your documents. No matching evidence means no AI answer.
- **Transaction assessments:** validated monetary amounts, live USD reference conversion, full OFAC SDN name/alias screening, schema-validated Groq output, and citations whose IDs and quotations are checked against the retrieved text.
- **Policy assistant:** document-grounded Q&A, topic filters, verified quotes, and visible limitations.
- **Decision history:** paginated records, search/filter within the displayed page, immutable original AI assessments, append-only human review records, and downloadable audit JSON containing inputs, model, quotes, retrieved passages, sanctions snapshot checksum/time, and exchange-rate evidence.
- **Workspace:** real counts, audit activity, actionable setup, mobile navigation, keyboard labels/focus, and persistent light/dark appearance.

## Free web integrations

| Capability | Provider | Authentication / limits |
| --- | --- | --- |
| AI analysis | [Groq](https://console.groq.com/docs/rate-limits), default `openai/gpt-oss-20b` | Free-tier key required; account/model limits apply. No automatic paid upgrade or alternate provider. |
| Sanctions evidence | [U.S. Treasury OFAC](https://ofac.treasury.gov/sanctions-list-service) official SDN XML feed | No key. Downloads every primary entry and alias; manually refresh in Data sources. |
| Exchange rates | [Frankfurter v2](https://frankfurter.dev/) | Free, no key. Latest daily USD reference rate fetched for each non-USD evaluation. |

OFAC snapshots are valid for 24 hours after successful download by default. A stale/missing snapshot stops assessments until you sync. Failed syncs never replace the last downloaded snapshot or reset its age. The UI displays sync times and record counts. Download publication dates and SHA-256 checksums are retained in assessment evidence.

Non-USD evaluations stop if a valid reference rate is unavailable, older than seven days, or future-dated. USD uses the mathematical identity rate of 1. Dates are reference dates, not execution quotes. Failed AI requests, rate limits, incomplete responses, invalid scores, and unverified quotations return explicit errors and do not save decisions. A potential OFAC match cannot receive an acceptable AI verdict.

Groq output uses [strict structured outputs](https://console.groq.com/docs/structured-outputs). Set `GROQ_MODEL` only to a model supporting that capability; unsupported/retired models produce an explicit provider error, never an alternate model or canned assessment.

The previous hardcoded FATF country lists and RBI/EU scraping claims have been removed. Import the current policies you actually use; this app does not claim coverage for sources it does not retrieve.

## Configuration

Copy `backend/.env.example` to `backend/.env` if starting manually:

```dotenv
GROQ_API_KEY=your_key_here
GROQ_MODEL=openai/gpt-oss-20b
SANCTIONS_MAX_AGE_HOURS=24
# DATABASE_PATH=/absolute/path/to/policylens-v2.db
```

The default database lives at `backend/data/policylens-v2.db`, resolved relative to the backend source rather than your shell directory. Back up the database with SQLite's backup API or stop the server before copying the database and its WAL files. The data folder and all local secrets are excluded from Git.

This version uses a **new v2 database**, not the legacy schema or checked-in sample decisions. Legacy code/data remain recoverable from Git history. There is no implicit import of old or synthetic records. API response shapes have changed to match the new React client.

## Development

Backend (repository root):

```sh
python -m venv .venv
# Windows
.venv\Scripts\python -m pip install -r backend/requirements-dev.txt
cd backend
..\.venv\Scripts\python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
# macOS/Linux equivalent: ../.venv/bin/python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Frontend (another terminal):

```sh
cd frontend
npm ci
npm run dev
```

Open **http://127.0.0.1:3000**. Vite proxies `/api` to Python. Production builds are served directly by FastAPI on port 8000; frontend calls use the same origin. API documentation is at **http://127.0.0.1:8000/docs**.

Checks (repository root; replace the Python executable for your platform):

```sh
.venv\Scripts\python -m pytest
.venv\Scripts\python -m ruff check backend run.py
cd frontend
npm test
npm run lint
npm run build
npm audit
```

Backend tests use isolated temporary SQLite databases and mocked provider HTTP responses, so CI requires no key or network feed. React tests cover onboarding, navigation, theme, policy input, offline errors, evaluation failures, and cited answers. CI runs both suites and builds the frontend.

## Scope

This is a **single-user local application**. It intentionally binds to loopback and has no user authentication or multi-tenant isolation. Do not expose it to the public internet without adding authentication, authorization, HTTPS, and operational controls. No cloud hosting or payments are configured.

AI scores are estimates rather than calibrated probabilities. An `acceptable` result is advisory against supplied policies, never regulatory clearance or payment approval. Screening covers OFAC SDN names/aliases using normalized name similarity ≥ 0.88; it does not cover beneficial ownership, every sanctions list, or all transliterations. Human review is required. A lack of matches is not clearance.

Relevant policy excerpts, questions, transaction details, and screening results are sent to Groq. Review its data terms before using confidential material. The app never executes transfers. Audit JSON is the supported report format; the old PDF report, automatic batch re-evaluation, and background scraping/scheduler paths were removed with their unreliable infrastructure.
