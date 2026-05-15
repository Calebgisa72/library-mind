"""Pydantic schemas for request/response validation.

Schemas are intentionally separate from service-internal data models so
the wire format can evolve independently of the domain representation.

Planned modules:

* :mod:`app.schemas.search`
* :mod:`app.schemas.chat`
* :mod:`app.schemas.classification`
* :mod:`app.schemas.summarisation`
* :mod:`app.schemas.health`
* :mod:`app.schemas.errors` — RFC-7807-style problem details.
"""
