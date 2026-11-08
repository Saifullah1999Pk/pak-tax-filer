# Implementation Plan: RAG Tax Assistant and MCP Server

**Branch**: `006-rag-mcp` | **Date**: 2026-11-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/006-rag-mcp/spec.md`

## Summary

A build command downloads the named FBR documents by URL and checksum, splits them into located
passages, embeds them locally and stores them in pgvector. `POST /api/ask` retrieves the top 5
passages, asks Claude for a structured, cited answer from them only, and shows it only if code
confirms every citation was retrieved and every number appears in a cited passage; otherwise it
refuses. A retrieval eval with stable-location labels runs in CI without secrets. An MCP server
(stdio, inside the backend container) exposes exactly three tools that call existing service
functions, acting as the owner of a personal access token. Decisions are in
[research.md](research.md).

## Technical Context

**Language/Version**: Python 3.13, TypeScript on Node 24 (as in 001)

**Primary Dependencies**: FastAPI, SQLAlchemy 2 async + Alembic, `pgvector` (Python), `pypdf`
(003), `anthropic` (003), Python MCP SDK `mcp`, **`fastembed` with `BAAI/bge-small-en-v1.5`
(new, pending the lead's approval)**, `pyyaml` (004); React + React Router (002)

**Storage**: PostgreSQL 17 + pgvector: four tables ([data-model.md](data-model.md)); FBR files
in a git-ignored cache

**Testing**: pytest (fake Claude client for answers and checks; fake embedder for unit tests);
retrieval eval with thresholds; Vitest

**Target Platform**: local Docker Compose; MCP over stdio from Claude Code

**Project Type**: web application + local MCP server

**Performance Goals**: answer within 10 seconds (SC-004; 8-second Claude timeout)

**Constraints**: corpus limited to the named sources (constitution, Corpus); no source files in
the repo (licence); no figures from AI (Principle I); eval without secrets; 30 questions per
user per hour

**Scale/Scope**: 2 source documents, a few hundred passages, 4 endpoints, 3 MCP tools, 2 pages

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / rule | Status | How |
|---|---|---|
| I. Deterministic tax math | PASS | Answers can't add numbers absent from cited passages (R6); `calculate_income_tax` is 004's engine |
| II. Authoritative sources | PASS | Only FBR-hosted documents, by URL and checksum; manual cited as guidance, Ordinance as law |
| III. Human confirmation | PASS | `calculate_income_tax` uses only confirmed certificates via the same service as the Tax page |
| IV. Honest output | PASS | Explicit refusal outside the corpus; label on every answer; fixed Tax page line, no figure |
| V. Synthetic data only | PASS | No user documents involved; question text not stored |
| VI. Measured AI | PASS | Retrieval eval with thresholds in CI (R10); answer checks tested with a fake client |
| VII. MVP scope | PASS | Exactly three MCP tools; corpus exactly as named; no chat history |
| Stack | **PENDING LEAD** | `fastembed` + `bge-small-en-v1.5` is a stack addition (Claude has no embeddings API); approval requested in the PR and recorded here |
| Secrets | PASS | `ANTHROPIC_API_KEY` and `PAKTAX_TOKEN` only from the local environment; tokens stored as hashes |

**Post-design re-check:** PASS, with the stack addition pending the lead's approval.

## Project Structure

### Documentation (this feature)

```text
specs/006-rag-mcp/
├── plan.md
├── research.md        # R1–R10
├── data-model.md      # 4 tables + in-code structures
├── quickstart.md
├── contracts/
│   ├── ask-and-tokens-api.md
│   └── mcp-tools.md
└── tasks.md           # /speckit-tasks
```

### Source Code (repository root)

```text
.mcp.json                          # starts the MCP server via docker compose exec
backend/
├── alembic/versions/0006_rag_mcp.py
├── app/rag/
│   ├── sources.yaml               # URL, sha256, kind, sections/pages
│   ├── models.py                  # corpus_documents, passages, ask_requests
│   ├── build.py                   # download, verify, extract, split, embed, store
│   ├── split.py                   # structure-aware passages
│   ├── embed.py                   # fastembed wrapper; fake for tests
│   ├── search.py                  # top-5 + cut-off
│   ├── settings.py                # cut-off, ANSWER_MODEL, timeout, limit
│   ├── answer.py                  # Claude call, structured output
│   ├── checks.py                  # citation + number checks (uses app.explain)
│   ├── service.py                 # ask(): limit, search, answer, checks
│   └── router.py                  # POST /api/ask
├── app/tokens/
│   ├── models.py, service.py, router.py   # /api/tokens
├── app/mcp_server/
│   └── __main__.py                # 3 tools, token check, stdio
├── evals/retrieval/
│   ├── questions.yaml, thresholds.yaml, run.py
├── evals/answers/run.py           # local only, uses the API key
└── tests/rag/, tests/tokens/, tests/mcp/
frontend/src/pages/AskPage.tsx, TokensPage.tsx (+ tests)
.github/workflows/ci.yml           # + retrieval-eval job with caches
```

**Structure Decision**: retrieval, answering and checks are separate modules so the checks can
be tested with a fake Claude client and the eval can run with retrieval alone.

## Complexity Tracking

| Item | Why needed | Simpler alternative rejected because |
|---|---|---|
| New stack component (`fastembed` + model), pending lead approval | Claude has no embeddings API and the README requires pgvector | Voyage API: a vendor, key and cost, and no CI eval on fork PRs; keyword search: README specifies pgvector |
| Personal access tokens | MCP clients aren't browsers; `calculate_income_tax` must act as a specific user (spec FR-013) | Shared key: breaks own-data rules; no auth: anyone with shell access could read any user's data |

## AI provider (2026-11-08)

The AI model is Google's **Gemini API, free tier**, replacing Claude (the lead asked for "anything
free"; see 003's plan, "Stack change"). Where this plan names Claude or the Anthropic SDK, read
Gemini and `google-genai`; the details are settled when this feature is built.
