from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Sequence

import requests
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
try:
    from ...utils.config import load_openai_settings
except ImportError:
    from utils.config import load_openai_settings  # type: ignore
try:
    # when imported as package
    from ...vectorstore.client.connection import (
        PgVectorConnectionConfig,
        PgVectorConnectionManager,
    )
except ImportError:
    # fallback when run as script with backend/src on sys.path
    from vectorstore.client.connection import (  # type: ignore
        PgVectorConnectionConfig,
        PgVectorConnectionManager,
    )

from langchain.globals import set_debug
set_debug(True)

logger = logging.getLogger(__name__)

EMBED_DIM = 384

@dataclass(frozen=True)
class RetrievedChunk:
    id: int
    message: str
    raw_line: str | None
    distance: float
    metadata: Any


def _query_similar_logs(
    query_vector: Sequence[float],
    *,
    top_k: int = 5,
    dotenv_path: str | None = None,
) -> list[RetrievedChunk]:
    start = time.perf_counter()
    if len(query_vector) != EMBED_DIM:
        raise ValueError(f"Unexpected embedding dimensions {len(query_vector)} (expected {EMBED_DIM})")

    config = PgVectorConnectionConfig.from_env(dotenv_path)
    manager = PgVectorConnectionManager(config)

    sql = """
        SELECT id, message, raw_line, metadata, embedding <=> %(vector)s::vector AS distance
        FROM log_event
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %(vector)s::vector
        LIMIT %(k)s;
    """

    rows: list[RetrievedChunk] = []
    with manager.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"vector": query_vector, "k": top_k})
            for row in cur.fetchall():
                log_id, message, raw_line, metadata, distance = row
                rows.append(
                    RetrievedChunk(
                        id=int(log_id),
                        message=message or "",
                        raw_line=raw_line,
                        metadata=metadata,
                        distance=float(distance),
                    )
                )

    logger.info("Retrieved %s log chunks (top_k=%s) in %.3fs", len(rows), top_k, time.perf_counter() - start)
    return rows


def _build_llm(*, dotenv_path: str | None = None) -> ChatOpenAI:
    api_key, model_name = load_openai_settings(dotenv_path)
    return ChatOpenAI(model=model_name, api_key=api_key, temperature=0)


def _format_context(chunks: Sequence[RetrievedChunk]) -> str:
    if not chunks:
        return "No matching log events found."
    lines = []
    for chunk in chunks:
        lines.append(f"[{chunk.id}] dist={chunk.distance:.4f}: {chunk.message}")
    return "\n".join(lines)


def answer_with_rag(
    question: str,
    *,
    query_vector: Sequence[float],
    top_k: int = 5,
    dotenv_path: str | None = None,
) -> dict[str, Any]:
    """
    Retrieve similar log_event rows via pgvector using a provided embedding vector and answer using OpenAI chat completion.
    Returns a dict with answer text and the retrieved sources.
    """
    overall_start = time.perf_counter()
    logger.info("Starting RAG flow: top_k=%s", top_k)

    stage_start = time.perf_counter()
    chunks = _query_similar_logs(query_vector, top_k=top_k, dotenv_path=dotenv_path)
    logger.info("Finished embedding lookup in %.3fs", time.perf_counter() - stage_start)

    context_text = _format_context(chunks)

    stage_start = time.perf_counter()
    prompt = PromptTemplate(
        input_variables=["question", "context"],
        template=(
            "You are an SRE assistant analyzing application logs.\n"
            "Use the provided context to answer the question concisely.\n"
            "You may infer standard failure semantics commonly associated with the observed exceptions,\n"
            "but do not invent events not implied by the logs.\n\n"
            "Classify outcomes as:\n"
            "- TRANSIENT (error occurred but recovered)\n"
            "- TERMINAL (workflow failed)\n"
            "- NONE (no failure)\n\n"
            "Context:\n{context}\n\n"
            "Question: {question}\n"
            "Answer:"
        ),
    )

    chain = prompt | _build_llm(dotenv_path=dotenv_path) | StrOutputParser()
    logger.info("Built prompt and LLM in %.3fs", time.perf_counter() - stage_start)
    logger.info("Invoking LLM chain: %s", chain)

    stage_start = time.perf_counter()
    answer = chain.invoke({"question": question, "context": context_text})
    logger.info("LLM response received in %.3fs", time.perf_counter() - stage_start)

    sources = [
        {
            "id": chunk.id,
            "message": chunk.message,
            "raw_line": chunk.raw_line,
            "distance": chunk.distance,
        }
        for chunk in chunks
    ]

    logger.info("RAG flow completed in %.3fs", time.perf_counter() - overall_start)
    return {"answer": answer, "sources": sources}


# ============================================================
# CLI helper to hit the HTTP endpoint for quick testing
# ============================================================


def _parse_vector_arg(value: str) -> list[float]:
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [float(x) for x in parsed]
    except json.JSONDecodeError:
        pass
    return [float(x.strip()) for x in value.split(",") if x.strip()]


def _fetch_embedding_by_id(row_id: int, dotenv_path: str | None = None) -> list[float]:
    start = time.perf_counter()
    config = PgVectorConnectionConfig.from_env(dotenv_path)
    manager = PgVectorConnectionManager(config)
    sql = "SELECT embedding FROM log_event WHERE id = %(id)s;"
    with manager.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"id": row_id})
            result = cur.fetchone()
            if not result:
                raise ValueError(f"log_event id {row_id} not found")
            embedding = [float(v) for v in result[0]]
            logger.info("Fetched embedding for id=%s in %.3fs", row_id, time.perf_counter() - start)
            return embedding


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a RAG query to the Flask endpoint.")
    parser.add_argument("--url", default="http://localhost:5000/api/rag/query", help="RAG endpoint URL")
    parser.add_argument("--question", required=True, help="Question to send to the LLM")
    parser.add_argument("--vector", help="Embedding vector as JSON array or comma-separated floats")
    parser.add_argument("--row-id", type=int, help="Use embedding from this log_event id as the query vector")
    parser.add_argument("--top-k", type=int, default=5, help="Number of neighbors to retrieve")
    parser.add_argument("--dotenv", type=str, default=None, help="Path to .env with PG_* vars (if using --row-id)")
    args = parser.parse_args()

    if args.vector:
        query_vector = _parse_vector_arg(args.vector)
    elif args.row_id:
        query_vector = _fetch_embedding_by_id(args.row_id, dotenv_path=args.dotenv)
    else:
        parser.error("Provide either --vector or --row-id to supply a query embedding.")
        return

    payload = {"question": args.question, "vector": query_vector, "top_k": args.top_k}
    logger.info("Sending RAG HTTP request to %s", args.url)
    http_start = time.perf_counter()
    resp = requests.post(args.url, json=payload, timeout=30)
    logger.info("HTTP request completed in %.3fs", time.perf_counter() - http_start)
    print("Status:", resp.status_code)
    try:
        print(json.dumps(resp.json(), indent=2))
    except Exception:
        print(resp.text)


if __name__ == "__main__":
    main()
