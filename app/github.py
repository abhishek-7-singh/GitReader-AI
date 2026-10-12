import os
import subprocess
import hashlib
import hmac
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from .config import GITHUB_WEBHOOK_SECRET, REPOS_DIR
from .db import record_commit, record_change_log, get_repository, upsert_repository

def verify_signature(body: bytes, header: Optional[str]) -> bool:
    """Verify GitHub webhook HMAC SHA256 signature if secret is configured."""
    if not GITHUB_WEBHOOK_SECRET:
        # If no secret is set in config, allow for local developer testing
        return True
    if not header:
        return False
    digest = hmac.new(GITHUB_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest("sha256=" + digest, header)

def get_repo_name_from_url(url: str) -> str:
    """Extract clean repo name from GitHub URL like https://github.com/owner/repo.git"""
    clean = url.rstrip("/").removesuffix(".git")
    parts = clean.split("/")
    if len(parts) >= 2:
        return f"{parts[-2]}_{parts[-1]}"
    return parts[-1] if parts else "repo"

def clone_or_pull_github_repo(repo_url: str, repo_name: Optional[str] = None, branch: Optional[str] = None) -> Dict[str, Any]:
    """Clone a GitHub repository URL or pull latest changes if already cloned."""
    Path(REPOS_DIR).mkdir(parents=True, exist_ok=True)
    name = repo_name or get_repo_name_from_url(repo_url)
    target_dir = Path(REPOS_DIR) / name

    if (target_dir / ".git").exists():
        # Repository already exists, pull latest
        try:
            cmd = ["git", "-C", str(target_dir), "pull"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            action = "pulled"
            output = result.stdout.strip()
        except subprocess.CalledProcessError as e:
            action = "pull_failed"
            output = e.stderr.strip()
    else:
        # Clone repository
        cmd = ["git", "clone"]
        if branch:
            cmd.extend(["-b", branch])
        cmd.extend([repo_url, str(target_dir)])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            action = "cloned"
            output = result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise ValueError(f"Git clone failed: {e.stderr.strip()}")

    # Get HEAD commit sha
    try:
        head_sha = subprocess.check_output(
            ["git", "-C", str(target_dir), "rev-parse", "HEAD"],
            text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        head_sha = "unknown"

    # Get current branch
    try:
        current_branch = subprocess.check_output(
            ["git", "-C", str(target_dir), "rev-parse", "--abbrev-ref", "HEAD"],
            text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        current_branch = branch or "main"

    return {
        "name": name,
        "path": str(target_dir.resolve()),
        "url": repo_url,
        "action": action,
        "branch": current_branch,
        "head_sha": head_sha,
        "output": output,
    }

def fetch_local_git_commits(repo_path: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Extract recent commits and diff stats directly from local git repository."""
    commits = []
    root = Path(repo_path)
    if not (root / ".git").exists():
        return commits

    try:
        # Format: SHA, Author Name, Author Email, ISO Date, Subject
        sep = "<--sep-->"
        cmd = [
            "git", "-C", str(root), "log",
            f"-n{limit}",
            f"--format=%H{sep}%an{sep}%ae{sep}%aI{sep}%s"
        ]
        out = subprocess.check_output(cmd, text=True, errors="replace", stderr=subprocess.DEVNULL)
        lines = [line.strip() for line in out.splitlines() if line.strip()]

        for line in lines:
            parts = line.split(sep)
            if len(parts) >= 5:
                sha, author, email, timestamp, message = parts[0], parts[1], parts[2], parts[3], parts[4]
                # Get files changed for this commit
                try:
                    stat_cmd = ["git", "-C", str(root), "show", "--name-status", "--oneline", sha]
                    stat_out = subprocess.check_output(stat_cmd, text=True, errors="replace", stderr=subprocess.DEVNULL)
                    added, modified, removed = [], [], []
                    for stat_line in stat_out.splitlines()[1:]:
                        if not stat_line.strip():
                            continue
                        tokens = stat_line.split(maxsplit=1)
                        if len(tokens) == 2:
                            status_code, filepath = tokens[0], tokens[1]
                            if status_code.startswith("A"):
                                added.append(filepath)
                            elif status_code.startswith("M"):
                                modified.append(filepath)
                            elif status_code.startswith("D"):
                                removed.append(filepath)
                except Exception:
                    added, modified, removed = [], [], []

                commits.append({
                    "sha": sha,
                    "author": author,
                    "email": email,
                    "timestamp": timestamp,
                    "message": message,
                    "files_added": added,
                    "files_modified": modified,
                    "files_removed": removed,
                })
    except Exception:
        pass
    return commits

def process_push(payload: dict) -> Dict[str, Any]:
    """Process incoming GitHub Push webhook payload, update logbook, and trigger sync."""
    repo_info = payload.get("repository") or {}
    repo_name = repo_info.get("name") or repo_info.get("full_name") or "unknown"
    commits = payload.get("commits") or []
    recorded = 0
    synced_files = []

    for item in commits:
        sha = item.get("id") or item.get("sha")
        if not sha:
            continue
        author_info = item.get("author") or {}
        author = author_info.get("name") or "Developer"
        email = author_info.get("email") or ""
        message = item.get("message") or ""
        timestamp = item.get("timestamp") or datetime.now(timezone.utc).isoformat()
        url = item.get("url") or ""

        added = item.get("added") or []
        modified = item.get("modified") or []
        removed = item.get("removed") or []

        synced_files.extend(added + modified)

        is_new = record_commit(
            repository=repo_name,
            sha=sha,
            author=author,
            email=email,
            message=message,
            timestamp=timestamp,
            url=url,
            files_added=added,
            files_modified=modified,
            files_removed=removed,
        )

        if is_new:
            recorded += 1
            summary = (
                f"Push by {author}: \"{message.strip()}\". "
                f"Changes: {len(added)} added, {len(modified)} modified, {len(removed)} removed."
            )
            diff_stat = f"+{len(added)} ~{len(modified)} -{len(removed)}"
            record_change_log(
                repository=repo_name,
                sha=sha,
                author=author,
                summary=summary,
                diff_stat=diff_stat,
            )

    # Check if this repository is tracked locally and pull if needed
    repo_record = get_repository(repo_name)
    pull_status = None
    if repo_record and Path(repo_record["path"]).exists():
        try:
            subprocess.run(
                ["git", "-C", repo_record["path"], "pull"],
                capture_output=True, text=True, check=True
            )
            pull_status = "Local repository updated via git pull"
        except Exception as e:
            pull_status = f"Git pull skipped or failed: {e}"

    return {
        "repository": repo_name,
        "received_commits": len(commits),
        "new_commits_recorded": recorded,
        "synced_files_count": len(synced_files),
        "pull_status": pull_status,
    }
