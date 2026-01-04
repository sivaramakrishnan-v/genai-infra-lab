import os
import sys
import logging
import time
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from sentence_transformers import SentenceTransformer

# Allow running as script (no parent package) by adding backend/src to sys.path
if __package__ is None:
    current = Path(__file__).resolve()
    src_dir = current.parents[1]  # backend/src
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    from api.rag.log_rag import answer_with_rag  # type: ignore
else:
    from .rag.log_rag import answer_with_rag

_embedder: SentenceTransformer | None = None
logger = logging.getLogger(__name__)

def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder


def create_app():
    # backend/src/api/app.py -> parents[3] is repo root
    static_dir = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    app = Flask(__name__, static_folder=str(static_dir), static_url_path="/")
    CORS(app)

    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"}), 200

    @app.route("/api/version", methods=["GET"])
    def version():
        return jsonify({"version": "0.1.0"}), 200

    @app.route("/api/test", methods=["POST"])
    def test():
        data = request.get_json()
        return jsonify({"echo": data}), 200
    
    @app.route("/api/analyze", methods=["POST"])
    def analyze():
        return jsonify({"echo":"Analyze"}), 200

    @app.route("/api/rag/query", methods=["POST"])
    def rag_query():
        payload = request.get_json(silent=True) or {}
        question = (payload.get("question") or "").strip()
        query_vector = payload.get("vector") or payload.get("question_vector")
        top_k = int(payload.get("top_k", 5))

        if not query_vector:
            return jsonify({"error": "vector is required (384-length embedding)"}), 400

        start = time.perf_counter()
        logger.info("RAG /query start: top_k=%s", top_k)
        try:
            result = answer_with_rag(
                question or "Summarize the relevant log events.",
                query_vector=query_vector,
                top_k=top_k,
            )
            elapsed = time.perf_counter() - start
            logger.info("RAG /query completed in %.3fs", elapsed)
            return jsonify(result), 200
        except Exception as exc:
            logging.exception("RAG query failed")
            return jsonify({"error": str(exc)}), 500

    @app.route("/api/rag/chat", methods=["POST"])
    def rag_chat():
        payload = request.get_json(silent=False) or {}
        question = (payload.get("question") or "").strip()
        top_k = int(payload.get("top_k", 5))

        if not question:
            return jsonify({"error": "question is required"}), 400

        start = time.perf_counter()
        logger.info("RAG /chat start: top_k=%s", top_k)
        try:
            embedder = _get_embedder()
            embed_start = time.perf_counter()
            query_vector = embedder.encode(question).tolist()
            logger.info("Embedding generated in %.3fs", time.perf_counter() - embed_start)
            result = answer_with_rag(
                question or "Summarize the relevant log events.",
                query_vector=query_vector,
                top_k=top_k,
            )
            elapsed = time.perf_counter() - start
            logger.info("RAG /chat completed in %.3fs", elapsed)
            return jsonify(result), 200
        except Exception as exc:
            logging.exception("RAG chat failed")
            return jsonify({"error": str(exc)}), 500

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path: str):
        full_path = static_dir / path
        if path and full_path.exists():
            return send_from_directory(app.static_folder, path)
        return send_from_directory(app.static_folder, "index.html")
    
    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app = create_app()
    app.run(host="0.0.0.0", port=port)
