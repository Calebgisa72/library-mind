"""HTTP API layer.

Each submodule defines an :class:`fastapi.APIRouter` for a single domain
(search, chat, classification, summarisation, health). Routers contain
**no business logic**: they validate input via Pydantic schemas, delegate
to a service, and shape the response.

Routers are implemented in later phases. This package currently exists
to fix the layered import structure.
"""
