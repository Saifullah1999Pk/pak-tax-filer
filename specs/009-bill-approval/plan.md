# Implementation Plan: Policy-Based Bill Approval Agent

**Branch**: `009-bill-approval` | **Date**: 2026-11-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/009-bill-approval/spec.md`; design
`docs/superpowers/specs/2026-11-13-bill-approval-agent-design.md`; constitution v1.3.0.

## Summary

A new `claims` area. An employee uploads a bill under a policy (medical, or mobile/internet);
Gemini reads its date or billing period, lines, amounts and total and proposes a category per
line (003's extraction patterns: JSON schema, retries, the busy/refund path from #43). The
employee confirms, corrects, adds or removes lines; a pure `decide()` engine applies the
year-keyed policy (cut banned lines, cap at the budget left, flag what it can't settle); the AI
explains the decision in a separate request, shown only if 004's number check passes. Approvers
(a flag set by the CLI) decide flagged claims in a queue, never their own. Budget is a ledger of
decided claims, recomputed under a per-employee lock at every decision.

## Technical Context

**Language/Version**: Python 3.13, TypeScript on Node 26 (as 001–008)

**Primary Dependencies**: none added: FastAPI, async SQLAlchemy, Alembic, `google-genai`,
pypdf, React; 003's storage and upload checks; 004's number check; 008's telemetry.

**Storage**: PostgreSQL, migration `0009_claims`: `claims`, `claim_lines`; `users.is_approver`;
`extraction_attempts.kind` (`document` | `bill`). Bill files in 003's storage (bucket or disk).

**Testing**: pytest (fake bill reader and explainer, as `no_real_ai` does for 003–007), signed-off
worked examples (`tests/claims/worked_examples.yaml`), an eval on synthetic bills, Vitest +
Testing Library, Playwright (fake Gemini answers bills; two approvers).

**Target Platform**: local Docker Compose and the GCP VM (unchanged).

**Project Type**: web application

**Performance Goals**: a decision within a second of confirming (code only); reading a bill as
fast as 003's extraction (bounded by Gemini).

**Constraints**: the AI never decides (Principle I; import rules extended); confirmation enforced
server-side (III); no self-approval; synthetic data only; no patient data (V).

**Scale/Scope**: 2 policies, 2 tables, about 11 endpoints, 3 pages, 1 CLI command, 1 eval.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / rule | Status | How |
|---|---|---|
| I. Deterministic math | PASS | `app/claims/engine.py` decides every amount with `Decimal`; `.importlinter` forbids the AI modules in the engine and policies (R3) |
| II. Authoritative sources | PASS | Each policy rule records its written source, synthetic and saying so; policies change only by reviewed PR (R2) |
| III. Human confirmation | PASS | Nothing decided before the employee confirms every line (server-enforced); flagged claims only by an approver, never their own (R5, R7) |
| IV. Honest output | PASS | Every decision labelled "provisional, pending the accounts department"; explanation only if number-checked (R8) |
| V. Synthetic data only | PASS | Synthetic bills in tests, eval and e2e; no patient, CNIC or account fields |
| VI. Test-first, measured AI | PASS | Worked examples signed off before the engine; reading measured by an eval (R9) |
| VII. Scope (v1.3.0) | PASS | Exactly the second capability the amendment adds; no payments, chains or policy editing |
| Stack | PASS | No new component or library |
| Secrets | PASS | None new |

**Post-design re-check:** PASS.

## Project Structure

### Documentation (this feature)

```text
specs/009-bill-approval/
├── plan.md
├── research.md          # R1–R11
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── claims-api.md
│   └── api.yaml         # checked by scripts/validate_contracts.py
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/0009_claims.py
├── app/claims/
│   ├── models.py          # Claim, ClaimLine
│   ├── policies/          # __init__.py (POLICIES by year), y2025_26.py (medical, mobile)
│   ├── engine.py          # decide(): pure, no I/O, no AI
│   ├── reading.py         # GeminiBillReader + FakeBillReader (schema, retries)
│   ├── explain.py         # explanation writer, number check, template fallback
│   ├── service.py         # submit, confirm, decide (locked), withdraw, approvals, budget
│   └── router.py          # /api/claims…, /api/approvals…
├── app/cli.py             # + make-approver / remove-approver
├── app/auth/…             # /api/auth/me gains is_approver
├── evals/claims/          # synthetic bills, generate + run (as evals/extraction)
└── tests/claims/          # engine (worked examples, sign-off), API, access, limits, reading,
                           # explanation, guardrails additions
frontend/src/
├── api/claims.ts
├── pages/ClaimsPage.tsx, ClaimPage.tsx, ApprovalsPage.tsx (+ tests)
└── navigation.ts           # Claims; Approvals for approvers only
e2e/fake_gemini/server.py   # + bill answers;  e2e/tests/claims.spec.ts (+ approver setup)
.importlinter               # + app.claims.engine, app.claims.policies as sources
```

**Structure Decision**: its own area (design approach A), so the tax features are untouched; it
reuses 003's storage, upload checks and attempts table, 004's number check and 008's telemetry
rather than copying them.

## Complexity Tracking

No constitution violations. The one new idea for this app, a second role seeing others' data, is
limited to the flagged-claims queue and tested as an access matrix (R7).
