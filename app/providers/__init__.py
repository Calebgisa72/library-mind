"""AI provider abstraction layer.

Exposes a single ``AIProvider`` protocol that all concrete providers
(OpenAI, Anthropic, AmaliAI) implement. A ``ResilientAIService`` (Part 1)
maintains an ordered list of providers and falls through on failure.

This indirection means the rest of the app talks to one interface; vendor
changes are localised to a single module.

Planned modules:

* :mod:`app.providers.base` — protocol / abstract base class.
* :mod:`app.providers.openai_provider`
* :mod:`app.providers.anthropic_provider`
* :mod:`app.providers.amaliai_provider`
* :mod:`app.providers.resilient` — failover orchestrator.
"""
