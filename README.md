# genai-infra-lab

# GenAI Vectorstore Client

A lightweight, Python client for working with **PostgreSQL + pgvector** in GenAI and RAG applications.

This project provides:
- A reusable **Connection Manager**
- A high-level **VectorStoreClient** for embeddings
- Safe helpers for executing, fetching, and managing queries
- Local development environment setup
- End-to-end connection tests

---

## 🚀 Features

### ✓ Clean Postgres Connection Manager  
Simplifies handling database connections, DSNs, and environment variables.

### ✓ Automatic pgvector Registration  
Ensures vector types are available on every connection.

### ✓ High-Level Database Client  
Utilities for:
- `execute(sql, params)`
- `fetch_one(sql, params)`
- `fetch_all(sql, params)`
- `insert_embedding(vector)`
- `similarity_search(query_vector, top_k)`

### ✓ Full Logging Support  
Structured logs for debugging and visibility.

### ✓ Easy Integration with GenAI Pipelines  
Designed for:
- RAG systems  
- LLM knowledge stores  
- LangGraph/LangChain agents  
- Embedding pipelines  

---

## 📦 Project Structure


---

## 🛠 Installation

### 1. Clone the repository

git clone https://github.com/sivaramakrishnan-v/genai-infra-lab.git
cd genai-vectorstore

## 2. Create your virtual environment

python -m venv genailab-env
source genailab-env/bin/activate     # macOS/Linux
genailab-env\Scripts\activate        # Windows

3. Requirements
pip install -r requirements.txt


