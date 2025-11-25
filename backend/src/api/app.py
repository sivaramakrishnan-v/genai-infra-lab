from flask import Flask, jsonify, request
from flask_cors import CORS
import os

def create_app():
    app = Flask(__name__)
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
    
    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app = create_app()
    app.run(host="0.0.0.0", port=port)
