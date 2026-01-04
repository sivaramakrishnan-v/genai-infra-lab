from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, List

# DB queries
from src.vectorstore.db_queries.queries import INSERT_LOG_MASTER, INSERT_LOG_EVENT

# DB connection
from src.vectorstore.client.connection import (
    PgVectorConnectionConfig,
    PgVectorConnectionManager,
)


logger = logging.getLogger(__name__)


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

    with conn.cursor() as cur:
        cur.execute("SELECT current_database(), inet_server_addr(), inet_server_port()")
        print("DB Identity →", cur.fetchone())

        cur.execute(INSERT_LOG_MASTER, params)
        master_id = cur.fetchone()[0]

    conn.commit()
    print("Inserted log_master.id =", master_id)
    return master_id


# ============================================================
# INSERT INTO log_event
# ============================================================
def insert_log_events(conn, master_id: int, entries: List[Any]):
    now = datetime.now(timezone.utc)
    rows = []

    for e in entries:
        f = e.fields

        rows.append({
            "master_id": master_id,
            "ts": f.get("timestamp"),
            "service_name": f.get("service"),
            "level": f.get("level"),
            "trace_id": f.get("trace_id"),
            "span_id": f.get("span_id"),
            "message": f.get("msg"),
            "raw_line": e.raw,
            "metadata": f,
            "logger_name": f.get("logger"),
            "thread_name": f.get("thread"),
            "exception_type": f.get("exception_type"),
            "exception_msg": f.get("exception_msg"),
            "stack_trace": f.get("stack_trace"),
            "created_at": now,
        })

    with conn.cursor() as cur:
        cur.executemany(INSERT_LOG_EVENT, rows)

    conn.commit()
    print("Inserted log_event rows:", len(entries))


# ============================================================
# HIGH-LEVEL: parse logs + insert master + insert events
# ============================================================
def ingest_log_file(conn, file_path: Path):

    print("Parsing:", file_path)
    entries, metadata = parse_file(file_path)

    print("Parsed entries:", len(entries))
    print("Metadata:", metadata)

    master_id = insert_log_master(
        conn,
        source_name=metadata["source_name"],
        line_count=metadata["line_count"],
        byte_size=metadata["byte_size"],
        parse_status=metadata.get("parse_status", "SUCCESS"),
    )

    insert_log_events(conn, master_id, entries)

    return master_id


# ============================================================
# TOP-LEVEL entry: loading DB config + ingestion in one call
# ============================================================
def run_log_ingest(file_path: str, dotenv_path: str | None = None):

    conf = PgVectorConnectionConfig.from_env(dotenv_path)
    manager = PgVectorConnectionManager(conf)

    print(
        f"Opening connection → host={conf.host} port={conf.port} db={conf.database}"
    )

    with manager.connection() as conn:
        return ingest_log_file(conn, Path(file_path))


def main(dotenv_path: str | None = None) -> None:
    """
    Smoke test against a real database: inserts master + events then cleans up.
    Requires PG_* environment variables and the log_master/log_event tables.
    """

    logging.basicConfig(level=logging.INFO)

    config = PgVectorConnectionConfig.from_env(dotenv_path)
    manager = PgVectorConnectionManager(config)

    class _Entry:
        def __init__(self, raw: str, fields: Mapping[str, Any]) -> None:
            self.raw = raw
            self.fields = fields

    sample_entries = [
        _Entry("raw line 1", {"msg": "hello", "level": "INFO", "timestamp": "2024-01-01T00:00:00Z"}),
        _Entry("raw line 2", {"msg": "world", "level": "ERROR", "timestamp": "2024-01-01T00:00:01Z"}),
    ]

    logger.info(
        "Connecting to %s:%s/%s",
        config.host,
        config.port,
        config.database,
    )

    try:
        with manager.connection() as conn:
            master_id = insert_log_master(
                conn,
                source_name="sample.log",
                line_count=len(sample_entries),
                byte_size=256,
            )
            insert_log_events(conn, master_id, sample_entries)
            logger.info("Inserted log_master id=%s with %s events; cleaning up", master_id, len(sample_entries))

            with conn.cursor() as cur:
                cur.execute("DELETE FROM log_event WHERE master_id = %(id)s", {"id": master_id})
                cur.execute("DELETE FROM log_master WHERE id = %(id)s", {"id": master_id})
            conn.commit()
            logger.info("Cleanup committed successfully")
    except Exception:
        logger.exception("Smoke test failed; ensure DB is reachable and schema is applied")
        raise


if __name__ == "__main__":
    main()
