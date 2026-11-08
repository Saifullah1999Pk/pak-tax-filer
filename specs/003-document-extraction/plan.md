# Implementation Plan: Document Upload + AI Extraction

**Branch**: `003-document-extraction` | **Date**: 2026-11-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-document-extraction/spec.md`

## Summary

Owner-only upload of salary and bank profit certificates (PDF, JPG, PNG), validated on the
server and stored in a Docker volume. One Gemini call per document with structured output
returns each figure with confidence and source; plain-code rule checks lower confidence where
figures don't add up. A review page lets the user correct and confirm every field; only
confirmed documents are readable by later features, through one service function. A
deterministic synthetic eval set (80 files) and an eval runner (one request per case, within the free limits) measure accuracy and pick
the cheapest model that meets the bar. Decisions are in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.13, TypeScript on Node 24 (as in 001)

**Primary Dependencies**: added: `google-genai` (Gemini API, free tier; replaced `anthropic` on 2026-11-08, see Stack change below), `pypdf`, `python-multipart`
(backend); `reportlab`, `Pillow` (eval generator, dev only); existing: FastAPI, SQLAlchemy,
Alembic, React, React Router

**Storage**: PostgreSQL tables `documents`, `extracted_fields` ([data-model.md](data-model.md));
files in Docker volume `uploads` at `/data/uploads`

**Testing**: pytest with a fake extractor (no API key needed); Vitest; the eval for real
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
| I. Deterministic tax math | PASS | The AI model only extracts; rule checks and all arithmetic comparisons are plain code on `Decimal` |
| II. Authoritative sources | N/A | No rates |
| III. Human confirmation | PASS | Every field and the document must be confirmed; `confirmed_documents` is the only read path (R9) |
| IV. Honest output | PASS | Confidence and rule reasons shown; "not found" never guessed |
| V. Synthetic data only | PASS | Demo notice; only figures extracted (no identifiers); eval data generated |
| VI. Test-first, measured AI | PASS | Tests first; labelled eval with per-field accuracy and a bar (R6); CI gate on `main` (R7, see limitation) |
| VII. MVP scope | PASS | Two document types only; out-of-scope items excluded |
| Stack | PASS | Gemini API replaces the Claude API with the lead's approval (Stack change below); new items are libraries; no OCR service or object storage |
| Secrets | PASS | `GEMINI_API_KEY` from `.env` locally and a GitHub secret in CI; never logged or sent to the browser |
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
│   │   ├── client.py                   # Gemini call; fake extractor for tests
│   │   ├── normalise.py                # amounts → Decimal, tax year format
│   │   └── rules.py                    # consistency checks
│   ├── service.py                      # extract, edit, confirm, delete, confirmed_documents
│   └── router.py                       # /api/documents
├── alembic/versions/0004_documents.py
├── evals/extraction/
│   ├── generate.py                     # synthetic cases + ground truth
│   └── run.py                          # eval (one request per case) + report
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

## Stack change (2026-11-08)

The lead had no Claude API key to give and asked for "anything free" (WhatsApp, 2026-11-07),
which is the approval the constitution requires for replacing a stack component. Extraction moves
to Google's **Gemini API free tier** via the `google-genai` SDK. Design:
[2026-11-08-gemini-provider-design.md](../../docs/superpowers/specs/2026-11-08-gemini-provider-design.md);
research R1, R6 and R7 are updated; tasks T033-T040 do the switch. Free-tier content is used to
improve Google's products, acceptable only because the app handles synthetic data alone
(Principle V).
