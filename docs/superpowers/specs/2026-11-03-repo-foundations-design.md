# 001 Repo Foundations: Design

**Date:** 2026-11-03 · **Status:** Proposed · **Feature:** 001 (README milestone 1) ·
**Governed by:** [Constitution v1.2.0](../../../.specify/memory/constitution.md)

## Intent

README milestone 1: "Docker Compose skeleton, `CLAUDE.md`, Claude Code hooks (guard the
tax-rates module, format-on-write) and permission settings." This gives every later feature a
running, empty app and a Claude Code setup that enforces the constitution from day one. No
product features are built here.

## Scope

1. **Docker Compose skeleton:** `db` (PostgreSQL + pgvector), `backend` (FastAPI),
   `frontend` (React + TypeScript). Matches the README's setup section: `docker compose up -d`
   starts all three; backend on `http://localhost:8000`, frontend on `http://localhost:5173`;
   tests via `docker compose exec backend pytest` and `docker compose exec frontend npm test`.
2. **`CLAUDE.md`:** a short guide for Claude Code: the constitution's key rules, the repo
   layout, and the commands to run, test and format.
3. **Hooks** (shared, in `.claude/settings.json`):
   - **Tax-rates guard:** any attempt by Claude to change the tax-rates module pauses and asks
     the person at the keyboard to approve, explaining that rates must come from FBR's
     gazetted documents (Principle II). It asks; it does not block.
   - **Format-on-write:** every file Claude writes is formatted automatically.
4. **Permission settings** (shared): what Claude may do without asking, must ask about, and
   must never do.
5. **README setup section** updated for FastAPI (replacing the Django `manage.py` step).

## Out of scope

Auth, database tables, any tax logic, CI (feature 008), any real data.

## Decisions

- **Guard behaviour:** ask for approval, not block (decided by Saifullah).
- **Layout:** `backend/` and `frontend/` at the repo root with `docker-compose.yml`, as the
  README's setup implies.
- **Tax-rates module path:** `backend/app/tax/rates/`, fixed now so the guard protects it
  before feature 004 fills it. *(Builder's call.)*
- **Hooks are written in Python**, so they run the same on Windows, macOS and Linux.
  *(Builder's call.)*
- **Tooling:** `uv` for Python dependencies; Vite for the frontend (its default port is
  5173); Ruff (Python) and Prettier (TypeScript) as formatters; pytest and Vitest behind the
  README's test commands. *(Builder's call; standard choices.)*
- **Permissions:** allow tests, linters, formatters and read-only git commands; ask before
  `git push` and deletions; deny reading `.env` files (constitution, Secrets).
  *(Builder's call.)*

## Approaches

The tax-rates guard could be a **Claude Code hook** (a script that runs before each file
change) or a **permission "ask" rule** on the folder. The README names hooks, and a hook can
explain *why* it is asking, so the guard is a hook.

## Done when

- `docker compose up -d` on a fresh clone starts `db`, `backend` and `frontend`.
- `GET http://localhost:8000/health` returns OK; `http://localhost:5173` shows a placeholder
  page; the `vector` extension is enabled in the database.
- `pytest` and `npm test` each run at least one passing test inside their containers.
- Editing a file under `backend/app/tax/rates/` through Claude triggers an approval prompt
  with the FBR reason.
- A file Claude writes comes out formatted.
- Claude cannot read `.env`.
- The README setup section works as written for FastAPI.

## Left to the plan

Database layer and migrations (likely SQLAlchemy + Alembic), Python and Node versions within
the README's minimums (3.12+, 20+), Dockerfile details, and the exact hook scripts.
