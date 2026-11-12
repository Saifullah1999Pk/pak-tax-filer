# Implementation Plan: Agentic Workflow

**Branch**: `007-agentic-workflow` | **Date**: 2026-11-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/007-agentic-workflow/spec.md`

## Summary

A `workflow_runs` row per user and tax year holds the current step, the outputs of the three
agent steps with the input fingerprint they were made for, and the approval. A pure transition
function moves the run; the service re-runs steps 1–3 whenever the fingerprint of the user's
confirmed certificates and profile changes, and refuses the result step unless the approved
fingerprint equals the current one. Each agent is one Gemini call with function calling over
in-process functions shared with 006's MCP tools, with a code-written fallback. The result calls 004's tax
service and is never stored. Decisions are in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.13, TypeScript on Node 24 (as in 001)

**Primary Dependencies**: none added; FastAPI, SQLAlchemy 2 async + Alembic, `google-genai`
(003–006), pgvector search (006), React + React Router (002)

**Storage**: PostgreSQL 17: one table `workflow_runs` ([data-model.md](data-model.md))

**Testing**: pytest with a fake agent client (scripted tool calls and replies); Vitest

**Target Platform**: local Docker Compose (from 001)

**Project Type**: web application

**Performance Goals**: each agent step within 15 seconds (as 006's answers), with the page
showing what each step is doing; the whole run under 3 minutes excluding reading (SC-001)

**Constraints**: no tax figure from AI (Principle I); gate enforced by the backend (Principle
III); citations only from search results (Principle IV); agents have no tools that write

**Scale/Scope**: demo scale; 5 endpoints, 1 page, 3 agents

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / rule | Status | How |
|---|---|---|
| I. Deterministic tax math | PASS | Result is 004's `app.tax.service`; agent text passes number checks (R5) |
| II. Authoritative sources | PASS | Research searches only 006's corpus |
| III. Human confirmation | PASS | Only confirmed certificates are read; result refused unless approved fingerprint = current (R3); agents' tools are read-only (R4) |
| IV. Honest output | PASS | Citations checked against search results; practitioner label on the result |
| V. Synthetic data only | PASS | No new data collected; step outputs hold only figures already in 003's tables |
| VI. Test-first, measured AI | PASS | State machine, gate and checks tested first with a fake client; guardrail tests for I, III, IV. The research step uses 006's search, measured by its retrieval eval; the agents' own text gets no accuracy eval, only checks and plain fallbacks (to say in the PR) |
| VII. MVP scope | PASS | README's six steps; wealth statement, PDF and telemetry excluded (FR-016) |
| Stack | PASS | No new dependencies; Gemini through `google-genai`, as 003–006 |
| Secrets | PASS | `GEMINI_API_KEY` from the environment, as in 003–006 |
| Shared quota | PASS | A run of steps 1–3 counts as one question against 006's limits (R9) |

**Post-design re-check:** PASS.

## Project Structure

### Documentation (this feature)

```text
specs/007-agentic-workflow/
├── plan.md
├── research.md          # R1–R8
├── data-model.md        # workflow_runs + step outputs
├── quickstart.md
├── contracts/
│   └── workflow-api.md  # /api/workflow, agent tools, page
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/0008_workflow.py
├── app/workflow/
│   ├── models.py          # WorkflowRun
│   ├── fingerprint.py     # SHA-256 of confirmed certificates + profile
│   ├── state.py           # pure transitions
│   ├── tools.py           # read-only tool functions (shared with 006's MCP tools)
│   ├── agents.py          # document, validation, research agents + fallbacks
│   ├── settings.py        # step timeout (WORKFLOW_MODEL/EFFORT live in app/settings.py)
│   ├── service.py         # advance, approve, back, done, result
│   └── router.py          # /api/workflow
└── tests/workflow/
    ├── fake_client.py
    ├── test_state.py
    ├── test_fingerprint.py
    ├── test_agents.py
    ├── test_gate.py       # guardrail: Principle III
    └── test_workflow_api.py

frontend/src/pages/WorkflowPage.tsx (+ .test.tsx)
frontend/src/components/MainNav.tsx   # "Guided filing" in the Filing group
```

**Structure Decision**: state, fingerprint and agents are separate modules so the gate and the
transitions are tested without any AI, and the agents with a fake client.

## Complexity Tracking

No constitution violations; nothing to justify.

## AI provider (2026-11-08)

The AI model is Google's **Gemini API, free tier**, replacing Claude (the lead asked for "anything
free"; see 003's plan, "Stack change"). Settled on 2026-11-12 (design addendum): this plan now
names Gemini throughout; see research R4, R6 and R9.
