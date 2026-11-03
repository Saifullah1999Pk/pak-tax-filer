---

description: "Task list for feature 001: Repo Foundations"
---

# Tasks: Repo Foundations

**Input**: Design documents from `/specs/001-repo-foundations/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: included. The spec requires passing backend and frontend tests (FR-006), and the
two hooks are tested before they are written (constitution, Principle VI).

**Organization**: grouped by user story so each can be built and checked on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the spec user story it serves (US1, US2, US3)

---

## Phase 1: Setup

**Purpose**: create the project skeletons.

- [ ] T001 Create the directory layout from plan.md: `backend/app/`, `backend/tests/`, `backend/alembic/versions/`, `frontend/src/`, `.claude/hooks/tests/`
- [ ] T002 Create `backend/pyproject.toml` with uv (Python 3.13): dependencies `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`; dev dependencies `pytest`, `httpx`, `ruff`; Ruff and pytest config in the same file; generate `backend/uv.lock`
- [ ] T003 [P] Create the React + TypeScript app in `frontend/` from the Vite template; add dev dependencies `vitest`, `@testing-library/react`, `jsdom`, `prettier`; set `"test": "vitest run"` in `frontend/package.json`; configure Vitest (jsdom) in `frontend/vite.config.ts`
- [ ] T004 [P] Create `.env.example` at the repo root with placeholder values only (`DATABASE_URL`, `ANTHROPIC_API_KEY=` left empty) and a comment that real values go in an uncommitted `.env`
- [ ] T005 [P] Add `node_modules/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/` and `dist/` to `.gitignore`

---

## Phase 2: Foundational

**Purpose**: the containers every story runs in. No story work starts before this is done.

- [ ] T006 [P] Create `backend/Dockerfile`: `python:3.13-slim`, install uv, `uv sync` from `backend/uv.lock`, run `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
- [ ] T007 [P] Create `frontend/Dockerfile`: `node:24-alpine`, `npm ci`, run `npm run dev -- --host 0.0.0.0 --port 5173`
- [ ] T008 Create `docker-compose.yml` with services `db` (`pgvector/pgvector:pg17`, healthcheck with `pg_isready`, named volume), `backend` (builds `backend/`, port `8000:8000`, `DATABASE_URL` pointing at `db`, waits for `db` healthy, mounts `./backend`), `frontend` (builds `frontend/`, port `5173:5173`, mounts `./frontend` with `node_modules` kept in the container); no service requires a `.env` file
- [ ] T009 Create `backend/app/__init__.py`, `backend/app/tax/__init__.py` and `backend/app/tax/rates/__init__.py`, with a docstring in the last one stating that this module holds TY rates sourced only from FBR's gazetted documents and is guarded (constitution, Principle II)

**Checkpoint**: `docker compose up -d` builds and starts all three containers.

---

## Phase 3: User Story 1 - Start the whole app with one command (Priority: P1) 🎯 MVP

**Goal**: one command starts db, backend and frontend; each shows it is alive.

**Independent Test**: [quickstart.md](quickstart.md), section 1.

### Tests for User Story 1 (write first, confirm they fail)

- [ ] T010 [P] [US1] Write `backend/tests/test_health.py`: `GET /health` returns `200` and exactly `{"status": "ok"}`, per [contracts/health.md](contracts/health.md)
- [ ] T011 [P] [US1] Write `frontend/src/App.test.tsx`: the placeholder page renders a heading containing "pak-tax-filer"

### Implementation for User Story 1

- [ ] T012 [US1] Create `backend/app/main.py`: FastAPI app with `GET /health` returning `{"status": "ok"}`; T010 passes
- [ ] T013 [US1] Replace the Vite starter in `frontend/src/App.tsx` with a placeholder page (heading "pak-tax-filer", one line saying the app is under construction); remove unused starter assets; T011 passes
- [ ] T014 [US1] Set up Alembic: `backend/alembic.ini` and an async `backend/alembic/env.py` that reads `DATABASE_URL` from the environment
- [ ] T015 [US1] Create `backend/alembic/versions/0001_enable_vector.py`: upgrade runs `CREATE EXTENSION IF NOT EXISTS vector`, downgrade runs `DROP EXTENSION IF EXISTS vector`
- [ ] T016 [US1] Run [quickstart.md](quickstart.md) section 1 and confirm every expected result

**Checkpoint**: User Story 1 works on its own.

---

## Phase 4: User Story 2 - AI changes to tax rates need human approval (Priority: P2)

**Goal**: any Claude change to `backend/app/tax/rates/` pauses for approval with the FBR reason.

**Independent Test**: [quickstart.md](quickstart.md), section 2.

### Tests for User Story 2 (write first, confirm they fail)

- [ ] T017 [P] [US2] Write `.claude/hooks/tests/test_tax_rates_guard.py`, feeding JSON events to the script on standard input: `Edit`, `Write` and `MultiEdit` on a file inside the folder → `permissionDecision: "ask"` with the FBR reason from [contracts/claude-hooks.md](contracts/claude-hooks.md); `Bash` commands containing `backend/app/tax/rates` with `/` or `\` → `ask`; a file or command outside the folder → exit 0, no output; the hook never outputs `deny`

### Implementation for User Story 2

- [ ] T018 [US2] Create `.claude/hooks/tax_rates_guard.py` (standard library only) implementing the `PreToolUse` contract in [contracts/claude-hooks.md](contracts/claude-hooks.md); T017 passes
- [ ] T019 [US2] Create `.claude/settings.json` and register the guard under `hooks.PreToolUse` with matcher `Edit|Write|MultiEdit|Bash` and command `uv run --no-project python "$CLAUDE_PROJECT_DIR/.claude/hooks/tax_rates_guard.py"`
- [ ] T020 [US2] Run [quickstart.md](quickstart.md) section 2 in Claude Code and confirm the prompt appears, reject leaves the file unchanged, and approve applies it

**Checkpoint**: User Story 2 works on its own.

---

## Phase 5: User Story 3 - The AI assistant follows the project's shared rules (Priority: P3)

**Goal**: shared guide, auto-formatting and permissions for every contributor.

**Independent Test**: [quickstart.md](quickstart.md), section 3.

### Tests for User Story 3 (write first, confirm they fail)

- [ ] T021 [P] [US3] Write `.claude/hooks/tests/test_format_on_write.py`: a badly formatted `.py` file is reformatted; a file with a syntax error is left unchanged and the hook exits 2 with a message on standard error; a `.md` file is left alone

### Implementation for User Story 3

- [ ] T022 [US3] Create `.claude/hooks/format_on_write.py` (standard library only) implementing the `PostToolUse` contract: `uvx ruff format` for `.py`; `npx --yes prettier --write` for `.ts`, `.tsx`, `.js`, `.jsx`, `.css`; T021 passes
- [ ] T023 [US3] Register the formatter in `.claude/settings.json` under `hooks.PostToolUse` with matcher `Edit|Write|MultiEdit` and command `uv run --no-project python "$CLAUDE_PROJECT_DIR/.claude/hooks/format_on_write.py"`
- [ ] T024 [US3] Add `permissions` to `.claude/settings.json` exactly as in the table in [contracts/claude-hooks.md](contracts/claude-hooks.md): allow tests, linters, formatters, read-only git and `docker compose ps`/`logs`; ask for `git push`, `rm`, `git rm`; deny reading `.env` and `.env.*`
- [ ] T025 [P] [US3] Write `CLAUDE.md` (about one page): the constitution's seven principles in one line each with a link to `.specify/memory/constitution.md`; the repo layout; commands to start the app, run migrations, run backend, frontend and hook tests, and format; a note that `backend/app/tax/rates/` is guarded
- [ ] T026 [US3] Run [quickstart.md](quickstart.md) section 3 in Claude Code and confirm each expected result

**Checkpoint**: all three user stories work independently.

---

## Phase 6: Polish

- [ ] T027 Update the "Development setup" section of `README.md`: prerequisites Docker + Docker Compose, `uv`, Node 24+; replace `python manage.py migrate` with `alembic upgrade head`; add the hook test command; leave the rest of the README unchanged
- [ ] T028 [P] Run `ruff check` and `ruff format --check` in `backend/` and `.claude/hooks/`, and `prettier --check` in `frontend/`; fix anything reported
- [ ] T029 Run the whole of [quickstart.md](quickstart.md) from a fresh clone, including section 4 on a second operating system if one is available; record the result in the PR description

---

## Dependencies & Execution Order

- **Setup (T001–T005)** → **Foundational (T006–T009)** → user stories.
- **US1** depends only on Foundational.
- **US2 and US3** need only T001 and T009 (the reserved folder), so they can run alongside US1.
- **`.claude/settings.json`** is edited by T019, T023 and T024, so those run in that order.
- **Polish** comes after all stories.
- Within each story: tests → implementation → quickstart check.

## Parallel Opportunities

- Setup: T003, T004, T005 together after T001/T002.
- Foundational: T006 and T007 together.
- US1: T010 and T011 together.
- Across stories: T017 (US2) and T021, T025 (US3) can be written while US1 is in progress.

## Implementation Strategy

1. **MVP = User Story 1**: Setup → Foundational → US1, then stop and validate with quickstart
   section 1. The app runs.
2. **Add US2**: the tax-rates guard, before feature 004 ever adds rates.
3. **Add US3**: formatting, permissions and `CLAUDE.md`.
4. **Polish**, then one PR for the implementation.

GitHub issues for these tasks are titled `[001] T0NN: <description>` so they can't clash with
other features' task numbers.
