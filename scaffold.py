import os

# =========================================================
# Project Layout:
#   /backend   → all Python code & pipelines
#   /frontend  → React UI (Vite)
#   root files → requirements.txt, Dockerfile, README.md, etc.
# =========================================================

BACKEND_ROOT = "backend"
FRONTEND_ROOT = "frontend"

# =========================================================
# Backend Folder Structure (matches your real project)
# =========================================================
BACKEND_STRUCTURE = [
    "src/api/routes",
    "src/api/models",
    "src/agents/graph/nodes",
    "src/agents/graph/state",
    "src/agents/tools",
    "src/agents/llm",
    "src/vectorstore/config",
    "src/vectorstore/client",
    "src/vectorstore/schema",
    "src/vectorstore/ops",
    "src/pipelines/ingestion",
    "src/pipelines/cleaning",
    "src/pipelines/embeddings",
    "src/pipelines/scheduler",
    "src/pipelines/jobs",
    "src/monitoring/otel",
    "src/monitoring/logs",
    "src/monitoring/metrics",
    "src/monitoring/tracing",
    "src/utils",
    "data/raw",
    "data/processed",
    "data/embeddings",
    "docs/architecture",
    "docs/decisions",
    "docs/runbooks",
    "infra/docker",
    "infra/terraform",
    "infra/ci_cd/github/workflows",
    "infra/ci_cd/pipeline",
    "tests/api",
    "tests/agents",
    "tests/vectorstore",
    "tests/pipelines",
    "tests/integration",
]

# =========================================================
# Backend Placeholder Files (only created if missing)
# =========================================================
BACKEND_FILES = [
    "src/api/main.py",
    "src/utils/config.py",
    "src/utils/logging.py",
]

# =========================================================
# Frontend Structure (React + Vite)
# =========================================================
FRONTEND_STRUCTURE = [
    "src/components",
    "src/pages",
    "src/hooks",
    "src/assets",
    "public",
]

FRONTEND_FILES = [
    "README.md",
    ".gitignore",
    "index.html",       # placeholder, Vite will replace it
    "package.json",     # placeholder
    "vite.config.js",   # placeholder
]

# =========================================================
# Create folders + files (safe)
# =========================================================
def create_scaffold(root, structure, files):
    print(f"\n📁 Ensuring structure under: {root}")

    for path in structure:
        folder = os.path.join(root, path)
        os.makedirs(folder, exist_ok=True)

    for file in files:
        file_path = os.path.join(root, file)
        if not os.path.exists(file_path):
            with open(file_path, "w") as f:
                f.write("")

    print(f"✅ OK: {root}")

# =========================================================
# Main
# =========================================================
def create_project():
    print("\n🚀 Setting up backend + frontend folders...\n")

    # Create backend structure
    create_scaffold(BACKEND_ROOT, BACKEND_STRUCTURE, BACKEND_FILES)

    # Create frontend structure
    create_scaffold(FRONTEND_ROOT, FRONTEND_STRUCTURE, FRONTEND_FILES)

    print("\n🎉 Project scaffolding complete! ✓")

if __name__ == "__main__":
    create_project()
