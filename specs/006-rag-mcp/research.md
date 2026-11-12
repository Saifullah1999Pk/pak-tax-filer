# Research: RAG Tax Assistant and MCP Server (006)

Each decision: what was chosen, why, and what else was considered. Sources and reasoning are in
the [design doc](../../docs/superpowers/specs/2026-11-03-rag-mcp-design.md).

## R1. Corpus sources and build

- **Decision:** `backend/app/rag/sources.yaml` lists each document: `id`, `title`, `kind`
  (`law` or `guidance`), official FBR `url`, `sha256`, and what to keep (Ordinance: sections
  12, 13, 149, 7B, 151; manual: chapters 4–6 and 14 by page range). A build command
  (`python -m app.rag.build`) downloads into a git-ignored cache (`backend/data/corpus-cache/`; amended 2026-11-11: inside the mounted folder, so downloads survive container restarts), stops
  if a checksum differs, extracts text with `pypdf` (already used in 003), splits, embeds and
  replaces the stored corpus in one transaction.
- **Rationale:** the manual can't be redistributed (design, "Licensing"); a checksum makes the
  corpus reproducible and catches silent FBR changes (FR-002).
- **Alternatives:** committing the PDFs (licence); fetching at question time (slow, fragile).

## R2. Splitting into passages

- **Decision:** Ordinance: one passage per sub-section (e.g. `§149(1)`), located by the
  section headings in the text; long sub-sections split at sentence boundaries with the same
  location. Manual: one passage per numbered heading (e.g. `ch. 14.3`), split the same way.
  Target 150–400 words; page from the PDF page the text came from.
- **Rationale:** citations must point somewhere exact (FR-003); legal text is naturally
  structured.
- **Alternatives:** fixed-size windows (break citations mid-clause).

## R3. Embeddings (stack addition, pending the lead's approval)

- **Decision:** `fastembed` with `BAAI/bge-small-en-v1.5` (384 dimensions, ONNX runtime, no
  PyTorch, ~130 MB model, cached in the image build). Stored in pgvector (already in the stack,
  001).
- **Rationale:** no key, no cost, text stays local, and the eval runs in CI on fork PRs without
  secrets (FR-011); small and fast enough for a corpus of a few hundred passages.
- **Alternatives:** Voyage AI API (better quality, but a vendor, key and cost, and no CI eval on
  fork PRs): the fallback if the lead prefers; sentence-transformers (pulls in PyTorch, much
  larger image).
- **Approval:** recorded in [plan.md](plan.md) once the lead answers in the PR.

## R4. Retrieval and the relevance cut-off

- **Decision:** cosine similarity over an HNSW index; return the top 5. A question is "not
  covered" when the best score is below a cut-off. The cut-off is set once from the eval (the
  value that best separates labelled from out-of-corpus questions) and stored in
  `backend/app/rag/settings.py` with the eval run that justified it.
- **Rationale:** one deterministic refusal rule that the CI eval can measure without Claude.

## R5. Answer generation

- **Decision:** official `anthropic` SDK (as in 003/004), setting `ANSWER_MODEL` (default
  `claude-opus-5-5`), effort `low`, 8-second timeout (SC-004 is 10 seconds), structured output
  with fields `answer`, `citations` (passage ids), `not_covered`, `uncovered_part`,
  `asks_own_tax_figure`. The prompt passes the retrieved passages as data and instructs: answer
  only from them, quote figures exactly as written, cite every claim, name any uncovered part.
- **Rationale:** structured output makes the checks in R6 mechanical; partial answers follow the
  clarification (spec, Session 2026-11-03).

## R6. Checks before showing an answer

- **Decision:** in code, after Claude replies: (1) every citation id is in the retrieved set;
  (2) every number in the answer appears in a cited passage's text or location, using 004's
  `app/explain/number_check.py` (moved there in 005) with the cited passages as the allowed set;
  section and clause references ("§149", "114(1)") count as numbers; number words are rejected.
  Any failure, a refusal, an API error or a timeout → the refusal or "try again later" message.
  If `asks_own_tax_figure` is true, the fixed Tax page line is appended by code.
- **Rationale:** enforces Principle I and the citation rule mechanically (FR-005, FR-007).

## R7. Question limit

- **Decision:** an `ask_requests` table records `user_id` and time for each question asked (no
  question text); before answering, count the user's rows in the past hour; at 30, refuse with
  "try again later". Old rows are deleted after a day. Same pattern as 002's `login_failures`.
- **Alternatives:** in-memory counter (lost on restart; wrong with several workers).

## R8. Personal access tokens

- **Decision:** token = `ptx_` + 32 random bytes (URL-safe); stored as SHA-256 hash (as 002
  stores session tokens) with `name`, `created_at`, `expires_at` (+90 days), `revoked_at`,
  `last_used_at`. Shown once at creation. Managed through `/api/tokens` (cookie-authenticated).
  Only the MCP server accepts tokens; the web API stays cookie-only (FR-015).
- **Rationale:** random tokens need no slow hash (unlike passwords); the prefix makes leaked
  tokens recognisable to secret scanners.

## R9. MCP server

- **Decision:** `backend/app/mcp_server/` with the Python MCP SDK (`mcp`, already in the stack),
  stdio transport, run inside the backend container. `.mcp.json` at the repo root starts it with
  `docker compose exec -T backend python -m app.mcp_server`; the token comes from the
  environment variable `PAKTAX_TOKEN` (set in the user's local, uncommitted settings). On each
  call the server checks the token and acts as its owner. Tools call service functions directly
  (002's design): `search_tax_documents` → `app.rag.search`; `calculate_income_tax` →
  004's `app.tax.service` (which uses 003's `confirmed_documents`); `validate_salary_information`
  → 003's `app/documents/extraction/rules.py`.
- **Rationale:** one implementation of each rule; no HTTP layer to secure for tokens.
- **Alternatives:** MCP server calling the HTTP API with bearer tokens (adds token auth to the
  web API); remote HTTP transport (out of scope).

## R10. Retrieval eval and CI

- **Decision:** `backend/evals/retrieval/questions.yaml`: ~30 questions with `expected`
  locations and ~10 with `expected: out_of_corpus`, written in a user's words (not copied from
  passages), some deliberately tricky. `run.py` reports hit@5 and cut-off refusal rate and exits
  non-zero below the thresholds in `thresholds.yaml` (proposed 0.80 and 0.90, set by the lead).
  A CI job builds the corpus (FBR files cached by the checksums in `sources.yaml`; the embedding
  model cached too) and runs the eval; if FBR is unreachable with no cache, the job fails.
  Answer quality with Claude is checked by a separate local script, `evals/answers/run.py`, not
  in CI.
- **Rationale:** meets Principle VI and FR-010/011 without secrets.

## Amendments 2026-11-11 (design addendum 2026-11-11 (`docs/superpowers/specs/2026-11-03-rag-mcp-design.md`))

- **R3 Embeddings:** replaced by Gemini's embedding API (`gemini-embedding-001`, 768
  dimensions, retrieval task types for passages and questions) through `google-genai`, already a
  dependency. The local model would have taken 0.3-0.5 GB on a 1 GB VM and was a new stack
  component. The corpus build embeds in batches with pauses and retries (free-tier per-minute
  limits) and is all-or-nothing.
- **R5 Answer generation:** Gemini (`google-genai`), as 003 and 004 call it, with structured
  output; a 15-second limit (SC-004 amended).
- **R7 Question limit:** plus a whole-app cap of 200 a day (FR-009b), counted and locked like
  003's `use_extraction`.
- **R8 Personal access tokens:** created and revoked by `app.cli` commands; no API or page.
- **R9 MCP server:** unchanged (stdio, the backend's own service functions); connected from both
  Gemini CLI and Claude Code, with setup for each in `docs/`.
- **R10 Retrieval eval and CI:** runs where the Gemini key is available, like the extraction
  eval; fork PRs attach a local report.
- **R6 Checks** (amended 2026-11-11, from the answers eval): a number in words passes only if a
  cited passage contains the very same phrase ("Rs. 10 million", as §12(2A) writes it); any
  other number word is still rejected. Refusing all number words refused 2 of 30 faithful
  answers that quoted the law. 004/005's summaries keep rejecting every number word. Also: a
  question mostly in non-Latin letters is refused before it is searched (spec: English only;
  Gemini embeds Urdu close to English passages), and the Tax page line is added to a
  `not_covered` reply too when `asks_own_tax_figure` is set.
