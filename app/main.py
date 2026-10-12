import os
import json
import shutil
import urllib.request
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .config import DOCS_UPLOAD_DIR, OLLAMA_BASE_URL, OLLAMA_CHAT_MODEL, OLLAMA_EMBED_MODEL
from .db import (
    init_db, list_repositories, get_repository, get_commits,
    get_change_logs, list_documents, save_release_notes, get_release_notes
)
from .ingestion import ingest_repository, ingest_document, build_tree_structure
from .rag import answer_question, generate_ai_release_notes
from .github import verify_signature, process_push, clone_or_pull_github_repo

app = FastAPI(
    title="GitReader AI — Repository Intelligence Platform",
    description="Local-first GitHub code analyzer, push logbook, AI release notes generator, and document RAG assistant.",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup
@app.on_event("startup")
def startup():
    init_db()
    Path(DOCS_UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

# Static files directory
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# Pydantic Schemas
class RepoIngestRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=150, description="Unique repository identifier")
    path: str = Field(..., min_length=1, max_length=3000, description="Local folder path or GitHub URL")
    branch: Optional[str] = Field(None, description="Optional Git branch name")

class DocumentIngestRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=3000)
    repository: str = Field(..., min_length=1, max_length=150)

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=5000)
    repository: Optional[str] = None
    model: Optional[str] = None

class ReleaseNotesGenerateRequest(BaseModel):
    repository: str = Field(..., min_length=1, max_length=150)
    version: Optional[str] = "v1.0.0"
    limit: Optional[int] = 30
    model: Optional[str] = None

# Health & Ollama Status
@app.get("/health")
def health():
    return {"status": "ok", "app": "GitReader AI"}

@app.get("/ollama/status")
def ollama_status():
    """Verify Ollama service and return installed models."""
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            models = [m.get("name") for m in data.get("models", [])]
            return {
                "connected": True,
                "base_url": OLLAMA_BASE_URL,
                "active_chat_model": OLLAMA_CHAT_MODEL,
                "active_embed_model": OLLAMA_EMBED_MODEL,
                "models": models,
            }
    except Exception as e:
        return {
            "connected": False,
            "base_url": OLLAMA_BASE_URL,
            "error": str(e),
            "models": [],
        }

# Repository Endpoints
@app.get("/repositories")
def get_all_repositories():
    return {"repositories": list_repositories()}

@app.post("/repositories/ingest")
def repository_ingest(body: RepoIngestRequest):
    try:
        result = ingest_repository(name=body.name, path_or_url=body.path, branch=body.branch)
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

@app.get("/repositories/{repository}/tree")
def repository_tree(repository: str):
    repo = get_repository(repository)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repository}' not found")
    root_path = Path(repo["path"])
    if not root_path.exists():
        raise HTTPException(status_code=400, detail=f"Local path does not exist: {repo['path']}")

    ascii_tree, nested_tree, tree_stats = build_tree_structure(root_path)
    return {
        "repository": repository,
        "path": str(root_path),
        "ascii_tree": ascii_tree,
        "nested_tree": nested_tree,
        "tree_stats": tree_stats,
    }

@app.post("/repositories/{repository}/sync")
def sync_repository(repository: str):
    """Pull latest Git commits and re-index changes."""
    repo = get_repository(repository)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    try:
        result = ingest_repository(name=repository, path_or_url=repo["path"], branch=repo.get("default_branch"))
        return {"success": True, "message": "Repository synchronized and re-indexed successfully", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {e}")

# Push Logbook & Commits
@app.get("/repositories/{repository}/commits")
def get_repo_commits(repository: str, limit: int = 50):
    return {"repository": repository, "commits": get_commits(repository, limit)}

@app.get("/repositories/{repository}/logbook")
def get_repo_logbook(repository: str, limit: int = 50):
    return {"repository": repository, "entries": get_change_logs(repository, limit)}

# AI Release Notes & Changelogs
@app.post("/repositories/{repository}/release-notes/generate")
def generate_release_notes_endpoint(repository: str, body: Optional[ReleaseNotesGenerateRequest] = None):
    commits = get_commits(repository, limit=(body.limit if body else 30))
    if not commits:
        raise HTTPException(status_code=400, detail=f"No commits recorded for repository '{repository}'.")

    model = body.model if body else None
    version = body.version if body else "v1.0.0"

    try:
        content = generate_ai_release_notes(repository, commits, model=model)
        title = f"Release Notes {version} — {repository}"
        save_release_notes(
            repository=repository,
            title=title,
            version=version,
            markdown_content=content,
            commits_count=len(commits)
        )
        return {
            "repository": repository,
            "version": version,
            "release_notes": content,
            "commits_used": len(commits),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {e}")

@app.get("/repositories/{repository}/release-notes")
def list_repo_release_notes(repository: str, limit: int = 20):
    return {"repository": repository, "release_notes": get_release_notes(repository, limit)}

# Document Ingestion Endpoints
@app.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    repository: str = Form(...)
):
    """Direct drag-and-drop document upload and RAG ingestion."""
    dest_dir = Path(DOCS_UPLOAD_DIR) / repository
    dest_dir.mkdir(parents=True, exist_ok=True)
    target_path = dest_dir / file.filename

    with open(target_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        result = ingest_document(str(target_path), repository=repository, original_filename=file.filename)
        return {"success": True, **result}
    except Exception as e:
        if target_path.exists():
            target_path.unlink()
        raise HTTPException(status_code=400, detail=f"Document parsing failed: {e}")

@app.post("/documents/ingest")
def document_ingest(body: DocumentIngestRequest):
    try:
        result = ingest_document(body.path, body.repository)
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Document ingestion failed: {e}")

@app.get("/documents")
def get_documents(repository: Optional[str] = None):
    return {"documents": list_documents(repository)}

# RAG Chatbot
@app.post("/chat")
def chat(body: ChatRequest):
    try:
        return answer_question(
            question=body.question,
            repository=body.repository,
            model=body.model
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat query failed: {e}")

# GitHub Webhook
@app.post("/webhooks/github")
async def github_webhook(request: Request):
    body = await request.body()
    sig_header = request.headers.get("x-hub-signature-256")
    if not verify_signature(body, sig_header):
        raise HTTPException(status_code=401, detail="Invalid GitHub webhook signature")

    event = request.headers.get("x-github-event", "")
    if event != "push":
        return {"accepted": True, "event": event, "message": f"Event '{event}' acknowledged"}

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in webhook payload")

    result = process_push(payload)
    return {"accepted": True, "event": "push", **result}

# Mount static web app UI
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
def serve_dashboard():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "GitReader AI API active. Visit /docs for Swagger API documentation."}
