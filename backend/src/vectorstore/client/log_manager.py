from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from src.vectorstore.db_queries.queries import INSERT_LOG_MASTER
from src.vectorstore.client.connection import (
    PgVectorConnectionConfig,
    PgVectorConnectionManager,
)

logger = logging.getLogger(__name__)
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"


# ============================================================
# INSERT INTO log_master
# ============================================================
def insert_log_master(
    conn,
    *,
    source_name: str,
    line_count: int,
    byte_size: int,
    parse_status: str = "SUCCESS",
    parse_error: str | None = None,
    service_name: str | None = None,
    environment: str = "dev",
    source_type: str = "file",
    log_format: str = "otel",
) -> int:

    # Use explicit UTC timezone to avoid deprecated naive UTC datetimes
    now = datetime.now(timezone.utc)

    params = {
        "source_name": source_name,
        "source_type": source_type,
        "service_name": service_name,
        "environment": environment,
        "log_format": log_format,
        "line_count": line_count,
        "byte_size": byte_size,
        "parse_status": parse_status,
        "parse_error": parse_error,
        "parsed_at": now,
        "created_at": now,
    }

    logger.debug(
        "Inserting log_master record for %s (lines=%s, bytes=%s, status=%s)",
        source_name, line_count, byte_size, parse_status
    )

    with conn.cursor() as cur:
        # Debug: confirm target DB so we never write to wrong DB again
        cur.execute("SELECT current_database(), inet_server_addr(), inet_server_port()")
        print("DB Identity →", cur.fetchone())

        cur.execute(INSERT_LOG_MASTER, params)
        master_id = cur.fetchone()[0]

    conn.commit()
    print("Inserted log_master.id =", master_id)
    return master_id


# ============================================================
# Insert using parsed metadata dict
# ============================================================
def insert_parsed_log_master(conn, parsed_data: Mapping[str, Any]) -> int:

    required_fields = ("source_name", "line_count", "byte_size")
    missing = [f for f in required_fields if f not in parsed_data]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    return insert_log_master(
        conn,
        source_name=str(parsed_data["source_name"]),
        line_count=int(parsed_data["line_count"]),
        byte_size=int(parsed_data["byte_size"]),
        parse_status=str(parsed_data.get("parse_status", "SUCCESS")),
        parse_error=parsed_data.get("parse_error"),
        service_name=parsed_data.get("service_name"),
        environment=str(parsed_data.get("environment", "dev")),
        source_type=str(parsed_data.get("source_type", "file")),
        log_format=str(parsed_data.get("log_format", "otel")),
    )


def ingest_log_file(
    conn,
    file_path: Path | str,
    *,
    environment: str = "dev",
    source_type: str = "file",
    log_format: str = "auto",
) -> int:
    """
    Scan a single log file, capture summary details, and insert into log_master.
    """

    path = Path(file_path)
    byte_size = path.stat().st_size

    # Count lines without holding them in memory
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        line_count = sum(1 for _ in handle)

    master_id = insert_log_master(
        conn,
        source_name=path.name,
        line_count=line_count,
        byte_size=byte_size,
        parse_status="SUCCESS",
        parse_error=None,
        environment=environment,
        source_type=source_type,
        log_format=log_format,
    )

    return master_id


# ============================================================
# Standalone convenience entry: opens connection automatically
# ============================================================
def insert_log_master_from_env(parsed_data: Mapping[str, Any], dotenv_path: str | None = None) -> int:

    config = PgVectorConnectionConfig.from_env(dotenv_path)
    manager = PgVectorConnectionManager(config)

    print(
        f"Opening connection via env → host={config.host} "
        f"port={config.port} db={config.database}"
    )

    with manager.connection() as conn:
        return insert_parsed_log_master(conn, parsed_data)


def ingest_log_file_from_env(
    file_path: Path | str,
    *,
    dotenv_path: str | None = None,
    environment: str = "dev",
    source_type: str = "file",
    log_format: str = "auto",
) -> int:
    """
    Scan + insert a single log file using connection details from environment variables.
    """

    config = PgVectorConnectionConfig.from_env(dotenv_path)
    manager = PgVectorConnectionManager(config)

    logger.info("Connecting to %s:%s/%s", config.host, config.port, config.database)

    with manager.connection() as conn:
        return ingest_log_file(
            conn,
            file_path,
            environment=environment,
            source_type=source_type,
            log_format=log_format,
        )


def ingest_all_logs_from_env(
    data_dir: Path | str = DEFAULT_DATA_DIR,
    *,
    dotenv_path: str | None = None,
    environment: str = "dev",
    source_type: str = "file",
    log_format: str = "auto",
) -> list[int]:
    """
    Walk the data directory (recursively) and insert log_master rows for every *.log file.
    """

    root = Path(data_dir)
    if not root.exists():
        raise FileNotFoundError(f"Log directory does not exist: {root}")

    log_files = sorted(root.rglob("*.log"))
    if not log_files:
        logger.info("No .log files found under %s", root)
        return []

    config = PgVectorConnectionConfig.from_env(dotenv_path)
    manager = PgVectorConnectionManager(config)
    logger.info("Connecting to %s:%s/%s", config.host, config.port, config.database)

    inserted: list[int] = []
    with manager.connection() as conn:
        for file_path in log_files:
            logger.info("Processing %s", file_path)
            master_id = ingest_log_file(
                conn,
                file_path,
                environment=environment,
                source_type=source_type,
                log_format=log_format,
            )
            inserted.append(master_id)
            logger.info("Inserted log_master id=%s for %s", master_id, file_path.name)

    return inserted


def main() -> None:
    """
    Scan all log files under backend/data/raw and insert summary rows into log_master.
    Requires PG_* environment variables and the log_master table.
    """

    logging.basicConfig(level=logging.INFO)

    try:
        inserted = ingest_all_logs_from_env(DEFAULT_DATA_DIR)
        logger.info("Inserted %s log_master rows", len(inserted))
        sys.exit(0)
    except Exception:
        logger.exception("Log ingestion failed")
        raise


if __name__ == "__main__":
    main()
