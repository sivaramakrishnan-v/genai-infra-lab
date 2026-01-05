# GenAI Infra Lab

A minimal RAG lab combining a Flask API, PostgreSQL/pgvector, and a React/Vite chat UI for log analysis experiments.

## Stack
- Flask API with SentenceTransformers embeddings and LangChain ChatOpenAI responses
- PostgreSQL + pgvector for similarity search
- React 19 + Vite UI (built assets served by Flask in production)
- Dockerfile for a Python 3.11 backend image

## Repo Layout
- backend/src/api: Flask app and RAG endpoints
- backend/src/vectorstore: pgvector connection + query helpers
- frontend: React app; `npm run build` outputs to `frontend/dist` served by Flask
- Dockerfile: backend-only container (uses root requirements.txt)

## Prerequisites
- Python 3.11+
- Node 20+
- PostgreSQL with pgvector extension enabled
- OpenAI API key; AWS credentials optional for Bedrock helpers
- Docker (optional)

## Environment
Create `.env` at the repo root (backend auto-loads it):
```
PG_HOST=localhost
PG_PORT=5432
PG_DATABASE=genai
PG_USER=genai
PG_PASSWORD=changeme
OPENAI_API_KEY=***YOUR_API_KEY***
OPENAI_MODEL=gpt-4o-mini
LOG_LEVEL=INFO
AWS_REGION=us-east-1        # optional, Bedrock helpers
BEDROCK_PROMPT=what is sre? # optional, Bedrock helpers
```

## Backend Setup
```
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Frontend Build (served by Flask)
```
cd frontend
npm install
npm run build  # outputs to frontend/dist
cd ..
```

## Run Backend (serves API + built UI)
```
# ensure the frontend is built first
# Windows PowerShell
$env:PYTHONPATH="backend"
python backend/src/api/app.py

# macOS/Linux
export PYTHONPATH=backend
python backend/src/api/app.py
```
App listens on http://localhost:5000.

## Frontend Dev Server (optional)
```
cd frontend
npm run dev -- --host
```
For API calls during dev, add a proxy to `vite.config.js`:
```
server: { proxy: { "/api": "http://localhost:5000" } }
```
(or call the backend with a full URL).

## Docker
```
docker build -t genai-infra-lab .
docker run -p 5000:5000 --env-file .env genai-infra-lab
```
Note: the Dockerfile currently ships the backend only. To serve the UI, build `frontend/dist` and copy it into the image (or mount it).

## Smoke Test
```
# with venv active
$env:PYTHONPATH="backend"  # or export PYTHONPATH=backend
python backend/src/api/main.py
```

## Database
Ensure pgvector is installed and a `log_event` table with an `embedding` vector column exists; RAG queries read from it.
