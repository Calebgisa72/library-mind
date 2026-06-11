# LibraryMind — Frontend

A production-style web client for the **LibraryMind** backend: an AI-powered
intelligent library assistant. The UI exercises **every** backend capability
through a polished, accessible, light/dark interface.

## Stack

- **Next.js 14** (App Router) + **TypeScript**
- **Tailwind CSS** with a custom deep-orange (`#E8590C`) design system and full light/dark theming
- **TanStack Query** for server state (mutations + the polling health query)
- **Zod** for runtime validation of every request and response (mirrors the backend's Pydantic schemas)
- **next-themes** for system/light/dark theme switching
- **axios** + a typed, error-normalising API client
- **lucide-react** icons

## Features (one per backend endpoint)

| Page | Endpoint | What it does |
| --- | --- | --- |
| Dashboard `/` | `GET /health` | Overview, live status strip, capability cards |
| Catalogue Search `/search` | `POST /search/books` | Semantic search ranked by cosine similarity |
| Ask the Librarian `/ask` | `POST /search/ask` | RAG Q&A grounded in the catalogue, with source citations and a cache flag |
| Chat `/chat` | `POST /chat` | Multi-turn chatbot with a localStorage-backed conversation history (auto UUID `conversation_id`) |
| Classify Ticket `/classify` | `POST /classify/ticket` | Structured triage: category, priority, sentiment, department, summary |
| Summarise Reviews `/summarise` | `POST /summarise/reviews` | Aggregate 1–50 reviews into sentiment, rating, themes, praise, criticism, recommendation |
| System Health `/health` | `GET /health` | Admin dashboard: providers, cache, daily spend vs. budget, request count (auto-refresh) |

## Getting started

```bash
cd frontend
cp .env.local.example .env.local   # defaults to http://localhost:8000
npm install
npm run dev                        # http://localhost:3000
```

The backend already allows `http://localhost:3000` and `http://localhost:5173`
via `CORS_ALLOWED_ORIGINS`, so no extra configuration is needed for local dev.

### Scripts

- `npm run dev` — start the dev server
- `npm run build` — production build
- `npm run start` — serve the production build
- `npm run typecheck` — `tsc --noEmit`
- `npm run lint` — Next.js ESLint

## Configuration

| Env var | Default | Purpose |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | Base URL of the FastAPI backend (browser-visible) |
| `BACKEND_INTERNAL_URL` | _(unset)_ | Optional. If set, Next.js proxies `/api/backend/*` to it server-side |

## Architecture notes

- `src/lib/schemas.ts` — Zod schemas that are the single source of truth for wire shapes.
- `src/lib/api.ts` — typed client; validates responses and normalises errors (`ApiError` with `status`, `isRateLimit`, `isUnavailable`, `isNetwork`).
- `src/lib/hooks.ts` — TanStack Query hooks; 4xx errors are not retried.
- `src/lib/conversations.ts` — client-owned chat history (the backend exposes no list/fetch endpoint).
- Theming is driven by HSL CSS variables in `src/app/globals.css`; the primary brand colour is deep orange and is tuned separately for light and dark.
