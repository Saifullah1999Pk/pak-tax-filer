# Roadmap and MVP: Design

**Date:** 2026-11-02 · **Status:** Proposed · **Governed by:**
[Constitution](../../../.specify/memory/constitution.md)

## Intent

Turn the README's MVP scope and build order into numbered Spec Kit features, so each one can be
specified, planned and broken into tasks before any code is written. The scope and build order
are the README's, unchanged. The stack is the README's, with FastAPI as the backend.

## MVP

The MVP is the README's "In" list. Each item maps to the feature(s) that deliver it:

| README "In" item | Feature |
|---|---|
| One taxpayer profile, one configurable tax year (TY2026) | 002 (auth + taxpayer profile), 004 |
| Salary certificate + bank profit certificate, AI extraction, human confirmation | 003 |
| Deterministic tax calculation (salary + §151) with step-by-step explanation | 004 |
| Wealth statement with deterministic reconciliation | 005 |
| RAG assistant over the named corpus + MCP server (three tools) | 006 |
| Agentic workflow with approval gate before calculation | 007 |

**Out (for now), as in the README:** dividends, rental income, other income types; multiple
employers beyond a simple sum; IRIS login/auto-filing; any claim of authoritative tax advice;
real user documents (synthetic/demo data only until a tax practitioner and legal review are in
place).

The MVP is complete when features 001–008 are done.

## Roadmap

| # | Feature | Depends on | Done when |
|---|---|---|---|
| 001 | Repo foundations | – | `docker compose up` runs db, backend and frontend from a fresh clone; `CLAUDE.md`, the tax-rates guard hook, format-on-write and permissions are in place; the README's setup section reflects FastAPI; CI checks lint, types and tests on every PR; shared Claude Code conventions in place (issues #4, #5) |
| 002 | Authentication foundation + taxpayer profile | 001 | A demo user can log in and out; protected APIs refuse requests without a valid session; the web app has a login page and protected pages; each user sets up one profile (tax year, ATL status) before using the app |
| 003 | Upload + AI extraction | 002 | Both document types extract with per-field confidence; nothing is used until the user confirms it (enforced by the backend); an eval reports per-field accuracy on synthetic documents |
| 004 | Tax engine | 001 | Every TY2026 rate cites its FBR source; FBR-derived worked examples pass as tests; the explanation only restates computed numbers |
| 005 | Wealth statement + reconciliation | 004 | Reconciliation is computed by code and tested; the LLM only explains the result |
| 006 | RAG + MCP server | 003, 004 | Answers always cite the corpus and refuse out-of-corpus questions; a retrieval eval is measured; the three MCP tools work, with calculation done by the 004 engine |
| 007 | Agentic workflow | 003, 004, 006 | Runs end to end on synthetic documents and cannot reach calculation without human approval |
| 008 | Telemetry, guardrails, PDF export | 001–007 | CI (from 001) also enforces the eval thresholds; guardrail tests cover Principles I, III, IV; every PDF carries the "not yet practitioner-reviewed" banner |

**Milestone 2 increments:** at the lead's request, 002 starts as a minimal authentication
foundation. The README's 8 milestones are the 8 features, so milestone 2's later parts are added
to 002 rather than given new numbers: the taxpayer profile (tax year, ATL status) was added on
2026-11-04; sign-up, email verification and password reset follow the same way.

**CI** moved from 008 to 001 at the lead's request (issues #4, #5).

Features are built in this order. Technical choices are made in each feature's plan; any
addition to the stack (e.g. an embeddings source for 006) needs lead approval, per the
constitution.

## Per-feature process

Brainstorm → `/speckit-specify` → `/speckit-clarify` → `/speckit-plan` → `/speckit-tasks` →
`/speckit-analyze` → PR for review → GitHub Issues on the upstream repo, linked to the spec →
implement → PR.
