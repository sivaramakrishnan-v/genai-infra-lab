import os

# -----------------------------
# Project Root
# -----------------------------
PROJECT_ROOT = "genai-infra-lab"

# -----------------------------
# Folder Structure Definition
# -----------------------------
STRUCTURE = [
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
    "infra/docker",
    "infra/terraform",
    "infra/ci_cd/github/workflows",
    "infra/ci_cd/pipeline",
    "tests/api",
    "tests/agents",
    "tests/vectorstore",
    "tests/pipelines",
    "tests/integration",
    "data/raw",
    "data/processed",
    "data/embeddings",
    "docs/architecture",
    "docs/decisions",
    "docs/runbooks"
]

# -----------------------------
# Placeholder Files
# -----------------------------
FILES = [
    ".env.example",
    "requirements.txt",
    "README.md",
    ".gitignore",
    "src/api/main.py",
    "src/utils/config.py",
    "src/utils/logging.py"
]

# -----------------------------
# Generate Folders + Files
# -----------------------------
def create_project():
    print(f"Creating project structure in '{PROJECT_ROOT}' ...")

    # Create folders
    for path in STRUCTURE:
        folder_path = os.path.join(PROJECT_ROOT, path)
        os.makedirs(folder_path, exist_ok=True)

    # Create files
    for file in FILES:
        file_path = os.path.join(PROJECT_ROOT, file)
        if not os.path.exists(file_path):
            with open(file_path, "w") as f:
                f.write("")  # empty placeholder

    print("Project scaffolding completed successfully.")


if __name__ == "__main__":
    create_project()
