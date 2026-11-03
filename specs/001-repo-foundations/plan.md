# Implementation Plan: Repo Foundations

**Branch**: `001-repo-foundations` | **Date**: 2026-11-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-repo-foundations/spec.md`

## Summary

Create a runnable, empty three-service app (PostgreSQL + pgvector, FastAPI, React + TypeScript)
started by one Docker Compose command, plus a shared Claude Code setup: `CLAUDE.md`, a Python
`PreToolUse` hook that asks for approval on any change to `backend/app/tax/rates/`, a Python
`PostToolUse` hook that formats written files, and shared permissions. Update the README's
setup section for FastAPI. Decisions and alternatives are in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.13 (backend, hooks), TypeScript on Node 24 LTS (frontend)

**Primary Dependencies**: FastAPI, Uvicorn, SQLAlchemy 2.0 (async) + asyncpg, Alembic; React,
Vite; dev: pytest, HTTPX, Ruff, Vitest, React Testing Library, Prettier

**Storage**: PostgreSQL 17 with pgvector (extension only; no tables in 001)

**Testing**: pytest (backend), Vitest (frontend), run inside containers per the README

**Target Platform**: local development via Docker Compose on Windows, macOS and Linux

**Project Type**: web application (backend + frontend)

**Performance Goals**: fresh clone to running app in under 10 minutes (SC-001)

**Constraints**: hooks cross-platform and standard-library only; no secrets needed; ports 8000
and 5173

**Scale/Scope**: skeleton only: one endpoint, one page, two hooks, one settings file

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / rule | Status | How |
|---|---|---|
| I. Deterministic tax math | N/A | No calculations in 001 |
| II. Authoritative sources | PASS | Tax-rates path reserved and guarded from day one |
| III. Human confirmation | N/A | No extraction in 001 |
| IV. Honest output | N/A | No reports in 001 |
| V. Synthetic data only | PASS | No data of any kind |
| VI. Test-first, measured AI | PASS | Smoke tests for health and the placeholder page; test commands wired up |
| VII. MVP scope | PASS | Only README milestone 1; FR-014 excludes everything else |
| Stack | PASS | Exactly the constitution's stack. Libraries and tools inside it (uv, SQLAlchemy, Alembic, Vite, Ruff, Prettier, pytest, Vitest) are not new stack components |
| Secrets | PASS | Claude denied reading `.env`; no secrets needed |

**Post-design re-check:** PASS. The design adds no components beyond the stack and stores no
data.

## Project Structure

### Documentation (this feature)

```text
specs/001-repo-foundations/
├── plan.md              # This file
├── research.md          # Decisions R1–R7
├── data-model.md        # None for 001
├── quickstart.md        # Validation guide
├── contracts/
│   ├── health.md        # GET /health
│   └── claude-hooks.md  # Hooks and permissions
└── tasks.md             # Created by /speckit-tasks
```

### Source Code (repository root)

```text
docker-compose.yml          # db, backend, frontend
.env.example                # documented placeholders, no real values
CLAUDE.md                   # guide for Claude Code
README.md                   # setup section updated for FastAPI

.claude/
├── settings.json           # shared hooks + permissions
└── hooks/
    ├── tax_rates_guard.py  # PreToolUse: ask on tax-rates changes
    ├── format_on_write.py  # PostToolUse: Ruff / Prettier
    └── tests/              # unit tests for both hooks (run on the host)

backend/
├── Dockerfile
├── pyproject.toml          # uv-managed; Ruff + pytest config
├── alembic.ini
├── alembic/versions/0001_enable_vector.py
├── app/
│   ├── main.py             # FastAPI app, GET /health
│   └── tax/rates/          # reserved for feature 004 (guarded)
└── tests/
    └── test_health.py

frontend/
├── Dockerfile
├── package.json            # npm test → vitest run
├── vite.config.ts
└── src/
    ├── App.tsx             # placeholder page
    └── App.test.tsx
```

**Structure Decision**: web application layout (`backend/` + `frontend/`), as the README's
three-service setup implies. Hooks run on the developer's machine, not in a container, so
their unit tests live beside them in `.claude/hooks/tests/` and run on the host
(`uv run --no-project --with pytest pytest .claude/hooks/tests`); `CLAUDE.md` lists this
command.

## Complexity Tracking

No constitution violations; nothing to justify.
