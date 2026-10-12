# Roadmap

1. GitHub App installation and secure installation-token flow.
2. Durable background worker for push events; webhook should enqueue and return quickly.
3. Incremental indexing: re-index changed files and delete vectors for removed paths.
4. LLM-based diff summaries and categories (feature, fix, refactor, docs, security, performance).
5. Hybrid retrieval: vector search plus SQL/Git history queries for author/date/path questions.
6. Next.js UI: repository overview, tree, activity log, release notes, document manager, chat.
7. Production: PostgreSQL, queue, auth/RBAC, repository-level retrieval filters, audit logs, rate limits, tests.
8. Add syntax-aware chunking (e.g. Tree-sitter) for functions/classes and citations with line numbers.

Never execute repository code. Apply access controls before retrieval; the model must not decide authorization.
