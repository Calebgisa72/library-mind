# API Reference — LibraryMind

| | |
|---|---|
| **Base URL (local)** | `http://localhost:8000` |
| **Auth** | None (lab scope — see *Future authentication* at the bottom) |
| **Content-Type** | `application/json` for all requests and responses |
| **Versioning** | Unversioned in this lab; future production releases will mount under `/v1` |

All endpoints below are **planned**. Implementation lands in Phase 7. This document is the authoritative contract; routers in `app/api/` must conform to it.

## Conventions

Successful responses use `2xx` status codes and return the shape documented per-endpoint. Validation failures use `422 Unprocessable Entity` with FastAPI's default Pydantic error envelope. Rate-limit rejections use `429 Too Many Requests` with `{ "detail": "Rate limit exceeded. Try again in N seconds." }`. AI-provider exhaustion uses `503 Service Unavailable` with `{ "detail": "All AI providers failed." }`. Server errors use `500` with `{ "detail": "Internal server error." }` (sanitised — no stack traces leak to clients).

Pagination, where applicable, uses cursor-style: requests accept `limit` (1–50, default 10); responses include the rows under a `results` key. No offsets — they would scale poorly if we ever moved to a relational store.

Filtering and sorting are not in scope for this lab. The vector store ranks by relevance natively; no other endpoint returns lists large enough to need sorting.

All string inputs are stripped of leading/trailing whitespace and rejected if empty. Maximum lengths are enforced server-side: 500 chars for `query`, 1000 for `question`, 4000 for `message`, 4000 for `ticket text`, 4000 per review (with a list cap of 50 reviews).

---

## 1. `POST /search/books`

Semantic search over the catalogue.

**Request**

```json
{
  "query": "space exploration adventure",
  "limit": 5
}
```

| Field   | Type   | Constraints                | Description                                  |
|---------|--------|----------------------------|----------------------------------------------|
| `query` | string | 3 ≤ len ≤ 500              | Natural-language search phrase               |
| `limit` | int    | 1 ≤ n ≤ 50 (default `10`)  | Maximum number of books to return            |

**Response** `200 OK`

```json
{
  "query": "space exploration adventure",
  "results": [
    {
      "id": "book-dune",
      "title": "Dune",
      "author": "Frank Herbert",
      "year": 1965,
      "genre": "Science Fiction",
      "score": 0.87
    }
  ]
}
```

`score` is cosine similarity in the range `[0, 1]`; higher is more similar. Results below `RAG_RELEVANCE_THRESHOLD` are excluded.

---

## 2. `POST /search/ask`

Retrieval-augmented Q&A. Returns a grounded answer with source citations.

**Request**

```json
{
  "question": "What sci-fi books do you have about desert planets?"
}
```

| Field      | Type   | Constraints       |
|------------|--------|-------------------|
| `question` | string | 5 ≤ len ≤ 1000    |

**Response** `200 OK`

```json
{
  "answer": "Our catalogue includes Dune by Frank Herbert, set on the desert planet Arrakis...",
  "sources": [
    { "title": "Dune", "author": "Frank Herbert", "score": 0.87 }
  ],
  "cached": false
}
```

When the question cannot be answered from the catalogue, `answer` is a polite refusal and `sources` is an empty list. Repeating the exact same `question` returns instantly with `cached: true`.

---

## 3. `POST /chat`

Multi-turn conversational endpoint. The chatbot remembers the previous messages of the conversation.

**Request**

```json
{
  "conversation_id": "c_8f3b...",
  "message": "Recommend a thriller."
}
```

| Field             | Type   | Constraints                |
|-------------------|--------|----------------------------|
| `conversation_id` | string | 1 ≤ len ≤ 64 (caller-supplied; UUIDs recommended) |
| `message`         | string | 1 ≤ len ≤ 4000             |

**Response** `200 OK`

```json
{
  "conversation_id": "c_8f3b...",
  "reply": "If you enjoyed *Gone Girl*, you might love...",
  "sources": [
    { "title": "The Girl on the Train", "author": "Paula Hawkins", "score": 0.79 }
  ]
}
```

Conversation history is automatically truncated to `CHAT_HISTORY_MAX_MESSAGES` recent turns before being sent to the model. Different `conversation_id`s maintain independent histories.

---

## 4. `POST /classify/ticket`

Classifies a raw support-ticket text into structured fields.

**Request**

```json
{
  "text": "My library card isn't working at the self-checkout and I'm very frustrated."
}
```

| Field  | Type   | Constraints       |
|--------|--------|-------------------|
| `text` | string | 5 ≤ len ≤ 4000    |

**Response** `200 OK`

```json
{
  "category": "technical",
  "priority": "high",
  "sentiment": "negative",
  "department": "IT Support",
  "summary": "Patron's library card fails at self-checkout, expressing strong frustration."
}
```

Enum values: `category ∈ {account, borrowing, technical, complaint, suggestion, general}`, `priority ∈ {low, medium, high, urgent}`, `sentiment ∈ {positive, neutral, negative}`. If the model returns invalid JSON or a value outside these enums, the service responds with `503` and a clear error message.

---

## 5. `POST /summarise/reviews`

Aggregates a list of reviews into a single structured analysis.

**Request**

```json
{
  "reviews": [
    "I couldn't put it down.",
    "Tried to like it, gave up after 80 pages.",
    "Pacing dragged in the middle but the ending was excellent."
  ]
}
```

| Field     | Type            | Constraints                                   |
|-----------|-----------------|-----------------------------------------------|
| `reviews` | array of string | 1–50 items, each 5 ≤ len ≤ 4000               |

**Response** `200 OK`

```json
{
  "overall_sentiment": "mixed",
  "estimated_rating": 3.7,
  "themes": ["pacing", "ending", "engagement"],
  "praise": ["compelling ending", "hard to put down"],
  "criticism": ["mid-book pacing issues", "slow start"],
  "recommendation": "Worth recommending to readers patient with a slow build."
}
```

---

## 6. `GET /health`

Operational status and observability.

**Response** `200 OK`

```json
{
  "status": "ok",
  "version": "0.1.0",
  "providers": {
    "openai": "configured",
    "anthropic": "configured",
    "amaliai": "not_configured"
  },
  "cache": "connected",
  "daily_cost_usd": 0.0247,
  "request_count_today": 18
}
```

`status` is `ok` if and only if at least one provider is configured and the application has not entered a degraded state. `cache` is `connected | unavailable`. The endpoint never makes a paid AI call; it reads in-memory counters only.

---

## Error response shape

Apart from FastAPI's default validation envelope (`422`), every error returns:

```json
{ "detail": "Human-readable explanation." }
```

This matches FastAPI's default `HTTPException` shape and integrates cleanly with the auto-generated OpenAPI schema.

---

## Future authentication

Out of scope for the lab. The intended design is bearer-token JWTs issued by an external identity provider, validated in middleware before request handlers run, with claims extracted into the `request.state.user` slot. Rate limits would key on user ID rather than IP. None of this is implemented in this lab.
