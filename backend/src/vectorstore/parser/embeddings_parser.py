from __future__ import annotations

"""
Parse logs, generate embeddings with LangChain (all-MiniLM-L6-v2), and insert
log_master + log_event records. Uses a simple worker to embed log messages with
lightweight progress logging.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue
from threading import Thread
from typing import List, Sequence

from psycopg.types.json import Json

from src.vectorstore.client.connection import (
    PgVectorConnectionConfig,
    PgVectorConnectionManager,
)
from src.vectorstore.client.log_manager import insert_log_master
from src.vectorstore.db_queries.queries import INSERT_LOG_EVENT
from src.vectorstore.parser.log_parser import LogParser, ParsedLogEntry

try:
    # LangChain 0.1+ moved community integrations here.
    from langchain_community.embeddings import HuggingFaceEmbeddings
except ImportError:  # pragma: no cover - fallback for older LangChain
    from langchain.embeddings import HuggingFaceEmbeddings  # type: ignore


@dataclass(frozen=True)
class EmbeddingJob:
    path: Path
    lines: Sequence[str] | None = None
    max_lines: int | None = None


@dataclass(frozen=True)
class EmbeddingResult:
    path: Path
    line_count: int
    vector_count: int
    vector_dim: int
    embeddings: Sequence[Sequence[float]]
    first_vector: List[float]


EMBED_BATCH_SIZE = 500


class EmbeddingWorker(Thread):
    """
    Thread worker that reads log files and produces embeddings.
    Uses a task queue of EmbeddingJob and writes EmbeddingResult to a result queue.
    """

    def __init__(
        self,
        embedder: HuggingFaceEmbeddings,
        tasks: "Queue[EmbeddingJob | None]",
        results: "Queue[EmbeddingResult]",
    ) -> None:
        super().__init__(daemon=True)
        self.embedder = embedder
        self.tasks = tasks
        self.results = results

    def run(self) -> None:
        while True:
            job = self.tasks.get()
            if job is None:  # sentinel to exit
                self.tasks.task_done()
                break

            if job.lines is not None:
                lines = list(job.lines if job.max_lines is None else job.lines[: job.max_lines])
            else:
                lines = _read_lines(job.path, max_lines=job.max_lines)

            vectors: List[Sequence[float]] = []
            if lines:
                total = len(lines)
                for start in range(0, total, EMBED_BATCH_SIZE):
                    end = min(start + EMBED_BATCH_SIZE, total)
                    batch = lines[start:end]
                    batch_vectors = self.embedder.embed_documents(batch)
                    vectors.extend(batch_vectors)
                    logging.info(
                        "Embedded lines %s-%s/%s for %s",
                        start + 1,
                        end,
                        total,
                        job.path.name,
                    )

            vector_dim = len(vectors[0]) if vectors else 0

            self.results.put(
                EmbeddingResult(
                    path=job.path,
                    line_count=len(lines),
                    vector_count=len(vectors),
                    vector_dim=vector_dim,
                    embeddings=vectors,
                    first_vector=vectors[0] if vectors else [],
                )
            )
            self.tasks.task_done()


def _read_lines(path: Path, *, max_lines: int | None = None) -> List[str]:
    lines: List[str] = []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for i, line in enumerate(handle):
            if max_lines is not None and i >= max_lines:
                break
            lines.append(line.rstrip("\n"))
    return lines


def sample_embedding() -> List[float]:
    sentences = ["hello world", "langchain embeddings sanity check"]
    embedder = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectors = embedder.embed_documents(sentences)
    # Return the first embedding to inspect its dimensionality.
    return vectors[0]


def _parse_ts(value: object) -> datetime | None:
    """
    Normalize timestamps to aware UTC datetimes. Returns None on failure.
    """

    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    if isinstance(value, (int, float)):
        try:
            ts = float(value)
            if ts > 1e12:
                ts /= 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            return None

    if isinstance(value, str):
        candidate = value.strip()
        candidate_iso = candidate.replace("Z", "+00:00").replace(",", ".")
        for fmt in (
            "%Y-%m-%d %H:%M:%S.%f%z",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S,%f",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                parsed = datetime.strptime(candidate_iso, fmt)
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        try:
            parsed = datetime.fromisoformat(candidate_iso)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    return None


def insert_log_events(conn, master_id: int, entries: Sequence[ParsedLogEntry], embeddings: Sequence[Sequence[float]]) -> int:
    """
    Insert log_event rows for parsed entries. Embeddings are stored inside metadata.
    """

    now = datetime.now(timezone.utc)
    rows = []
    for entry, vector in zip(entries, embeddings):
        fields = dict(entry.fields or {})
        fields["embedding"] = vector
        ts_value = fields.get("timestamp") or fields.get("ts")
        rows.append(
            {
                "master_id": master_id,
                "ts": _parse_ts(ts_value),
                "service_name": fields.get("service_name") or fields.get("service"),
                "level": fields.get("level"),
                "trace_id": fields.get("trace_id"),
                "span_id": fields.get("span_id"),
                "message": fields.get("message") or fields.get("msg") or entry.raw,
                "raw_line": entry.raw,
                "metadata": Json(fields),
                "logger_name": fields.get("logger"),
                "thread_name": fields.get("thread"),
                "exception_type": fields.get("exception_type"),
                "exception_msg": fields.get("exception_msg"),
                "stack_trace": fields.get("stack_trace"),
                "created_at": now,
            }
        )

    if not rows:
        return 0

    with conn.cursor() as cur:
        cur.executemany(INSERT_LOG_EVENT, rows)
    return len(rows)


def main() -> None:
    """
    Parse a log file with LogParser, embed parsed messages via a worker, and insert into DB.
    Adjust SAMPLE_LOG_PATH if needed.
    """

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    backend_root = Path(__file__).resolve().parents[3]
    sample_log = backend_root / "data" / "raw" / "synthetic" / "synthetic_java_app1_50mb.log"
    if not sample_log.exists():
        raise FileNotFoundError(f"Sample log not found: {sample_log}")

    # Parse the log file and extract messages (fallback to raw when missing)
    parser = LogParser()
    parsed_entries: List[ParsedLogEntry] = list(parser.parse_file(sample_log))
    parsed_messages: List[str] = []
    for entry in parsed_entries:
        fields = entry.fields or {}
        parsed_messages.append(fields.get("message") or fields.get("msg") or entry.raw)

    tasks: Queue[EmbeddingJob | None] = Queue()
    results: Queue[EmbeddingResult] = Queue()
    embedder = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    worker = EmbeddingWorker(embedder, tasks, results)
    worker.start()

    tasks.put(EmbeddingJob(path=sample_log, lines=parsed_messages))
    tasks.put(None)  # sentinel to stop the worker after this job
    tasks.join()

    result = results.get()
    print("Embedded file:", result.path.name)
    print("Lines read:", result.line_count)
    print("Vectors:", result.vector_count)
    print("Vector dimension:", result.vector_dim)
    print("First vector values:", result.first_vector)

    # Insert into DB: log_master + log_event
    config = PgVectorConnectionConfig.from_env(".env")
    manager = PgVectorConnectionManager(config)
    with manager.connection() as conn:
        master_id = insert_log_master(
            conn,
            source_name=sample_log.name,
            line_count=len(parsed_entries),
            byte_size=sample_log.stat().st_size,
            parse_status="SUCCESS",
            parse_error=None,
            environment="dev",
            source_type="file",
            log_format="auto",
        )
        inserted_events = insert_log_events(conn, master_id, parsed_entries, result.embeddings)
        print(f"Inserted log_master id={master_id} with {inserted_events} log_event rows")


if __name__ == "__main__":
    main()
