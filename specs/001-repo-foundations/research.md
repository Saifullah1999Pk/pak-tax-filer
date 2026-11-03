# Research: Repo Foundations (001)

Each decision: what was chosen, why, and what else was considered.

## R1. Runtime versions

- **Decision:** Python 3.13, Node 24 (LTS), PostgreSQL 17 with pgvector.
- **Rationale:** the README sets minimums (Python 3.12+, Node 20+). Node 20 reached end of
  life in April 2026, so the current LTS is used. Python 3.13 is current and widely supported
  by libraries. PostgreSQL 17 is current and has an official pgvector image.
- **Alternatives:** Python 3.12 (security fixes only now); Python 3.14 (newest, library
  support still catching up); Node 22 (older LTS).

## R2. Backend tooling

- **Decision:** `uv` for dependencies and running; Uvicorn as the server; pytest + HTTPX
  `TestClient` for tests; Ruff for formatting and linting.
- **Rationale:** `uv` is fast, handles Python versions, and is already used on the dev machine.
  These are FastAPI's documented defaults. Ruff replaces Black, isort and Flake8 with one tool.
- **Alternatives:** pip + venv (slower, no lockfile by default); Poetry (heavier); Black +
  Flake8 (three tools instead of one).

## R3. Database layer (for features 002+)

- **Decision:** SQLAlchemy 2.0 (async, with `asyncpg`) and Alembic for migrations. 001 sets up
  Alembic with a single migration that enables the `vector` extension; no tables.
- **Rationale:** the standard FastAPI pairing; pgvector has first-class SQLAlchemy support;
  async fits FastAPI. Enabling the extension in a migration (rather than a Docker init script)
  means every database, not only a fresh Docker volume, gets it, and the README's
  `manage.py migrate` step maps directly to `alembic upgrade head`.
- **Alternatives:** SQLModel (thin layer over SQLAlchemy, fewer docs for advanced cases);
  Docker `initdb` script for the extension (only runs on an empty volume).

## R4. Frontend tooling

- **Decision:** Vite (React + TypeScript template), Vitest + React Testing Library, Prettier.
- **Rationale:** Vite's dev server defaults to port 5173, matching the README; Vitest shares
  Vite's config, so `npm test` needs no extra setup.
- **Alternatives:** Create React App (deprecated); Jest (separate config for TypeScript/ESM).

## R5. Claude Code hooks: mechanism and language

- **Decision:** two hooks registered in the shared `.claude/settings.json`, each a small Python
  script in `.claude/hooks/` using only the standard library, run with
  `uv run --no-project python`.
  - **Tax-rates guard:** a `PreToolUse` hook on `Edit`, `Write`, `MultiEdit` and `Bash`. If the
    target path (or, for `Bash`, the command text) refers to `backend/app/tax/rates/`, it
    returns `permissionDecision: "ask"` with the FBR reason. Otherwise it returns nothing and
    normal rules apply.
  - **Format-on-write:** a `PostToolUse` hook on `Edit`, `Write`, `MultiEdit`. Runs
    `uvx ruff format` for `.py` files and `npx prettier --write` for `.ts`, `.tsx`, `.js`,
    `.jsx`, `.css`. If the formatter fails, the file is left as written and the failure is
    reported back to Claude.
- **Rationale:** Python runs the same on Windows, macOS and Linux; `uv` guarantees a Python
  interpreter regardless of whether the OS calls it `python` or `python3`. A hook (rather than
  a permission rule alone) can explain *why* it asks, and can inspect `Bash` commands.
- **Alternatives:** shell or PowerShell hooks (not cross-platform); a permission `ask` rule on
  the folder (can't give the FBR reason or see shell commands); running formatters inside
  the containers (would require the stack to be running while editing).
- **Consequence:** `uv` and Node become host prerequisites for contributors using Claude Code;
  the README lists them.

## R6. Permissions

- **Decision:** shared `permissions` in `.claude/settings.json`:
  - **allow:** pytest, Ruff, Vitest/`npm test`, Prettier, read-only git (`status`, `diff`,
    `log`, `show`, `branch`), `docker compose ps`/`logs`;
  - **ask:** `git push`, file deletion (`rm`, `git rm`);
  - **deny:** reading `.env` and `.env.*`.
  Personal overrides stay in the git-ignored `.claude/settings.local.json`.
- **Rationale:** matches the spec (FR-011) and the constitution's Secrets rule.
- **Alternatives:** allow everything (unsafe); per-developer settings only (not shared, so
  FR-012 fails).

## R7. Health check

- **Decision:** `GET /health` returns `200` with `{"status": "ok"}`.
- **Rationale:** the simplest common convention; enough for the spec (FR-003). Database
  connectivity checks come with the first feature that uses the database.
