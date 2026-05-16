# LibraryMind — Frontend (placeholder)

This directory is reserved for the future LibraryMind web client. It is
**not** part of the current lab deliverable; the lab is graded purely on
the backend.

## Planned stack

- **React 18** + **TypeScript** + **Vite**
- **Tailwind CSS** for styling
- **TanStack Query** for server state
- **Zod** for runtime validation of API responses (mirrors the backend's Pydantic schemas)

## Planned scope

A minimal SPA exercising every backend capability:

- Catalogue search box with semantic-search results
- "Ask the librarian" panel powered by `/search/ask`
- Persistent chat thread powered by `/chat`
- Admin view summarising daily usage from `/health`

## Out of scope for the lab

No build tooling, lockfile, or package manifest is checked in yet. The
backend is the only artefact under active development.
