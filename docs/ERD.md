# Entity Relationship Diagram — LibraryMind

This document describes the **conceptual** data model. Most entities are in-memory or stored in ChromaDB for this lab (per the lab brief, which permits in-memory persistence for the usage tracker, conversation store, and ticket history). A future production iteration would migrate the in-memory entities into a relational database; the model below is shaped so that migration would be a substitution, not a rewrite.

## 1. Entity Map

```mermaid
erDiagram
    BOOK ||--o{ EMBEDDING : "has"
    BOOK ||--o{ REVIEW : "receives"
    CONVERSATION ||--o{ MESSAGE : "contains"
    MESSAGE ||--o{ CITATION : "may cite"
    CITATION }o--|| BOOK : "references"
    TICKET ||--|| CLASSIFICATION : "produces"
    USAGE_RECORD }o--|| AI_CALL : "summarises"
    CACHE_ENTRY ||--o{ AI_CALL : "may bypass"

    BOOK {
        string id PK
        string title
        string author
        int year
        string genre
        string description
        datetime created_at
        datetime updated_at
    }

    EMBEDDING {
        string id PK
        string book_id FK
        string model
        vector vector
        int dimension
        datetime created_at
    }

    CONVERSATION {
        string id PK
        datetime created_at
        datetime last_message_at
    }

    MESSAGE {
        string id PK
        string conversation_id FK
        string role
        string content
        datetime created_at
    }

    CITATION {
        string id PK
        string message_id FK
        string book_id FK
        float relevance_score
    }

    TICKET {
        string id PK
        string raw_text
        datetime created_at
    }

    CLASSIFICATION {
        string ticket_id PK_FK
        string category
        string priority
        string sentiment
        string department
        string summary
        datetime classified_at
    }

    REVIEW {
        string id PK
        string book_id FK
        string text
        datetime created_at
    }

    USAGE_RECORD {
        string id PK
        string provider
        string model
        int prompt_tokens
        int completion_tokens
        float cost_usd
        string operation
        datetime created_at
    }

    AI_CALL {
        string id PK
        string provider
        string model
        bool succeeded
        int latency_ms
        datetime called_at
    }

    CACHE_ENTRY {
        string key PK
        string value
        int ttl_seconds
        datetime created_at
    }
```

## 2. Storage Strategy

| Entity            | Persistence today                          | Persistence future                          |
|-------------------|--------------------------------------------|---------------------------------------------|
| `Book`            | `app/data/books.json` (seed file) + ChromaDB metadata | Postgres `books` table                     |
| `Embedding`       | ChromaDB collection `books`                | ChromaDB / pgvector                         |
| `Conversation`    | In-memory dict in `ChatbotService`         | Postgres + Redis hot cache                  |
| `Message`         | In-memory list per conversation            | Postgres                                    |
| `Citation`        | Embedded inline in RAG response payload    | Postgres                                    |
| `Ticket`          | Not stored (stateless classification)      | Postgres                                    |
| `Classification`  | Returned to caller, not stored             | Postgres                                    |
| `Review`          | Submitted per-request, not stored          | Postgres                                    |
| `UsageRecord`     | In-memory list in `UsageTracker`           | Postgres + ClickHouse for analytics         |
| `AICall`          | Logged only (structlog)                    | OpenTelemetry traces + Postgres             |
| `CacheEntry`      | Redis (with no-op fallback)                | Redis                                       |

## 3. Relationships & Cardinality

A book has zero-or-more embeddings (one per embedding model in use; we use one model at a time, so in practice 1:1). A book may receive many reviews; reviews are submitted to the summariser but not stored long-term in this lab. A conversation has many messages, in strict chronological order; deleting a conversation cascades to its messages and the citations attached to its messages. A message may cite zero or more books; each citation references exactly one book.

A ticket has exactly one classification (1:1). A usage record summarises exactly one AI call; a cache hit produces no usage record, by design — this is what makes "cache hit" observable.

## 4. Indexes & Constraints

In ChromaDB, the natural index is the HNSW vector index on the embedding column with cosine distance. Metadata filters (`genre`, `year`) require ChromaDB metadata indexes, which are built automatically for any field stored in `metadatas` at upsert time.

For the in-memory stores, `Conversation.id` and `UsageRecord.id` are UUIDs generated at construction. The conversation store is a `dict[str, list[Message]]`, so lookup is O(1) by ID and append is O(1).

The future relational schema would enforce: `books.id` unique, `conversations.id` unique, `messages.created_at` indexed for chronological retrieval, `usage_records.created_at` indexed for "spend in the last 24 hours" queries, and `tickets.created_at` indexed for analytics.

## 5. Timestamps & Audit

Every entity carries `created_at` (UTC). Mutable entities (`Book`, `Conversation`) additionally carry `updated_at`. The lab does not require soft deletes; if the production iteration introduces them, an `archived_at` nullable column on `Book` and `Conversation` would be sufficient.

For audit, structured logs are the source of truth in this lab. Every state change in the usage tracker emits a log line carrying `request_id`, `provider`, `model`, `prompt_tokens`, `completion_tokens`, and `cost_usd`; replaying those logs reconstructs the state of the tracker at any point in time.
