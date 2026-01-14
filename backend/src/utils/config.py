from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

OPENAI_MODEL_ENV_VAR = "OPENAI_MODEL"
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
OPENAI_ENV_VAR = "OPENAI_API_KEY"


def get_env(key: str, default: Optional[str] = None, *, required: bool = False) -> str:
    """
    Fetch an environment variable with optional default and required enforcement.
    """
    value = os.environ.get(key, default)
    if required and value is None:
        logger.error("Required environment variable missing: %s", key)
        raise RuntimeError(f"Missing required environment variable: {key}")
    logger.debug("Loaded env %s=%s", key, value)
    return value


def load_database_config() -> Dict[str, Any]:
    """
    Load common PostgreSQL settings from environment variables.
    """
    return {
        "host": get_env("PG_HOST", required=True),
        "port": int(get_env("PG_PORT", "5432")),
        "database": get_env("PG_DATABASE", required=True),
        "user": get_env("PG_USER", required=True),
        "password": get_env("PG_PASSWORD", required=True),
    }


def load_openai_settings(dotenv_path: Optional[str] = None) -> tuple[str, str]:
    """
    Load OpenAI API settings and model name from environment variables.
    """
    env_file = dotenv_path or ".env"
    load_dotenv(env_file, override=False)
    api_key = os.environ.get(OPENAI_ENV_VAR)
    if not api_key:
        logger.error("Required environment variable missing: %s", OPENAI_ENV_VAR)
        raise RuntimeError(f"Environment variable '{OPENAI_ENV_VAR}' is required but missing.")
    model_name = os.environ.get(OPENAI_MODEL_ENV_VAR, OPENAI_DEFAULT_MODEL)
    return api_key, model_name


def main() -> None:
    """
    Simple smoke test to verify required environment variables are present.
    """

    logging.basicConfig(level=logging.INFO)
    try:
        db_conf = load_database_config()
        logger.info("Loaded database config: host=%s port=%s db=%s", db_conf["host"], db_conf["port"], db_conf["database"])
    except Exception:
        logger.exception("Config smoke test failed; ensure PG_* variables are set")
        raise


if __name__ == "__main__":
    main()
