# Architecture — LibraryMind

## 1. Architectural Style

LibraryMind uses a strict four-layer architecture: **API → Service → AI Provider → Infrastructure**. Each layer depends only on the layer below; reverse imports are forbidden. The pattern is conventional for stateless, request/response backends and offers three practical benefits for this lab: each layer is independently testable (mock the AI provider once and you've made every service testable), business logic is sealed away from transport details (so the same service could be exposed over gRPC or a CLI without change), and vendor dependencies are isolated to one layer (swapping OpenAI for Anthropic is a single-file change).

We chose a layered architecture over alternatives — hexagonal/ports-and-adapters, clean architecture, vertical slices — because the lab is small enough that the extra ceremony of hexagonal architecture would be noise, but big enough that vertical slices would scatter cross-cutting concerns. Layered is the right point on the curve.

Scalability considerations: every layer is stateless except for the in-memory stores in the infrastructure layer (rate limiter token bucket, usage records, conversation history). Those are intentionally process-local because the lab assumes single-instance deployment; the abstractions wrap them so a Redis-backed implementation is a swap-not-rewrite when horizontal scaling matters. ChromaDB is embedded in-process; a future deployment would point at a remote Chroma server with no API change.

## 2. Architecture Diagram

```mermaid
flowchart TD
    Client[HTTP Client] --> Mw

    subgraph API["Layer 1 — API"]
        Mw[Middleware<br/>CORS · Request-ID · Errors] --> Routers
        Routers[Routers<br/>search · chat · classify<br/>summarise · health]
    end

    Routers --> Services

    subgraph Services["Layer 2 — Service"]
        RAG[RAG Engine]
        Chat[Chatbot]
        Classify[Classifier]
        Summ[Summariser]
        Embed[Embedding Service]
    end

    RAG --> Resilient
    Chat --> RAG
    Chat --> Resilient
    Classify --> Resilient
    Summ --> Resilient
    Embed --> Resilient

    subgraph Providers["Layer 3 — AI Provider"]
        Resilient[ResilientAIService]
        Resilient --> P_OpenAI[OpenAIProvider]
        Resilient --> P_Anthropic[AnthropicProvider]
        Resilient --> P_AmaliAI[AmaliAIProvider]
    end

    RAG --> VS
    Embed --> Cache

    Services -.uses.-> Infra

    subgraph Infra["Layer 4 — Infrastructure"]
        Cache[(Redis Cache<br/>graceful fallback)]
        RL[Rate Limiter<br/>token bucket]
        UT[Usage Tracker<br/>tokens · USD]
        VS[(ChromaDB<br/>vector store)]
    end

    P_OpenAI -.records.-> UT
    P_Anthropic -.records.-> UT
    P_AmaliAI -.records.-> UT
    Resilient -.checks.-> RL
```

## 3. Folder Organisation

The repository is laid out as follows. Module responsibilities are stated in each `__init__.py`; this section is the executive summary.

```
library-mind/
├── app/
│   ├── api/              # Layer 1: FastAPI routers (one per domain)
│   ├── services/         # Layer 2: business orchestration
│   ├── providers/        # Layer 3: AI vendor abstractions + failover
│   ├── infrastructure/   # Layer 4: cache, rate limiter, usage tracker, vector store
│   ├── prompts/          # Versioned prompt templates (RAG, chatbot, classifier, summariser)
│   ├── schemas/          # Pydantic request/response models
│   ├── core/             # Settings, structured logging, exception hierarchy
│   ├── data/             # Seed catalogue (books.json)
│   ├── main.py           # FastAPI application factory
│   └── __main__.py       # `python -m app` entrypoint
├── scripts/              # Seeding & smoke-test scripts
├── tests/                # Pytest suite
├── docs/                 # PRD, ERD, API reference, CI guide, this file
├── frontend/             # Placeholder for the future React client
├── .github/workflows/    # CI definitions (currently disabled — see docs/CI.md)
├── docker-compose.yml    # Local dev stack (api + redis)
├── Dockerfile            # Multi-stage container build
├── Makefile              # Developer task runner
└── pyproject.toml        # Deps, build, lint, type, test config
```

Tests mirror the package structure (`tests/services/test_rag.py` exercises `app/services/rag.py`). Documentation lives in `docs/` and is the source of truth — code disagreements with these documents are bugs in the code, not the docs.

## 4. Request Flow

The canonical request — a patron asking *"recommend a book about space exploration"* via `POST /search/ask` — flows through every layer.

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant R as Router
    participant Rag as RAGService
    participant Cache as Cache
    participant RL as RateLimiter
    participant Emb as EmbeddingService
    participant VS as ChromaDB
    participant AI as ResilientAIService
    participant UT as UsageTracker

    C->>R: POST /search/ask {question}
    R->>R: Validate (Pydantic)
    R->>Rag: ask(question)
    Rag->>Cache: get(hash(question))
    alt cache hit
        Cache-->>Rag: cached response
        Rag-->>R: response (cached=true)
    else cache miss
        Rag->>RL: acquire()
        alt rate-limited
            RL-->>Rag: RateLimitExceeded
            Rag-->>R: 429
        else allowed
            Rag->>Emb: embed(question)
            Emb->>Cache: get(hash(question))
            Cache-->>Emb: miss
            Emb->>AI: provider.embed(question)
            AI-->>Emb: vector
            Emb-->>Rag: vector
            Rag->>VS: query(vector, top_k)
            VS-->>Rag: candidates
            Rag->>Rag: filter by threshold
            alt no candidates pass threshold
                Rag-->>R: polite refusal, sources=[]
            else
                Rag->>AI: generate(prompt + context)
                AI-->>Rag: answer
                AI->>UT: record(tokens, cost)
                Rag->>Cache: set(hash, response)
                Rag-->>R: response (cached=false)
            end
        end
    end
    R-->>C: JSON
```

The chatbot path is identical except the chatbot service also retrieves and truncates conversation history before constructing the prompt, and appends the user message and assistant reply to the conversation store after success.

## 5. Service Boundaries

`RAGService` knows nothing about HTTP or about providers; it accepts a question and returns a structured result. `ChatbotService` depends on `RAGService` for retrieval; it does not duplicate that logic. `EmbeddingService` is shared between RAG and any other consumer that needs vectors, because embedding is the most cache-worthy operation in the system. `ClassifierService` and `SummariserService` consume only the AI provider layer — they do not touch the vector store because their inputs are self-contained.

The provider layer exposes a single `AIProvider` protocol with one method (`generate(prompt, system, temperature, max_tokens)`); each concrete provider implements it. `ResilientAIService` is a *decorator* over a list of providers — it satisfies the same protocol, so callers cannot tell whether they are talking to one provider or to a fallback chain. This is the point of using protocol-based dependencies: substitution is free.

## 6. Validation Flow

Validation happens in three concentric rings. The outermost ring is Pydantic at the router boundary: type coercion, length limits, enum membership. The middle ring is service-layer validation: invariants that cannot be expressed in a schema, like "rate limit not exceeded" or "embedding model still matches the seed". The innermost ring is provider-layer validation: provider-specific concerns like token-limit checks before dispatching. Failures at each ring map to a clear exception (`ValidationError`, `RateLimitExceededError`, `ProviderError`) and the global exception handler in the API layer translates each to the correct HTTP status.

## 7. Authentication Flow

Out of scope for this lab — no endpoint is protected. The architecture is auth-ready: middleware would sit between CORS and the routers, populating `request.state.user` from a verified JWT. Routers would consume that via a `Depends(get_current_user)` dependency. Per-user rate limiting would key the token bucket on user ID. None of this is implemented now; the placeholder is `app/api/` middleware ordering, which already reserves a slot above routers for auth.

## 8. Model Integration Approach (ORM/Data Layer)

There is no SQL ORM in this lab because there is no SQL database. The catalogue lives in ChromaDB, accessed via a thin `VectorStore` wrapper that hides ChromaDB's specific API. Conversation, ticket, and usage records live in plain Python data structures behind narrowly-scoped store classes (`ConversationStore`, `UsageTracker`). The store classes are designed as interfaces with a single in-memory implementation today; future Postgres-backed implementations would satisfy the same interface and require no service-layer changes.

## 9. Async Processing Design

There is no background-task system in this lab because no operation needs to outlive the request: embeddings, RAG answers, and classifications are all synchronous from the user's perspective. FastAPI handlers are declared `async def` so they don't block the event loop on I/O (provider calls are awaited with the async clients each SDK ships), but there is no Celery, RQ, or APScheduler.

If a future iteration needed background work — pre-computing embeddings for newly ingested books, periodically rolling up usage records — the natural fit would be Celery with Redis as the broker (Redis is already in the stack). The seeding script would dispatch ingest tasks, and a worker process would consume them. Until that need exists, adding a task queue would be over-engineering.

## 10. Caching Strategy

Three caches sit on the hot path. The **embedding cache** keys on the hash of the input text and stores the resulting vector; this is the highest-value cache because embedding the same query twice produces the same vector deterministically. The **RAG response cache** keys on the hash of the question and stores the full answer + sources payload; this is what makes "same question asked twice returns instantly" measurable. The **classifier/summariser caches** key on the hash of the input text and store the parsed structured output; this matters less because user inputs are rarely identical, but it costs nothing.

All caches share the same Redis backend behind a single `Cache` wrapper class. The wrapper is designed so a `redis.ConnectionError` is logged and swallowed, returning `None` from `get` and silently no-op-ing on `set`. The application continues to function — slower, but correct — when Redis is down. This is the "degrade gracefully" requirement from the lab brief.

Cache TTLs are configurable; defaults are 1 hour for RAG responses and 24 hours for embeddings. Cache keys include a short version prefix (`v1:rag:...`) so prompt edits during development can be invalidated cleanly by bumping the prefix.

## 11. Distance vs Similarity

ChromaDB with `hnsw:space=cosine` returns **cosine distance**, not cosine similarity. Distance is in the range `[0, 2]` where `0` means identical vectors and `2` means diametrically opposed. The lab brief and the user-facing API contract speak in **similarity** terms (`[0, 1]`, higher = more relevant). The RAG engine performs the conversion exactly once at the boundary:

```python
similarity = max(0.0, 1.0 - distance)
```

The `RAG_RELEVANCE_THRESHOLD` setting is a **similarity** threshold (default `0.35`); results with similarity below it are discarded *after* the conversion. Sources returned in the API response carry the similarity score, never the raw distance, so the contract is consistent.

This is the single most common pitfall in RAG implementations (the lab's own brief calls it out). Centralising the conversion in the RAG service eliminates the class of bugs where one code path uses distance and another uses similarity.

## 12. Prompt Strategy

Prompts are first-class application logic. They live in `app/prompts/` — never inline in services — for four reasons. **PR review**: a prompt change shows up as a diff in a single, named file rather than buried inside a method. **A/B testing**: swapping `RAG_SYSTEM_PROMPT` for `RAG_SYSTEM_PROMPT_V2` is one import-line change. **Cache invalidation**: prompt edits during development can be invalidated cleanly by bumping the version prefix in the cache key (`v1:rag:...` → `v2:rag:...`) rather than flushing the entire Redis namespace. **Token accounting**: keeping prompts in named constants makes their token cost auditable; a stray `f"You are {role}. {long_history}..."` buried in a function obscures what is actually being billed.

Each prompt module exports a typed string constant (`RAG_SYSTEM_PROMPT: str`), a module-level docstring explaining the shaping decisions, and — where applicable — a typed list of few-shot examples (`CLASSIFICATION_EXAMPLES: list[tuple[str, dict]]`). Temperature defaults live next to the prompt that uses them (`0.1` for classification and extraction, `0.3` for RAG generation, `0.7` for the chatbot's conversational tone).

The classifier and summariser prompts include explicit instructions to return JSON with no surrounding prose, and the response parser strips ```json``` markdown fences defensively. This pattern is non-optional: M3's notes and the lab brief both call out fence-wrapping as the most common reason JSON parsing fails in production.

## 13. Chunking Decision

Chunking is the standard solution for fitting long documents into a model's embedding token limit. **It is deliberately *not* implemented in this lab** because the catalogue's input data — book descriptions of a few sentences each — fits comfortably inside any embedding model's token window (typically 512–8192 tokens). Splitting a 200-word book description into chunks would *hurt* retrieval quality by scattering coherent meaning across multiple vectors.

If the catalogue ever ingested full-text book chapters or reviews exceeding 1000 characters, the path is clear: add `langchain-text-splitters` to the dependency set, use `RecursiveCharacterTextSplitter` with `chunk_size=1000` / `chunk_overlap=200` separators (`["\n\n", "\n", ". ", " "]`), and store `(document_id, chunk_index, total_chunks)` in ChromaDB metadata so source citations can resolve back to the parent document. The vector store interface already accepts metadata dicts, so no rearchitecting is needed.

## 14. Cost Management

Every AI call has a price. Four mechanisms keep that price visible and bounded:

**Token counting at the source.** `tiktoken` (for OpenAI-compatible models) and the providers' reported token counts feed into the usage tracker. Prompt tokens and completion tokens are recorded separately because their pricing differs by roughly 3–5×.

**Per-model pricing table.** A constant in `app/infrastructure/usage_tracker.py` maps `(provider, model)` to `(input_per_1k_usd, output_per_1k_usd)`. Updating prices when vendors change them is a one-file edit.

**Aggressive caching.** Embeddings and full RAG responses are cached by deterministic hash of the input. Identical questions return for free. M1 and M2 both stress that caching is the single highest-leverage cost optimisation for AI features.

**Soft daily budget cap.** `BUDGET_DAILY_LIMIT_USD` (default `0.0` = disabled) sets a daily threshold. `/health` reports current daily spend; later phases log a warning when daily spend approaches the cap. The lab does not require enforcement (rejecting requests over budget), so we track and warn rather than block — this matches the lab acceptance criterion of reporting non-zero cost after an AI call, while leaving room for a future enforcement step.

Model-selection guidance ships as a comment in `.env.example`: `gpt-4o-mini` and `claude-3-5-haiku-latest` are the defaults because they are roughly an order of magnitude cheaper than the flagship variants and sufficient for the lab's tasks (classification, summarisation, chat over a small catalogue).

## 15. Deferred Optimisations

The notes (M2 in particular) describe several optimisations beyond what the lab requires. They are deliberately deferred and documented here so a future contributor knows we considered them.

**Hybrid search (BM25 + semantic).** Combining BM25 keyword scores with vector similarity scores improves precision on queries that mention proper nouns (author names, book titles). Out of scope because the lab's catalogue is small and semantic search alone meets the acceptance criteria. If added later, `rank-bm25` is the natural Python library; the merge formula is a weighted sum with `semantic_weight = 0.7`.

**Cross-encoder re-ranking.** Retrieving 20 candidates with vector search and re-ranking the top 5 with a cross-encoder (e.g. `cross-encoder/ms-marco-MiniLM-L-6-v2` from `sentence-transformers`) produces noticeably better precision on harder queries. Adds latency and a model dependency; not justified for the lab.

**LangChain / LlamaIndex.** Both wrap the RAG pipeline behind a high-level API. We use raw SDKs in this lab for three reasons: (1) the implementation is more explicit and therefore easier to grade, (2) the rubric tests our understanding of each pipeline stage rather than our ability to invoke a framework, (3) raw control over prompts and retrieval is needed to satisfy specific acceptance criteria (citation format, threshold behaviour). LangChain remains a sensible refactor target after the lab.

**Streaming responses.** The OpenAI/Anthropic SDKs support token-level streaming, which dramatically improves perceived latency for chatbot replies. Out of scope because the lab's REST API contract returns complete JSON responses; streaming would require Server-Sent Events or WebSockets, neither of which is required by the rubric.

**Function calling / tool use.** Out of scope; the lab does not require agentic behaviour.

## 16. Observability

Structured logging is the foundation. Every log line is JSON in production and human-readable in development. Every log line associated with a request carries a request ID (generated in middleware in Phase 7 and bound to the structlog context for the lifetime of the request). Every AI call logs `provider`, `model`, `prompt_tokens`, `completion_tokens`, `cost_usd`, and `latency_ms`. Every cache lookup logs `hit | miss`. Every rate-limit decision logs `allowed | rejected`.

The `/health` endpoint exposes the running aggregate: daily cost in USD, total request count today, and the configured-provider list. This is the minimum viable telemetry for a lab. A production iteration would add OpenTelemetry traces (one span per layer), a Prometheus exporter for the usage tracker counters, and Sentry for unhandled exceptions. The seams for all three are present: the global exception handler is the natural Sentry insertion point, the usage tracker already aggregates the metrics Prometheus would scrape, and FastAPI/uvicorn integrate with OpenTelemetry through a single middleware addition.
