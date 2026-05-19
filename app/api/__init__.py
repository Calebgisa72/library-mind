"""HTTP API layer.

Each submodule defines an :class:`fastapi.APIRouter` for a single domain
(search, chat, classification, summarisation, health). Routers contain
**no business logic**: they validate input via Pydantic schemas, delegate
to a service, and shape the response.

Sub-packages:
    routers/    -- one router module per endpoint group
    dependencies.py -- FastAPI ``Depends()`` factories (singletons)
    middleware.py   -- request-ID middleware + exception handler registration
"""
