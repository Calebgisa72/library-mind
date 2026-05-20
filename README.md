# LibraryMind

> AI-powered intelligent library assistant — multi-provider RAG backend.

LibraryMind is a production-grade FastAPI service that lets patrons search a library catalogue by meaning rather than keywords, ask grounded questions about the collection, chat with an AI librarian that remembers context, and submit support tickets that auto-classify by category, priority, and sentiment. It is the capstone for Module 10 of the AmaliTech Python Backend & AI training programme.

The system is built around a strict four-layer architecture (API → Service → AI Provider → Infrastructure), a multi-provider AI failover chain (OpenAI, Anthropic, AmaliAI), ChromaDB for vector storage, Redis for caching, and a token-bucket rate limiter — with first-class observability via structured logging and a `/health` endpoint that exposes daily spend in USD.

## Table of contents

- [Architecture overview](#architecture-overview)
- [Project status](#project-status)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Commands](#commands)
- [API at a glance](#api-at-a-glance)
- [Sample requests](#sample-requests)
- [Project structure](#project-structure)
- [Branch & PR strategy](#branch--pr-strategy)
- [Troubleshooting](#troubleshooting)
- [Development standards](#development-standards)
- [Documentation map](#documentation-map)

## Architecture overview

```
┌──────────────────────────────────────────────────────────────────┐
│ Layer 1: API           FastAPI routers · Pydantic validation     │
├──────────────────────────────────────────────────────────────────┤
│ Layer 2: Services      RAG · Chatbot · Classifier · Summariser   │
├──────────────────────────────────────────────────────────────────┤
│ Layer 3: AI Providers  OpenAI · Anthropic · AmaliAI · failover   │
├──────────────────────────────────────────────────────────────────┤
│ Layer 4: Infrastructure  ChromaDB · Redis · Rate Limiter · Usage │
└──────────────────────────────────────────────────────────────────┘
```

Full diagrams and the request flow live in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). The product spec is in [`docs/PRD.md`](docs/PRD.md), the data model in [`docs/ERD.md`](docs/ERD.md), and the API contract in [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md).

## Project status

The project is delivered in phases. Each phase is gated on review before the next begins.

| Phase | Scope                                                    | Status         |
|-------|----------------------------------------------------------|----------------|
| 0     | Environment, tooling, documentation                      | ✅ complete     |
| 1     | Multi-provider AI layer with failover                    | ✅ complete     |
| 2     | Cache, rate limiter, usage tracker                       | ✅ complete     |
| 3     | Knowledge base + embeddings + vector store               | ✅ complete     |
| 4     | RAG engine                                               | ✅ complete     |
| 5     | AI librarian chatbot                                     | ✅ complete     |
| 6     | Ticket classification + review summarisation             | ✅ complete     |
| 7     | REST API + endpoint wiring                               | ✅ complete     |
| 8     | Smoke tests, validation, reflection                      | ✅ complete     |

## Quick start

```bash
# 1. Clone the repository and enter it
git clone https://github.com/calebgisa/library-mind.git
cd library-mind

# 2. Copy the environment template and add at least one provider API key
cp .env.example .env
# (Windows PowerShell: Copy-Item .env.example .env)

# 3. Create the virtual environment, install dependencies, and install pre-commit hooks
python -m venv .venv
# Activate the venv (see the Commands section below for the exact line for your shell)
python -m pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"
pre-commit install --install-hooks

# 4. Run the API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be running on `http://localhost:8000`. Swagger UI is at `/docs`, ReDoc at `/redoc`.

## Configuration

All settings are read from environment variables (with a `.env` file as the default source for local development). The full list is documented in [`.env.example`](.env.example). The most important variables:

| Variable                  | Purpose                                                        | Default                          |
|---------------------------|----------------------------------------------------------------|----------------------------------|
| `PRIMARY_PROVIDER`        | Which provider is tried first (`openai`/`anthropic`/`amaliai`) | `openai`                         |
| `OPENAI_API_KEY`          | OpenAI credentials                                             | —                                |
| `ANTHROPIC_API_KEY`       | Anthropic credentials                                          | —                                |
| `AMALIAI_API_KEY`         | AmaliAI credentials                                            | —                                |
| `REDIS_URL`               | Redis connection string                                        | `redis://localhost:6379/0`       |
| `RATE_LIMIT_PER_MINUTE`   | Token bucket refill rate                                       | `60`                             |
| `RAG_TOP_K`               | Top-K vectors retrieved from ChromaDB                          | `4`                              |
| `RAG_RELEVANCE_THRESHOLD` | Similarity threshold (0=unrelated, 1=identical)                | `0.35`                           |
| `BUDGET_DAILY_LIMIT_USD`  | Soft daily cost cap (`0.0` disables; tracking still happens)   | `0.0`                            |
| `CHROMA_PERSIST_DIR`      | Local directory for ChromaDB data                              | `./data/chroma`                  |
| `LOG_FORMAT`              | `json` for production, `console` for dev                       | `json`                           |

At least one of `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `AMALIAI_API_KEY` must be set — the application refuses to start otherwise.

## Commands

LibraryMind has no task runner — we use raw, cross-platform commands so the workflow is identical whether you're on Linux, macOS, or Windows. Every command below assumes you've **activated the virtual environment** first (see *Activate the virtual environment* immediately below). Once activated, your shell prompt should show `(.venv)`.

### Activate the virtual environment

The activation line is the only command that differs by platform. Run it once per terminal session.

**Linux / macOS (bash, zsh):**

```bash
source .venv/bin/activate
```

**Windows (PowerShell):**

```powershell
.\.venv\Scripts\Activate.ps1
```

**Windows (cmd):**

```cmd
.venv\Scripts\activate.bat
```

If PowerShell rejects the script with an *"execution of scripts is disabled"* error, run this **once** per machine and retry:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

To leave the virtual environment, run `deactivate` from any shell. Everything below assumes you stay inside the activated venv.

### One-time setup

| Command                                                | What it does                                                                  |
|--------------------------------------------------------|-------------------------------------------------------------------------------|
| `python -m venv .venv`                                 | Creates the project's virtual environment under `./.venv/`.                   |
| `python -m pip install --upgrade pip setuptools wheel` | Upgrades base packaging tools inside the venv.                                |
| `pip install -e ".[dev]"`                              | Installs LibraryMind in editable mode plus all development dependencies (Ruff, Black, Mypy, Pytest, pre-commit, etc.). |
| `pre-commit install --install-hooks`                   | Wires the pre-commit hooks into `.git/hooks/` so every commit is auto-checked.|

### Running the application

| Command                                                                            | What it does                                                                  |
|------------------------------------------------------------------------------------|-------------------------------------------------------------------------------|
| `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`                         | Starts the FastAPI server with auto-reload. Swagger UI at `/docs`, ReDoc at `/redoc`. |
| `python -m app`                                                                    | Alternative entrypoint (uses the same uvicorn invocation under the hood).     |

### Quality gates — read-only mode (run before every PR)

| Command                                  | What it does                                                                 |
|------------------------------------------|------------------------------------------------------------------------------|
| `ruff check app scripts tests`           | Lint — style, imports, security smells, common bugs. Fails CI on any issue.  |
| `black --check app scripts tests`        | Verifies code is already formatted. Fails CI if not. No auto-fix.            |
| `mypy app`                               | Strict static type checking on the application package.                      |
| `pre-commit run --all-files`             | Runs every configured pre-commit hook against the whole tree.                |

### Quality gates — auto-fix mode (run while developing)

| Command                                  | What it does                                                                 |
|------------------------------------------|------------------------------------------------------------------------------|
| `ruff check --fix app scripts tests`     | Lint with auto-fix; fixes import order, simple style issues, etc.            |
| `ruff format app scripts tests`          | Formats the codebase via Ruff's formatter.                                   |
| `black app scripts tests`                | Formats via Black (final pass — Black is the source of truth for layout).    |

### Testing

| Command                                          | What it does                                                                |
|--------------------------------------------------|-----------------------------------------------------------------------------|
| `pytest`                                         | Runs the full test suite with coverage (configured in `pyproject.toml`).    |
| `pytest -x`                                      | Stops at the first failure — useful when iterating on a single bug.         |
| `pytest -k <pattern>`                            | Runs only tests whose name matches the pattern (e.g. `pytest -k rag`).      |
| `pytest tests/providers/`                        | Runs only the provider tests (replace with any path).                       |
| `pytest --cov-report=html`                       | Generates an HTML coverage report; open `htmlcov/index.html` in a browser.  |

The test suite grows phase by phase and is consolidated in Phase 8. Phases 0–2 currently have 105 tests (all passing).

### Phase-specific commands

| Command                                          | When you need it                                                            |
|--------------------------------------------------|-----------------------------------------------------------------------------|
| `python -m scripts.seed_vector_store`            | Phase 3+: reads `app/data/books.json`, embeds each book, upserts into ChromaDB. |
| `python -m scripts.smoke_test`                   | Phase 8: end-to-end smoke test against a running server (10 lab scenarios). |

### Smoke test

The smoke test validates every Part 8 scenario against a live server. Run it after starting
the application:

```bash
# Terminal 1 (venv active) — start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 (venv active) — run the smoke test
python -m scripts.smoke_test
```

The script exits **0** when all 10 scenarios pass, **1** when any fail. It prints a
colour-coded pass/fail table to stdout. The base URL can be overridden:

```bash
LIBRARYMIND_BASE_URL=http://localhost:8000 python -m scripts.smoke_test
```

**Scenario 10 (provider fallback)** is partially automated: the smoke test verifies that
≥2 providers are configured in `/health`. The actual live-failover test (setting the primary
key to an invalid value and confirming the fallback provider responds) requires a server
restart with a modified `.env`; see *Troubleshooting* for instructions.

### Docker

Docker Desktop on Windows and Docker Engine on Linux/macOS both ship the `docker` and `docker compose` commands natively — these commands are platform-identical and **do not** require the venv.

| Command                              | What it does                                                                        |
|--------------------------------------|-------------------------------------------------------------------------------------|
| `docker compose up --build -d`       | Builds the API image and starts both services (`api` + `redis`) in the background.  |
| `docker compose ps`                  | Shows the status of both services.                                                  |
| `docker compose logs -f`             | Tails the combined logs of both services until you press Ctrl-C.                    |
| `docker compose logs -f api`         | Tails only the API service logs.                                                    |
| `docker compose down`                | Stops both services but keeps their volumes (ChromaDB data persists).               |
| `docker compose down -v`             | Stops both services **and removes volumes** — ChromaDB and Redis are wiped clean.   |
| `docker compose build --no-cache`    | Rebuilds the API image from scratch (use after dependency or Dockerfile changes).   |

The compose file mounts the source tree read-only so uvicorn's `--reload` picks up code changes without rebuilding the image.

### Housekeeping

| Command (Linux / macOS)                                                  | What it does                                |
|--------------------------------------------------------------------------|---------------------------------------------|
| `rm -rf .mypy_cache .ruff_cache .pytest_cache htmlcov .coverage`         | Removes tool caches.                        |
| `find . -type d -name __pycache__ -exec rm -rf {} +`                     | Removes Python bytecode caches.             |

| Command (Windows PowerShell)                                                          | What it does                     |
|---------------------------------------------------------------------------------------|----------------------------------|
| `Remove-Item -Recurse -Force .mypy_cache, .ruff_cache, .pytest_cache, htmlcov, .coverage -ErrorAction SilentlyContinue` | Removes tool caches.             |
| `Get-ChildItem -Recurse -Directory -Filter __pycache__ \| Remove-Item -Recurse -Force` | Removes Python bytecode caches.  |

## API at a glance

| Method | Path                  | Purpose                                |
|--------|-----------------------|----------------------------------------|
| POST   | `/search/books`       | Semantic catalogue search              |
| POST   | `/search/ask`         | RAG Q&A with source citations          |
| POST   | `/chat`               | Multi-turn conversational chatbot      |
| POST   | `/classify/ticket`    | Structured ticket classification       |
| POST   | `/summarise/reviews`  | Aggregate review analysis              |
| GET    | `/health`             | Status + daily spend + request count   |

Full payload schemas, error envelopes, and status codes: [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md).

## Sample requests

Endpoints are wired in Phase 7. The shapes below match the planned contract.

```bash
# Semantic search
curl -X POST http://localhost:8000/search/books \
  -H "Content-Type: application/json" \
  -d '{"query": "desert planet adventure", "limit": 5}'

# RAG Q&A
curl -X POST http://localhost:8000/search/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What sci-fi books do you have about desert planets?"}'

# Chat
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"conversation_id": "c_demo", "message": "Recommend a thriller."}'

# Ticket classification
curl -X POST http://localhost:8000/classify/ticket \
  -H "Content-Type: application/json" \
  -d '{"text": "My card isn'\''t working at self-checkout and I'\''m frustrated."}'

# Review summarisation
curl -X POST http://localhost:8000/summarise/reviews \
  -H "Content-Type: application/json" \
  -d '{"reviews": ["I couldn'\''t put it down.", "Pacing dragged but ending was excellent."]}'

# Health
curl http://localhost:8000/health
```

The Python equivalent with `httpx`:

```python
import httpx

with httpx.Client(base_url="http://localhost:8000") as client:
    r = client.post("/search/ask", json={"question": "Recommend a classic romance."})
    r.raise_for_status()
    print(r.json())
```

## Project structure

```
library-mind/
├── app/                  # Application package (see docs/ARCHITECTURE.md)
│   ├── api/              #   FastAPI routers (Phase 7)
│   ├── services/         #   Business logic (Phases 3–6)
│   ├── providers/        #   Multi-provider AI layer (Phase 1)
│   ├── infrastructure/   #   Cache, rate limiter, usage tracker (Phase 2)
│   ├── prompts/          #   Versioned prompt templates (Phases 4–6)
│   ├── schemas/          #   Pydantic models
│   ├── core/             #   Settings, logging, exceptions  ✓ Phase 0
│   └── data/             #   Seed catalogue (books.json)
├── scripts/              # Seeding & smoke tests
├── tests/                # Pytest suite
├── docs/                 # PRD, ERD, API reference, architecture, CI guide
├── frontend/             # Placeholder for future React client
├── .github/workflows/    # CI (currently disabled — see docs/CI.md)
├── docker-compose.yml    # api + redis dev stack
├── Dockerfile            # Multi-stage build
├── pyproject.toml        # Deps, lint, type, test config
├── .env.example          # Documented configuration template
└── README.md             # You are here
```

## Branch & PR strategy

We use trunk-based development with feature branches and conventional commits.

- `main` is always deployable. Direct pushes are not permitted.
- Phase branches use the prefix matching the change type: `chore/phase-0-setup`, `feat/phase-1-providers`, `feat/phase-4-rag-engine`, and so on.
- Commits follow Conventional Commits: `feat(rag): add relevance threshold filter`.
- PR titles follow the same convention. The PR template (`.github/PULL_REQUEST_TEMPLATE.md`) ships with a checklist that must be ticked before merge.

## Troubleshooting

**"No AI provider configured"** at startup — set at least one of `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `AMALIAI_API_KEY` in your `.env` file.

**Redis connection errors** in logs — these are expected and harmless when Redis is not running. The application falls back to a no-op cache and continues serving requests; only response latency suffers.

**Slow first request after seeding** — ChromaDB's HNSW index loads lazily; the first query rebuilds it. Subsequent queries hit the warm index.

**Stale cache after editing a prompt** — bump the version prefix in the cache-key helper (see `docs/ARCHITECTURE.md` § Caching Strategy) or run `redis-cli FLUSHDB` against the dev Redis.

**Embedding dimension mismatch** after switching embedding models — delete `./data/chroma` and re-seed. Embeddings from different models live in different vector spaces; ChromaDB will not silently coerce them.

**GitHub Actions not running** — CI is currently disabled because of a GitHub billing block. The workflow file is preserved at `.github/workflows/ci.yml.disabled`. To re-enable, rename it back to `ci.yml` and push. See [`docs/CI.md`](docs/CI.md) for details. All quality gates the workflow enforces are also available locally — see the [`Commands`](#commands) section.

**Confused by similarity scores vs distance** — ChromaDB returns cosine *distance* (lower is better), but the API returns cosine *similarity* (higher is better). The RAG engine converts internally; `RAG_RELEVANCE_THRESHOLD` is always a similarity threshold. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) § *Distance vs Similarity*.

## Development standards

We aim for production-grade code throughout. The minimum bar:

- Every public function has a docstring explaining intent (not implementation).
- Every comment explains *why*, not *what*.
- No secrets in source. No hardcoded URLs, model names, or thresholds — all configuration goes through `app.core.settings`.
- All input is validated by Pydantic at the boundary; domain invariants are validated in services.
- No dead code, no commented-out blocks, no `print()` calls in app code.
- All async I/O uses async libraries; no thread-pool wrappers around blocking SDKs.
- Errors map to typed domain exceptions, not bare `Exception`.

The detailed engineering rulebook lives in `Guidelines.md` (git-ignored, internal).

## Documentation map

| File                          | What's in it                                              |
|-------------------------------|-----------------------------------------------------------|
| `README.md`                   | This file — overview, setup, command reference            |
| `docs/PRD.md`                 | Product vision, goals, non-goals, requirements            |
| `docs/ERD.md`                 | Conceptual data model + storage decisions                 |
| `docs/API_REFERENCE.md`       | Endpoint contracts, payloads, error envelopes             |
| `docs/ARCHITECTURE.md`        | Layered design, diagrams, flows, strategy per concern     |
| `docs/CI.md`                  | CI status (currently disabled) + re-enable instructions   |
| `Agent.md` *(git-ignored)*    | Instructions for AI coding agents                         |
| `Guidelines.md` *(git-ignored)* | Engineering rulebook                                    |
| `handoff.md` *(git-ignored)*  | Phase-by-phase progress log + continuation prompt         |

## License

MIT. See [`LICENSE`](LICENSE).
