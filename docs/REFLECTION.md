# LibraryMind — Reflection Document

*Module 10 Lab Submission · Gisa Mugisha Caleb Pacifique*

---

## 1. Project Summary

LibraryMind is a production-grade FastAPI backend for a public library, exposing six
AI-powered endpoints over a strict four-layer architecture (API → Service → AI Provider →
Infrastructure). The system integrates multi-provider AI failover across OpenAI, Anthropic,
and AmaliAI, stores book embeddings in ChromaDB for semantic search, implements a complete
Retrieval-Augmented Generation pipeline, maintains multi-turn conversational memory, and
classifies support tickets and summarises reviews via structured-output prompts. Throughout
the build, equal weight was given to production concerns: Redis caching with graceful
degradation, a token-bucket rate limiter, and per-call cost tracking in USD.

---

## 2. Key Design Decisions

**Raw SDKs over LangChain.** The AI provider layer uses the official `openai` and `anthropic`
SDKs plus a thin `httpx`-based client for AmaliAI, rather than a framework like LangChain.
This choice exposed every stage of the pipeline explicitly — embedding, retrieval, threshold
filtering, prompt construction, generation — which made the code easier to reason about,
test, and grade against the rubric. LangChain would have abstracted these stages into opaque
chain objects, making it harder to demonstrate understanding of each step.

**Centralised distance-to-similarity conversion.** ChromaDB returns cosine *distance* in
`[0, 2]`; the lab and the API contract speak in *similarity* terms `[0, 1]`. The conversion
`similarity = max(0.0, 1.0 - distance)` is performed exactly once, at the `VectorStore.search`
boundary, and never repeated elsewhere. This eliminated an entire class of subtle bugs where
one code path would apply the wrong threshold direction. The `RAG_RELEVANCE_THRESHOLD` setting
is always documented as a similarity threshold in comments and the API reference.

**Dedicated `app/prompts/` package.** Every prompt the application sends to an AI provider
lives in a named module under `app/prompts/` rather than as an inline triple-quoted string.
This had four practical benefits that materialised during development: PR diffs are readable
(prompt edits show up in a single file), cache keys include a version prefix that can be
bumped without flushing Redis, temperature defaults live next to the prompt they belong to,
and anti-drift tests in `tests/prompts/` catch any accidental regression to a prompt that no
longer matches the expected output format.

**Multi-inheritance `AllProvidersFailedError`** was designed to satisfy the lab's literal
acceptance criterion: *"a RuntimeError is raised with a helpful message"*. The exception
class inherits from both `RuntimeError` and a custom `ProviderError`, so `isinstance` checks
against either parent pass. The global exception handler in the API layer maps it to HTTP 503,
while the service layer catches it as `RuntimeError` as the lab expects.

---

## 3. Challenges Faced

**Distance vs similarity confusion — the first real bug.** During Phase 3 the seed script ran
without error and the vector store appeared populated, but every RAG question returned the
polite refusal. After an hour of confusion, the root cause was clear: the relevance threshold
was set to `0.35` (similarity), but at the time the RAG service was comparing raw ChromaDB
distances against it. A distance of `0.20` (highly similar) was being discarded because
`0.20 < 0.35`. The fix was to centralise the conversion in `VectorStore.search` and
explicitly document in three places (code, `ARCHITECTURE.md`, and `Agent.md`) that the
threshold is a *similarity* threshold and distances must never leak past the vector store
boundary. This decision now appears in the architecture document under its own section.

**JSON fence stripping is not optional.** During Phase 6, the classifier returned correct
values in approximately 70% of test runs. Occasional failures were caused by the model
wrapping its JSON output in markdown code fences (` ```json … ``` `) even when the prompt
explicitly said "return only JSON". The fix was the `parse_ai_json()` helper in
`app/services/json_utils.py`, which strips both annotated (` ```json `) and plain (` ``` `)
fences before calling `json.loads()`. The helper is now used by every service that expects
a JSON response from the model. The lab brief flags this as a "Known Pitfall" — and the
brief was right.

**Rate-limiter semantics under async concurrency.** The initial token-bucket implementation
used a plain Python counter without a lock. Under pytest-asyncio, two coroutines in the same
event loop would occasionally read the same token count simultaneously and both proceed,
allowing the bucket to go negative. Switching to `asyncio.Lock` — the correct primitive for
a single-event-loop async context — fixed the race and made the test for "61st request in 60
seconds triggers rejection" reliable.

---

## 4. A Debugging Story

During Phase 4 testing, the RAG answer for "What science fiction books do you have about
desert planets?" kept returning the refusal message rather than a grounded answer. The test
confirmed the vector store was seeded (22 books, including Dune), so the issue was somewhere
between the search and the threshold filter.

Logging the raw ChromaDB distances revealed scores like `0.18`, `0.22`, `0.31`. Against a
threshold of `0.35` these were all being discarded. But the threshold was a *similarity*
threshold. Converting: `1 - 0.18 = 0.82` — clearly above the threshold. The bug was that
the RAG service was comparing raw distance to a similarity threshold.

The fix was two-step: first, move the `1 - distance` conversion into `VectorStore.search`
so every caller automatically receives similarities; second, add a unit test
(`test_vector_store.py::test_search_converts_distance_to_similarity`) that mocks ChromaDB
to return a known distance and asserts the returned score equals `1 - distance`. This test
continues to run on every commit, making the invariant impossible to regress silently.

---

## 5. Extensions and Deliberate Non-Extensions

**Attempted extensions:** Comprehensive pytest anti-drift tests for every prompt constant,
ensuring prompt wording, temperature, and token-limit constants cannot be accidentally
changed without a visible test failure. This went beyond the lab requirement but costs almost
nothing and pays dividends whenever a prompt is iterated.

**Deliberate non-extensions:** Hybrid BM25+semantic search and cross-encoder re-ranking
(described in `docs/ARCHITECTURE.md` § *Deferred Optimisations*) were considered but deferred
because the lab's 22-book catalogue is small enough that semantic search alone meets every
acceptance criterion. Adding a BM25 layer would have complicated the relevance-threshold
logic without demonstrable benefit for a catalogue of this size.

LangChain and LlamaIndex were explicitly avoided even for the chatbot's conversation history
management. Managing the history manually (`ConversationStore`, `generate_chat` with a
messages list, `recent()` truncation) required roughly 80 lines of code and made the
context-window management behaviour testable and inspectable — qualities that a framework
would have hidden behind a configuration object.

Streaming responses were not implemented because the lab's REST API contract returns complete
JSON payloads, and streaming would require Server-Sent Events or WebSockets — complexity with
no rubric benefit.

---

*Word count: approximately 870 words.*
