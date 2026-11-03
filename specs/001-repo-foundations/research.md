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

## R8. CI (added for issues #4/#5)

- **Decision:** one GitHub Actions workflow, `.github/workflows/ci.yml`, on every pull request
  and push to `main`, with three jobs: **backend** (uv; `ruff check`, `ruff format --check`,
  `mypy app`, `pytest` against a PostgreSQL + pgvector service container), **frontend**
  (`npm ci`, `prettier --check`, `tsc --noEmit`, `npm test`) and **hooks** (`pytest
  .claude/hooks/tests`). The eval gate is added when the first eval exists (003, 006).
- **Rationale:** the constitution's merge gate needs lint, type checks and tests; separate jobs
  run in parallel and show exactly which part failed. Running Postgres as a service container
  matches the real database.
- **Alternatives:** one combined job (slower, unclear failures); running CI through Docker
  Compose (slower startup, harder caching); Pyright instead of mypy (either works; mypy is the
  more common default with SQLAlchemy and Pydantic plugins).

## R9. Claude Code conventions layout (added for issues #4/#5)

- **Decision:**
  - `backend/CLAUDE.md` and `frontend/CLAUDE.md`: short folder guides, loaded when Claude works
    in that folder; they don't repeat the root `CLAUDE.md`.
  - `.claude/rules/`: one file per topic: `architecture.md`, `backend.md`, `frontend.md`,
    `api.md`, `testing.md`, `security.md`. Backend- and frontend-specific rules are scoped to
    their folders with `paths` front matter.
  - `.claude/skills/`: `fastapi-feature`, `react-feature`, `code-review` (next to the existing
    `speckit-*` skills).
  - `.claude/agents/`: `backend-reviewer.md`, `frontend-reviewer.md`, each with read-only tools.
- **Rationale:** these are Claude Code's own locations for each kind of guidance, so they load
  automatically; one concern per file keeps each short and avoids duplication (issue #5).
- **Alternatives:** one long `CLAUDE.md` (hard to maintain, always fully loaded); reviewers with
  write access (a reviewer should report, not change code).

## R10. API convention (added for issue #4)

- **Decision:** `docs/api-conventions.md` is the written standard (see
  [contracts/api-conventions.md](contracts/api-conventions.md)); `.claude/rules/api.md` points to
  it. Each feature's API contract lives in its `specs/NNN-*/contracts/` and follows it. FastAPI's
  generated OpenAPI schema is the machine-readable source the frontend can check against.
- **Rationale:** one human-readable standard, per-feature contracts reviewed with the spec, and
  an automatically generated schema that can't drift from the code.
