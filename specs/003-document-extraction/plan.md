# Implementation Plan: Document Upload + AI Extraction

**Branch**: `003-document-extraction` | **Date**: 2026-11-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-document-extraction/spec.md`

## Summary

Owner-only upload of salary and bank profit certificates (PDF, JPG, PNG), validated on the
server and stored in a Docker volume. One Claude call per document with structured output
returns each figure with confidence and source; plain-code rule checks lower confidence where
figures don't add up. A review page lets the user correct and confirm every field; only
confirmed documents are readable by later features, through one service function. A
deterministic synthetic eval set (80 files) and a batch eval runner measure accuracy and pick
the cheapest model that meets the bar. Decisions are in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.13, TypeScript on Node 24 (as in 001)

**Primary Dependencies**: added: `anthropic` (Claude API), `pypdf`, `python-multipart`
(backend); `reportlab`, `Pillow` (eval generator, dev only); existing: FastAPI, SQLAlchemy,
Alembic, React, React Router

**Storage**: PostgreSQL tables `documents`, `extracted_fields` ([data-model.md](data-model.md));
files in Docker volume `uploads` at `/data/uploads`

**Testing**: pytest with a fake Claude client (no API key needed); Vitest; the eval for real
accuracy

**Target Platform**: local Docker Compose

**Project Type**: web application

**Performance Goals**: figures shown within 30 s of upload (SC-001); hard timeout 60 s

**Constraints**: money as `Decimal`/`numeric`; no personal identifiers requested or stored;
unconfirmed figures unreachable by other features; API key only from the environment

**Scale/Scope**: demo scale; 8 endpoints, 2 pages, 80-case eval

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / rule | Status | How |
|---|---|---|
| I. Deterministic tax math | PASS | Claude only extracts; rule checks and all arithmetic comparisons are plain code on `Decimal` |
| II. Authoritative sources | N/A | No rates |
| III. Human confirmation | PASS | Every field and the document must be confirmed; `confirmed_documents` is the only read path (R9) |
| IV. Honest output | PASS | Confidence and rule reasons shown; "not found" never guessed |
| V. Synthetic data only | PASS | Demo notice; only figures extracted (no identifiers); eval data generated |
| VI. Test-first, measured AI | PASS | Tests first; labelled eval with per-field accuracy and a bar (R6); CI gate on `main` (R7, see limitation) |
| VII. MVP scope | PASS | Two document types only; out-of-scope items excluded |
| Stack | PASS | Claude API is in the stack; new items are libraries; no OCR service or object storage |
| Secrets | PASS | `ANTHROPIC_API_KEY` from `.env` locally and a GitHub secret in CI; never logged or sent to the browser |
| Merge gates | PASS with noted limitation | Fork PRs can't receive secrets, so the eval runs on `main` and locally per PR until branch access is granted (R7) |

**Post-design re-check:** PASS.

## Project Structure

### Documentation (this feature)

```text
specs/003-document-extraction/
├── plan.md
├── research.md            # R1–R10
├── data-model.md          # documents, extracted_fields
├── quickstart.md
├── contracts/
│   ├── documents-api.md   # endpoints + confirmed_documents service
│   └── eval.md            # generator, runner, report, bar
└── tasks.md               # /speckit-tasks
```

### Source Code (repository root)

```text
docker-compose.yml                      # + uploads volume on backend
.github/workflows/ci.yml                # + extraction-eval job (main + manual)

backend/
├── app/documents/
│   ├── models.py                       # Document, ExtractedField
│   ├── uploads.py                      # type/size/page checks, storage
│   ├── extraction/
│   │   ├── schemas.py                  # Pydantic output schema per document type
│   │   ├── prompt.py                   # instructions (versioned with the eval)
│   │   ├── client.py                   # Claude call; fake client for tests
│   │   ├── normalise.py                # amounts → Decimal, tax year format
│   │   └── rules.py                    # consistency checks
│   ├── service.py                      # extract, edit, confirm, delete, confirmed_documents
│   └── router.py                       # /api/documents
├── alembic/versions/0004_documents.py
├── evals/extraction/
│   ├── generate.py                     # synthetic cases + ground truth
│   └── run.py                          # batch eval + report
└── tests/documents/
    ├── test_uploads.py
    ├── test_normalise_rules.py
    ├── test_extraction.py              # with fake client
    ├── test_review_confirm.py
    ├── test_access.py
    └── test_eval_scoring.py

frontend/src/
├── pages/DocumentsPage.tsx (+ .test.tsx)
└── pages/ReviewPage.tsx (+ .test.tsx)
```

**Structure Decision**: extraction lives in its own sub-package so the prompt, schema, client and
rules can change together and be measured by the eval; everything else in the app reads figures
only through `service.confirmed_documents`.

## Complexity Tracking

| Item | Why needed | Simpler alternative rejected because |
|---|---|---|
| Eval can't gate fork PRs automatically | GitHub withholds secrets from fork PR workflows | `pull_request_target` would expose the API key to untrusted code; local run + lead review + `main` run instead (R7) |
