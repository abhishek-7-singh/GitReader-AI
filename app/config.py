import os
from dotenv import load_dotenv
load_dotenv()
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "qwen2.5-coder:3b")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
CHROMA_DIR = os.getenv("CHROMA_DIR", "./data/chroma")
SQLITE_PATH = os.getenv("SQLITE_PATH", "./data/app.db")
REPOS_DIR = os.getenv("REPOS_DIR", "./data/repos")
DOCS_UPLOAD_DIR = os.getenv("DOCS_UPLOAD_DIR", "./data/uploads")
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")
MAX_FILE_BYTES = int(os.getenv("MAX_FILE_BYTES", "500000"))
