from __future__ import annotations

import logging
import os
from typing import Optional


def configure_logging(level: Optional[str] = None) -> logging.Logger:
    """
    Configure root logging with a sensible default format.
    """
    resolved = level or os.environ.get("LOG_LEVEL", "INFO")
    numeric_level = getattr(logging, resolved.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logger = logging.getLogger(__name__)
    logger.info("Logging configured at level %s", resolved.upper())
    return logger


def main() -> None:
    """
    Smoke test for the logging configuration helper.
    """

    logger = configure_logging()
    logger.debug("Debug message (visible if LOG_LEVEL=DEBUG)")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")


if __name__ == "__main__":
    main()
