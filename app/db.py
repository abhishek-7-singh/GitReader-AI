import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone
from .config import SQLITE_PATH

def connect():
    Path(SQLITE_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS repositories (
            name TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            url TEXT,
            default_branch TEXT DEFAULT 'main',
            last_indexed_at TEXT,
            last_commit_sha TEXT,
            total_files INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS commits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repository TEXT NOT NULL,
            sha TEXT NOT NULL,
            author TEXT,
            email TEXT,
            message TEXT,
            timestamp TEXT,
            url TEXT,
            files_added TEXT,
            files_modified TEXT,
            files_removed TEXT,
            UNIQUE(repository, sha)
        );

        CREATE TABLE IF NOT EXISTS change_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repository TEXT NOT NULL,
            sha TEXT NOT NULL,
            author TEXT,
            summary TEXT NOT NULL,
            diff_stat TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repository TEXT NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            chunk_count INTEGER DEFAULT 0,
            file_type TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS release_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repository TEXT NOT NULL,
            title TEXT NOT NULL,
            version TEXT,
            markdown_content TEXT NOT NULL,
            commits_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        ''')

def upsert_repository(name: str, path: str, url: str = None, branch: str = "main", last_commit_sha: str = None, total_files: int = 0):
    now = datetime.now(timezone.utc).isoformat()
    with connect() as c:
        c.execute('''
            INSERT INTO repositories(name, path, url, default_branch, last_indexed_at, last_commit_sha, total_files)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                path = excluded.path,
                url = COALESCE(excluded.url, repositories.url),
                default_branch = COALESCE(excluded.default_branch, repositories.default_branch),
                last_indexed_at = excluded.last_indexed_at,
                last_commit_sha = COALESCE(excluded.last_commit_sha, repositories.last_commit_sha),
                total_files = excluded.total_files
        ''', (name, path, url, branch, now, last_commit_sha, total_files))

def get_repository(name: str):
    with connect() as c:
        row = c.execute("SELECT * FROM repositories WHERE name = ?", (name,)).fetchone()
        return dict(row) if row else None

def list_repositories():
    with connect() as c:
        return [dict(x) for x in c.execute("SELECT * FROM repositories ORDER BY name")]

def record_commit(repository: str, sha: str, author: str, message: str, timestamp: str, url: str = "",
                  email: str = "", files_added: list = None, files_modified: list = None, files_removed: list = None):
    with connect() as c:
        cur = c.execute('''
            INSERT OR IGNORE INTO commits(
                repository, sha, author, email, message, timestamp, url, files_added, files_modified, files_removed
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            repository, sha, author, email, message, timestamp, url,
            json.dumps(files_added or []),
            json.dumps(files_modified or []),
            json.dumps(files_removed or [])
        ))
        return cur.rowcount > 0

def get_commits(repository: str, limit: int = 50):
    with connect() as c:
        rows = c.execute(
            "SELECT * FROM commits WHERE repository = ? ORDER BY id DESC LIMIT ?",
            (repository, min(max(limit, 1), 200))
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try: d["files_added"] = json.loads(d.get("files_added") or "[]")
            except Exception: d["files_added"] = []
            try: d["files_modified"] = json.loads(d.get("files_modified") or "[]")
            except Exception: d["files_modified"] = []
            try: d["files_removed"] = json.loads(d.get("files_removed") or "[]")
            except Exception: d["files_removed"] = []
            result.append(d)
        return result

def record_change_log(repository: str, sha: str, summary: str, author: str = "", diff_stat: str = ""):
    with connect() as c:
        c.execute('''
            INSERT INTO change_logs(repository, sha, author, summary, diff_stat)
            VALUES(?, ?, ?, ?, ?)
        ''', (repository, sha, author, summary, diff_stat))

def get_change_logs(repository: str, limit: int = 50):
    with connect() as c:
        return [dict(x) for x in c.execute(
            "SELECT * FROM change_logs WHERE repository = ? ORDER BY id DESC LIMIT ?",
            (repository, min(max(limit, 1), 200))
        )]

def record_document(repository: str, filename: str, file_path: str, file_size: int, chunk_count: int, file_type: str):
    with connect() as c:
        c.execute('''
            INSERT INTO documents(repository, filename, file_path, file_size, chunk_count, file_type)
            VALUES(?, ?, ?, ?, ?, ?)
        ''', (repository, filename, file_path, file_size, chunk_count, file_type))

def list_documents(repository: str = None):
    with connect() as c:
        if repository:
            return [dict(x) for x in c.execute("SELECT * FROM documents WHERE repository = ? ORDER BY id DESC", (repository,))]
        return [dict(x) for x in c.execute("SELECT * FROM documents ORDER BY id DESC")]

def save_release_notes(repository: str, title: str, version: str, markdown_content: str, commits_count: int = 0):
    with connect() as c:
        c.execute('''
            INSERT INTO release_notes(repository, title, version, markdown_content, commits_count)
            VALUES(?, ?, ?, ?, ?)
        ''', (repository, title, version, markdown_content, commits_count))

def get_release_notes(repository: str, limit: int = 20):
    with connect() as c:
        return [dict(x) for x in c.execute(
            "SELECT * FROM release_notes WHERE repository = ? ORDER BY id DESC LIMIT ?",
            (repository, min(max(limit, 1), 50))
        )]
