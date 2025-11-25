from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass
import os
from typing import Any, Iterator, Mapping, Optional, Sequence, Union

from dotenv import load_dotenv
import psycopg
from psycopg import Connection, Cursor
from pgvector.psycopg import register_vector

load_dotenv()

logger = logging.getLogger(__name__)


def _get_required_env(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        logger.error("Required environment variable '%s' not found", key)
        raise RuntimeError(f"Environment variable '{key}' is required but missing.")
    logger.debug("Loaded environment variable '%s'", key)
    return value


@dataclass(frozen=True)
class PgVectorConnectionConfig:
    host: str
    port: int
    database: str
    user: str
    password: str

    @classmethod
    def from_env(cls, dotenv_path: Optional[str] = None) -> "PgVectorConnectionConfig":
        env_file = dotenv_path or ".env"
        loaded = load_dotenv(env_file, override=False)
        logger.debug("load_dotenv path=%s loaded=%s", env_file, loaded)
        return cls(
            host=_get_required_env("PG_HOST"),
            port=int(os.environ.get("PG_PORT", "5432")),
            database=_get_required_env("PG_DATABASE"),
            user=_get_required_env("PG_USER"),
            password=_get_required_env("PG_PASSWORD"),
        )


class PgVectorConnectionManager:
    """
    Provides pgvector-ready PostgreSQL connections configured via environment variables.
    """

    def __init__(self, config: PgVectorConnectionConfig) -> None:
        self._config = config

    def _connect(self) -> Connection[Any]:
        conn = psycopg.connect(
            host=self._config.host,
            port=self._config.port,
            dbname=self._config.database,
            user=self._config.user,
            password=self._config.password,
        )
        register_vector(conn)
        logger.debug(
            "Established pgvector connection to %s:%s/%s",
            self._config.host,
            self._config.port,
            self._config.database,
        )
        return conn

    @contextmanager
    def connection(self) -> Iterator[Connection[Any]]:
        conn = self._connect()
        try:
            logger.debug("Yielding raw connection")
            yield conn
            conn.commit()
            logger.debug("Connection committed successfully")
        except Exception:
            logger.exception("Connection context failed; rolling back")
            conn.rollback()
            raise
        finally:
            logger.debug("Closing connection")
            conn.close()

    @contextmanager
    def cursor(self) -> Iterator[Cursor[Any]]:
        with self.connection() as conn:
            cur = conn.cursor()
            try:
                logger.debug("Yielding cursor")
                yield cur
            finally:
                logger.debug("Closing cursor")
                cur.close()


QueryParams = Optional[Union[Sequence[Any], Mapping[str, Any]]]


class PgVectorClient:
    """
    Lightweight helper built on top of PgVectorConnectionManager for reusable query execution.
    """

    def __init__(self, manager: PgVectorConnectionManager) -> None:
        self._manager = manager

    @classmethod
    def from_env(cls, dotenv_path: Optional[str] = None) -> "PgVectorClient":
        config = PgVectorConnectionConfig.from_env(dotenv_path)
        return cls(PgVectorConnectionManager(config))

    def execute(self, sql: str, params: QueryParams = None) -> None:
        logger.debug("Executing SQL (no fetch): %s", sql)
        with self._manager.cursor() as cur:
            cur.execute(sql, params)

    def fetch_one(self, sql: str, params: QueryParams = None) -> Any:
        logger.debug("Executing SQL fetch_one: %s", sql)
        with self._manager.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()

    def fetch_all(self, sql: str, params: QueryParams = None) -> Sequence[Any]:
        logger.debug("Executing SQL fetch_all: %s", sql)
        with self._manager.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def main(dotenv_path: Optional[str] = None) -> None:
    """
    Convenience entry point to verify connectivity and the PgVector helpers.
    """
    logging.basicConfig(level=logging.INFO)
    try:
        config = PgVectorConnectionConfig.from_env(dotenv_path)
        manager = PgVectorConnectionManager(config)
        client = PgVectorClient(manager)

        with manager.connection() as conn:
            info = getattr(conn, "info", None)
            if info:
                logger.info(
                    "Connection established via manager: host=%s port=%s db=%s",
                    info.host,
                    info.port,
                    info.dbname,
                )
            else:
                logger.info("Connection established via manager.")

        with manager.cursor() as cur:
            cur.execute("SELECT 'cursor test' AS message;")
            logger.info("Cursor test result: %s", cur.fetchone())

        client.execute("SELECT 1;")
        logger.info("Client execute() completed for SELECT 1.")

        single = client.fetch_one("SELECT 42 AS value;")
        logger.info("Client fetch_one() result: %s", single)

        rows = client.fetch_all("SELECT generate_series(1, 3) AS value;")
        logger.info("Client fetch_all() results: %s", rows)

        logger.info("All PgVector connection helpers executed successfully.")
    except Exception:
        logger.exception("Connection test failed")
        raise


__all__ = [
    "PgVectorConnectionConfig",
    "PgVectorConnectionManager",
    "PgVectorClient",
    "main",
]


if __name__ == "__main__":
    main()
