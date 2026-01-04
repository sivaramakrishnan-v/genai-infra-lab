from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

if __package__ is None:
    current = Path(__file__).resolve()
    src_dir = current.parents[1]  # backend/src
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    from api.app import create_app  # type: ignore
else:
    from .app import create_app

logger = logging.getLogger(__name__)


def main() -> None:
    """
    Smoke test for the Flask app using the built-in test client.
    Does not start a server; simply hits key endpoints and logs responses.
    """

    log_level = os.environ.get("LOG_LEVEL", "INFO")
    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO))

    app = create_app()
    client = app.test_client()

    health = client.get("/api/health")
    logger.info("GET /api/health -> %s %s", health.status_code, health.json)

    version = client.get("/api/version")
    logger.info("GET /api/version -> %s %s", version.status_code, version.json)

    echo = client.post("/api/test", json={"ping": "pong"})
    logger.info("POST /api/test -> %s %s", echo.status_code, echo.json)

    logger.info("Flask smoke tests completed successfully.")


if __name__ == "__main__":
    main()
