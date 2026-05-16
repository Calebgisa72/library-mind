"""Entrypoint enabling ``python -m app`` to launch the dev server.

Production deployments should invoke uvicorn/gunicorn directly with their
own process-supervision settings; this module is a developer convenience.
"""

from __future__ import annotations

import uvicorn

from app.core.settings import get_settings


def main() -> None:
    """Run the API with uvicorn using configured host/port."""
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "development",
        log_config=None,  # We configure logging ourselves in app.core.logging.
    )


if __name__ == "__main__":
    main()
