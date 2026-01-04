from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Sequence

from langchain.text_splitter import RecursiveCharacterTextSplitter

try:
    from langchain_community.embeddings import HuggingFaceEmbeddings
except ImportError:
    from langchain.embeddings import HuggingFaceEmbeddings  # type: ignore

from datetime import datetime, timezone
from typing import Sequence

from psycopg.types.json import Json

from src.vectorstore.client.connection import (
    PgVectorConnectionConfig,
    PgVectorConnectionManager,
)
from src.vectorstore.client.log_manager import insert_log_master
from src.vectorstore.parser.log_parser import LogParser, ParsedLogEntry

# ============================================================
# CONFIG
# ============================================================

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # 384 dims
EMBEDDING_DIMS = 384
EMBEDDING_DATA_DIR = Path(__file__).resolve().parent.parent / "embedding_data"

_EMBEDDERS: dict[str, HuggingFaceEmbeddings] = {}

_DEFAULT_EMBED_KWARGS = {
    "encode_kwargs": {
        "batch_size": 256,
        "normalize_embeddings": True,
    }
}


# ============================================================
# EMBEDDING HELPERS
# ============================================================

def _read_text(source: str | Path) -> str:
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Text source not found: {path}")
    return path.read_text(encoding="utf-8")


def _embedding_json_path(source: Path) -> Path:
    return EMBEDDING_DATA_DIR / f"{source.stem}.json"


def _load_cached_embeddings(
    json_path: Path,
) -> tuple[list[str], list[list[float]]] | None:
    if not json_path.exists():
        return None

    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logging.warning("Failed to read cached embeddings %s: %s", json_path, exc)
        return None

    chunks = payload.get("chunks")
    vectors = payload.get("vectors")

    if not isinstance(chunks, list) or not isinstance(vectors, list):
        return None

    if len(chunks) != len(vectors):
        raise ValueError("Cached chunks/vectors length mismatch")

    return [str(c) for c in chunks], [list(map(float, v)) for v in vectors]


def _store_embeddings_json(
    json_path: Path,
    *,
    source_path: Path,
    model_name: str,
    chunk_size: int,
    chunk_overlap: int,
    chunks: Sequence[str],
    vectors: Sequence[Sequence[float]],
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "source": str(source_path),
        "model_name": model_name,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "vector_dims": EMBEDDING_DIMS,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "chunks": list(chunks),
        "vectors": [list(map(float, v)) for v in vectors],
    }

    json_path.write_text(json.dumps(payload), encoding="utf-8")


def _get_embedder(model_name: str) -> HuggingFaceEmbeddings:
    if model_name in _EMBEDDERS:
        return _EMBEDDERS[model_name]

    try:
        embedder = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": "cuda"},
            **_DEFAULT_EMBED_KWARGS,
        )
    except Exception:
        embedder = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": "cpu"},
            **_DEFAULT_EMBED_KWARGS,
        )

    _EMBEDDERS[model_name] = embedder
    return embedder


# ============================================================
# EMBEDDING PIPELINE
# ============================================================

def embed_with_recursive_splitter(
    text: str | Iterable[str],
    *,
    chunk_size: int = 800,
    chunk_overlap: int = 200,
    separators: Sequence[str] | None = None,
    model_name: str = DEFAULT_EMBEDDING_MODEL,
    embed_batch_size: int = 64,
    progress_callback: Callable[[int, int, str | None], None] | None = None,
) -> tuple[list[str], list[list[float]]]:

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=separators,
    )

    sources = [text] if isinstance(text, str) else list(text)

    chunks: list[str] = []
    for item in sources:
        chunks.extend(splitter.split_text(item))

    if not chunks:
        return [], []

    embedder = _get_embedder(model_name)
    vectors: list[list[float]] = []

    total = len(chunks)
    for start in range(0, total, embed_batch_size):
        end = min(start + embed_batch_size, total)
        batch = chunks[start:end]
        batch_vectors = embedder.embed_documents(batch)
        vectors.extend(batch_vectors)

        if progress_callback:
            progress_callback(end, total, None)

    return chunks, vectors


# ============================================================
# DATABASE INSERT (pgvector-native)
# ============================================================

def insert_log_events(
    conn,
    master_id: int,
    chunks: Sequence[str],
    vectors: Sequence[Sequence[float]],
    *,
    batch_size: int = 500,
) -> int:
    """
    Insert embedded chunks into log_event.embedding (vector(384))
    using psycopg v3 native executemany.
    """

    assert len(chunks) == len(vectors), "Chunks/vectors mismatch"

    sql = """
        INSERT INTO log_event (
            master_id,
            message,
            raw_line,
            embedding,
            metadata,
            created_at
        )
        VALUES (
            %(master_id)s,
            %(message)s,
            %(raw_line)s,
            %(embedding)s,
            %(metadata)s,
            %(created_at)s
        )
    """

    now = datetime.now(timezone.utc)
    inserted = 0

    with conn.cursor() as cur:
        for start in range(0, len(chunks), batch_size):
            rows = []

            for i in range(start, min(start + batch_size, len(chunks))):
                rows.append(
                    {
                        "master_id": master_id,
                        "message": chunks[i],
                        "raw_line": chunks[i],
                        "embedding": vectors[i],  # vector(384)
                        "metadata": Json({"chunk_index": i}),
                        "created_at": now,
                    }
                )

            cur.executemany(sql, rows)
            inserted += len(rows)

    conn.commit()
    return inserted


# ============================================================
# ORCHESTRATION
# ============================================================

def _parsed_messages(entries: Sequence[ParsedLogEntry]) -> list[str]:
    messages: list[str] = []
    for entry in entries:
        fields = entry.fields or {}
        messages.append(fields.get("message") or fields.get("msg") or entry.raw)
    return messages


def insert_embeddings_for_log_file(
    file_path: str | Path,
    *,
    dotenv_path: str | None = ".env",
    environment: str = "dev",
    source_type: str = "file",
    log_format: str = "auto",
    chunk_size: int = 1200,
    chunk_overlap: int = 100,
    model_name: str = DEFAULT_EMBEDDING_MODEL,
    embed_batch_size: int = 128,
    progress_callback: Callable[[int, int, str | None], None] | None = None,
) -> tuple[int, int]:

    path = Path(file_path)
    parser = LogParser()
    entries: list[ParsedLogEntry] = list(parser.parse_file(path))

    if not entries:
        raise ValueError(f"No parsed log entries in {path}")

    embedding_json = _embedding_json_path(path)
    cached = _load_cached_embeddings(embedding_json)

    if cached:
        chunks, vectors = cached
        logging.info("Loaded %s cached embeddings", len(vectors))
    else:
        messages = _parsed_messages(entries)
        chunks, vectors = embed_with_recursive_splitter(
            messages,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            model_name=model_name,
            embed_batch_size=embed_batch_size,
            progress_callback=progress_callback,
        )

        if not chunks:
            raise ValueError("No chunks produced")

        _store_embeddings_json(
            embedding_json,
            source_path=path,
            model_name=model_name,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            chunks=chunks,
            vectors=vectors,
        )

    config = PgVectorConnectionConfig.from_env(dotenv_path)
    manager = PgVectorConnectionManager(config)

    with manager.connection() as conn:
        master_id = insert_log_master(
            conn,
            source_name=path.name,
            line_count=len(entries),
            byte_size=path.stat().st_size,
            parse_status="SUCCESS",
            parse_error=None,
            environment=environment,
            source_type=source_type,
            log_format=log_format,
        )

        inserted = insert_log_events(conn, master_id, chunks, vectors)

    return master_id, inserted


# ============================================================
# CLI
# ============================================================

def _default_progress(processed: int, total: int, source: str | None) -> None:
    logging.info("Embedded %s/%s chunks", processed, total)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    backend_root = Path(__file__).resolve().parents[3]
    sample_file = (
        backend_root
        / "data"
        / "raw"
        / "synthetic"
        / "springboot_workflow_with_exceptions_10mb.log"
    )

    master_id, inserted = insert_embeddings_for_log_file(
        sample_file,
        chunk_size=1200,
        chunk_overlap=100,
        embed_batch_size=128,
        progress_callback=_default_progress,
    )

    logging.info("Inserted log_master=%s log_event rows=%s", master_id, inserted)


if __name__ == "__main__":
    main()
