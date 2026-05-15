# LibraryMind

> AI-powered intelligent library assistant — multi-provider RAG backend.

LibraryMind is a production-grade FastAPI service that lets patrons search a library catalogue by meaning rather than keywords, ask grounded questions about the collection, chat with an AI librarian that remembers context, and submit support tickets that auto-classify by category, priority, and sentiment. It is the capstone for Module 10 of the AmaliTech Python Backend & AI training programme.

The system is built around a strict four-layer architecture (API → Service → AI Provider → Infrastructure), a multi-provider AI failover chain (OpenAI, Anthropic, AmaliAI), ChromaDB for vector storage, Redis for caching, and a token-bucket rate limiter — with first-class observability via structured logging and a `/health` endpoint that exposes daily spend in USD.

## Table of contents

- [Architecture overview](#architecture-overview)
- [Project status](#project-status)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Local development](#local-development)
- [Docker](#docker)
- [Testing](#testing)
- [Linting & formatting](#linting--formatting)
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
| 0     | Environment, tooling, documentation                      | ✅ in review    |
| 1     | Multi-provider AI layer with failover                    | ⏳ pending      |
| 2     | Cache, rate limiter, usage tracker                       | ⏳ pending      |
| 3     | Knowledge base + embeddings + vector store               | ⏳ pending      |
| 4     | RAG engine                                               | ⏳ pending      |
| 5     | AI librarian chatbot                                     | ⏳ pending      |
| 6     | Ticket classification + review summarisation             | ⏳ pending      |
| 7     | REST API + endpoint wiring                               | ⏳ pending      |
| 8     | Smoke tests, validation, reflection                      | ⏳ pending      |

## Quick start

```bash
git clone https://github.com/calebgisa/library-mind.git
cd library-mind
cp .env.example .env
# Open .env and add at least one provider API key.
make install-dev
make run
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
| `RAG_RELEVANCE_THRESHOLD` | Drop results below this similarity score                       | `0.25`                           |
| `CHROMA_PERSIST_DIR`      | Local directory for ChromaDB data                              | `./data/chroma`                  |
| `LOG_FORMAT`              | `json` for production, `console` for dev                       | `json`                           |

At least one of `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `AMALIAI_API_KEY` must be set — the application refuses to start otherwise.

## Local development

```bash
make install-dev        # create .venv/, install all deps, install pre-commit hooks
make run                # uvicorn with auto-reload
make seed               # seed the vector store from app/data/books.json  (Phase 3+)
```

## Docker

```bash
make docker-up          # build images, start api + redis
make docker-logs        # tail logs
make docker-down        # stop and remove volumes
```

The compose file mounts the source tree read-only so uvicorn's `--reload` picks up changes without rebuilding the image.

## Testing

```bash
make test               # full suite with coverage
make test-fast          # stop on first failure
make cov                # generate HTML coverage report
```

The test suite ships empty in Phase 0 (configuration is verified by `make check` instead). Tests land in Phase 8.

## Linting & formatting

```bash
make lint               # Ruff with auto-fix
make format             # Ruff format + Black
make typecheck          # Mypy
make check              # all of the above in CI-style read-only mode
```

Pre-commit hooks run the same checks on every commit. Run `pre-commit run --all-files` to apply them to the whole tree.

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
├── scripts/              # Seeding & smoke tests
├── tests/                # Pytest suite
├── docs/                 # PRD, ERD, API reference, architecture
├── frontend/             # Placeholder for future React client
├── .github/workflows/    # CI
├── docker-compose.yml    # api + redis dev stack
├── Dockerfile            # Multi-stage build
├── Makefile              # Developer task runner
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
| `Agent.md` *(git-ignored)*    | Instructions for AI coding agents                         |
| `Guidelines.md` *(git-ignored)* | Engineering rulebook                                    |
| `handoff.md` *(git-ignored)*  | Phase-by-phase progress log + continuation prompt         |

## License

MIT. See [`LICENSE`](LICENSE).
