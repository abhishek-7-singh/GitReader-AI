# GitReader AI — Repository Intelligence Platform

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi" alt="FastAPI" />
  <img src="https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white" alt="LangChain" />
  <img src="https://img.shields.io/badge/Ollama-000000?style=for-the-badge&logo=ollama&logoColor=white" alt="Ollama" />
  <img src="https://img.shields.io/badge/ChromaDB-FF6600?style=for-the-badge" alt="ChromaDB" />
  <img src="https://img.shields.io/badge/SQLite-07405E?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite" />
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
</p>

A local-first, privacy-respecting GitHub code analyzer, developer push logbook, AI release notes synthesizer, multi-format document parser, and context-aware RAG chatbot powered by **LangChain**, **ChromaDB**, and **Ollama**.

---

## 🌟 Key Features

1. **GitHub Ingestion & Interactive Tree Explorer**:
   - Ingest any local Git directory or clone directly from a public or private GitHub repository (`https://github.com/owner/repo`).
   - Generates interactive hierarchical trees, formatted ASCII directory views, and language/file-size distribution statistics.

2. **Real-Time Push Logbook & Git Analytics**:
   - Maintains an automated SQLite logbook recording every developer push.
   - Captures author, timestamp, commit SHA, message, and files added, modified, or removed (`+added ~modified -deleted`).
   - GitHub webhook endpoint (`/webhooks/github`) with HMAC SHA-256 signature verification.
   - Built-in Push Simulator to test developer workflows without setting up external tunnels.

3. **AI Release Notes & Changelog Synthesizer**:
   - One-click release notes synthesis using local LLMs (e.g., `qwen2.5-coder:3b` or `llama3`).
   - Automatically categorizes changes into **Release Overview**, **Features & Enhancements**, **Bug Fixes**, **Refactoring & Maintenance**, and **Developer Contributions**.

4. **Multi-Format Document Parsing**:
   - Drag-and-drop parsing and vector indexing for Architecture PDFs (`.pdf`), Word specifications (`.docx`), Markdown design documents (`.md`), and plain text (`.txt`).
   - Unified retrieval across both source code and technical documentation.

5. **Grounded RAG Chatbot (LangChain + Ollama)**:
   - High-precision Q&A grounded strictly in the repository codebase and parsed documents.
   - Prevents hallucinations and provides verbatim citations with exact source file paths, commit hashes, and chunk previews.

6. **Modern Dark-Mode Dashboard**:
   - Single-page dashboard served directly by FastAPI at `http://127.0.0.1:8000/`.

---

## 🧠 Architectural Overview

```
[ GitHub Repo / Local Dir ]       [ Architecture PDF / Word Docs ]
             │                                   │
             ▼                                   ▼
    [ GitReader Ingestion ]             [ Document Parser ]
   (Directory Walk + AST Chunking)      (PyPDF / python-docx)
             │                                   │
             └─────────────────┬─────────────────┘
                               │
                               ▼
     [ LangChain RecursiveCharacterTextSplitter ]
                               │
                               ▼
        [ Ollama nomic-embed-text (Embeddings) ]
                               │
                               ▼
            [ ChromaDB Vector Store (Local) ]
                               │
                      Similarity Retrieval
                               │
                               ▼
          [ LangChain Grounded QA Prompt ]
                               │
                               ▼
        [ Ollama qwen2.5-coder:3b / llama3 (LLM) ]
                               │
                               ▼
    [ Grounded Technical Answers + File Citations ]
```

---

## 🗄️ Database Architecture & Storage

GitReader AI utilizes a dual-engine storage model designed for privacy and local-first execution:

### 1. Relational SQLite Database (`data/app.db`)
Stores structured metadata, Git commit histories, push logbooks, parsed document registries, and generated release notes.

#### Schema Overview:

```sql
-- Tracked Repositories
CREATE TABLE repositories (
    name TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    url TEXT,
    default_branch TEXT DEFAULT 'main',
    last_indexed_at TEXT,
    last_commit_sha TEXT,
    total_files INTEGER DEFAULT 0
);

-- Commit History & Diff Breakdown
CREATE TABLE commits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repository TEXT NOT NULL,
    sha TEXT NOT NULL,
    author TEXT,
    email TEXT,
    message TEXT,
    timestamp TEXT,
    url TEXT,
    files_added TEXT,      -- JSON array of added file paths
    files_modified TEXT,   -- JSON array of modified file paths
    files_removed TEXT,    -- JSON array of deleted file paths
    UNIQUE(repository, sha)
);

-- Developer Push Logbook
CREATE TABLE change_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repository TEXT NOT NULL,
    sha TEXT NOT NULL,
    author TEXT,
    summary TEXT NOT NULL,
    diff_stat TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Uploaded & Parsed Technical Documents
CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repository TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    file_type TEXT,
    uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- AI Synthesized Release Notes
CREATE TABLE release_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repository TEXT NOT NULL,
    title TEXT NOT NULL,
    version TEXT,
    markdown_content TEXT NOT NULL,
    commits_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### 2. Local ChromaDB Vector Store (`data/chroma/`)
- **Embeddings Model**: `nomic-embed-text` via local Ollama API.
- **Chunking Engine**: LangChain `RecursiveCharacterTextSplitter` configured with code-aware language separators.
- **Vector Indexing**: Chunks are tagged with rich metadata (`repository`, `source`, `filename`, `language`, `chunk_index`).
- **Persistence**: Stored entirely on disk under `data/chroma/` without any external cloud telemetry.

---

## 🚀 Step-by-Step Guide: How to Install and Run

### 1. Prerequisites
- **Python 3.9+** (Check with `python --version`)
- **Git** installed on your system
- **Ollama** installed and running locally ([Download Ollama](https://ollama.ai))

### 2. Install and Start Ollama
Ensure the Ollama daemon is running, then pull the required models:

```bash
# Pull the recommended coder LLM
ollama pull qwen2.5-coder:3b

# Pull the vector embedding model
ollama pull nomic-embed-text
```

Verify that the models are installed:
```bash
ollama list
```

### 3. Clone and Setup Environment
Navigate into the project directory:

```bash
cd GitReader-AI
```

Create and activate a virtual environment (optional but recommended):
```powershell
# Windows PowerShell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables (Optional)
Copy `.env.example` to `.env` if you wish to customize port, models, or directories:
```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=qwen2.5-coder:3b
OLLAMA_EMBED_MODEL=nomic-embed-text
CHROMA_DIR=./data/chroma
SQLITE_PATH=./data/app.db
REPOS_DIR=./data/repos
DOCS_UPLOAD_DIR=./data/uploads
GITHUB_WEBHOOK_SECRET=
MAX_FILE_BYTES=500000
```

### 6. Run the Application
Launch the FastAPI server with Uvicorn:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Or via direct Uvicorn CLI:
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 7. Access the Web Dashboard & API Docs
- **Web Dashboard**: Open your browser and go to [`http://127.0.0.1:8000/`](http://127.0.0.1:8000/)
- **Interactive Swagger API Documentation**: [`http://127.0.0.1:8000/docs`](http://127.0.0.1:8000/docs)
- **Alternative ReDoc**: [`http://127.0.0.1:8000/redoc`](http://127.0.0.1:8000/redoc)

---

## 📖 Detailed User Walkthrough

### 1. Ingesting a Repository
- **Local Folder**: Enter a repository name and provide an absolute path on your computer (e.g., `C:\Users\username\Projects\my-app`).
- **Remote GitHub URL**: Enter any public Git repository URL (e.g., `https://github.com/psf/requests`). GitReader will clone the repository into `data/repos/`, index all supported code files (`.py`, `.js`, `.ts`, `.html`, `.css`, `.json`, `.md`, `.go`, `.rs`, `.java`, etc.), split them into semantic chunks, and generate vector embeddings.

### 2. Exploring File Trees & Language Breakdown
- Click the **Tree** tab to view an interactive ASCII and collapsible folder tree.
- View real-time language distributions and file statistics.

### 3. Developer Push Logbook & Webhook Integration
- Connect GitHub webhooks by pointing your repository settings to:
  `http://<your-server-ip>:8000/webhooks/github`
  (Content type: `application/json`, Secret: match `GITHUB_WEBHOOK_SECRET`).
- Alternatively, use the built-in **Push Simulator** from the dashboard to simulate Git push events and view commit diffs (`+added`, `~modified`, `-deleted`).

### 4. Synthesizing AI Release Notes
- Open the **Release Notes** section.
- Select your target repository and click **Generate Release Notes**.
- The local LLM will analyze recent commits, summaries, and file modifications to generate clean, publication-ready Markdown notes.

### 5. Uploading & Ingesting Documents
- Under the **Documents** section, drag and drop `.pdf`, `.docx`, `.md`, or `.txt` files (e.g., system design docs, API specs).
- Files are parsed, split into chunks, and vectorized into ChromaDB alongside repository code.

### 6. Grounded RAG Chatbot
- Select a repository context or query across all ingested sources.
- Ask questions like:
  - *"How does the authentication middleware work?"*
  - *"What database tables are initialized on startup?"*
  - *"Where is the vector embedding logic defined?"*
- Answers are accompanied by exact source code citations and expandable chunk previews.

---

## 📡 API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/` | `GET` | Interactive Web Dashboard UI |
| `/ollama/status` | `GET` | Health check for Ollama connection & installed models |
| `/repositories` | `GET` | List all tracked repositories |
| `/repositories/ingest` | `POST` | Ingest a local repository or clone a GitHub URL |
| `/repositories/{repo}/tree` | `GET` | Retrieve ASCII and nested folder hierarchy with language stats |
| `/repositories/{repo}/sync` | `POST` | Pull latest Git changes and re-index changed files |
| `/repositories/{repo}/commits` | `GET` | List recent commits with file diff breakdown |
| `/repositories/{repo}/logbook` | `GET` | Retrieve developer push logbook timeline |
| `/repositories/{repo}/release-notes/generate` | `POST` | Synthesize release notes and changelog with local LLM |
| `/documents/upload` | `POST` | Upload and parse `.pdf`, `.docx`, `.md`, or `.txt` |
| `/chat` | `POST` | RAG Chatbot query grounded on repository code & docs |
| `/webhooks/github` | `POST` | GitHub push webhook listener (with signature verification) |

---

## 🛡️ Privacy & Security

- **100% Local Inference**: All code embeddings and LLM reasoning run locally via Ollama. No source code or proprietary architecture documents are ever sent to external cloud APIs.
- **Strict Data Ignored**: Database files, vector stores, uploads, and raw documentation are kept local and ignored by `.gitignore` to avoid leaking sensitive data to public remotes.
