# Repo Intelligence Assistant

Local-first GitHub repository knowledge assistant: repository ingestion, change logbook, draft release notes, document parsing, and RAG chat with Ollama.

## Requirements
- Python 3.11+
- Git
- Ollama

Pull models:
```bash
ollama pull qwen2.5-coder:3b
ollama pull nomic-embed-text
```

## Run on Windows PowerShell
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/docs.

## First use
POST `/repositories/ingest` with `{"name":"my-project","path":"C:/path/to/local/git/clone"}`.
POST `/chat` with `{"question":"Where is authentication handled?","repository":"my-project"}`.
POST `/documents/ingest` with `{"path":"C:/docs/architecture.pdf","repository":"my-project"}`.

GitHub webhook: configure `GITHUB_WEBHOOK_SECRET`, set a GitHub webhook to `/webhooks/github`, subscribe to push events, and use HTTPS for any deployed endpoint. This starter verifies webhook signatures and records push commit metadata. A GitHub App installation-token sync worker is a next milestone; this starter does not automatically fetch private repo contents from GitHub.

## Important
This is an MVP scaffold, not production-ready. Before multi-user deployment add GitHub App auth, a durable background queue, repository-level authorization, incremental indexing, PostgreSQL, rate limits, retries, observability and tests. Never execute repository code. Treat source files and documents as untrusted input. Review release notes before publishing.
