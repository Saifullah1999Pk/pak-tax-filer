# Research: Document Upload + AI Extraction (003)

Each decision: what was chosen, why, and what else was considered.

## R1. Calling Claude

- **Decision:** the official Anthropic Python SDK (`anthropic`), one Messages API call per
  document. The PDF is sent as a base64 `document` block, a JPG/PNG as an `image` block, followed
  by the instructions. Output is constrained with **structured outputs** (a JSON schema built
  from a Pydantic model per document type), so the response is always valid JSON in our shape.
- **Model:** a setting, `EXTRACTION_MODEL`, default `claude-opus-5-5`; candidates for the eval
  are `claude-opus-5-5`, `claude-sonnet-5-5` and `claude-haiku-5-5` (R6). Effort is a setting
  too, starting at `low`: this is reading, not reasoning.
- **Refusals and errors:** the request opts into the API's server-side refusal fallback; if the
  final `stop_reason` is still `refusal`, or the call errors or times out (60 s), the document
  is marked failed with a short reason and can be retried. Typed SDK exceptions are caught
  most-specific first (rate limit, server error, connection), never by matching message text.
- **Rationale:** structured outputs remove JSON-parsing failures; the SDK handles retries on
  429/5xx; native PDF and image input means no OCR step.
- **Alternatives:** asking for JSON in the prompt only (can still produce invalid JSON); tool
  calls to get JSON (structured outputs is the direct feature for this); OCR first (rejected in
  the design).

## R2. What Claude returns

- **Decision:** per field: `value` (string as printed, or null for "not found"), `confidence`
  (`high` | `medium` | `low`), `page` (1-based) and `label` (the printed label next to it). No
  names, CNICs, account numbers or addresses are requested or returned (FR-003, Principle V).
- **Normalisation in code:** amounts are parsed into `Decimal` (commas, `Rs.`/`PKR` and spaces
  removed; brackets or minus treated as negative so the rule check catches them); the tax year
  is normalised to the `2025-26` form.

## R3. Rule checks

- **Decision:** a plain function per document type, run after normalisation and again after
  every user edit; any failure sets that field to `low` with a reason string. Rules exactly as
  in spec User Story 1, scenario 5.
- **Rationale:** deterministic, unit-testable, and catches confident-but-wrong answers the model
  can't flag itself (Principle I spirit: arithmetic relations are checked by code).

## R4. Upload validation and storage

- **Decision:** validate on the server before anything else: extension and actual content type
  (magic bytes) are PDF, JPEG or PNG; size ≤ 10 MB; for PDFs, `pypdf` checks page count ≤ 5 and
  rejects encrypted files; images count as 1 page. Files are stored in a Docker volume at
  `/data/uploads/<user_id>/<random uuid>.<ext>`, never under the user's filename. Served back
  only through an owner-checked endpoint.
- **Alternatives:** storing files in PostgreSQL (bloats the database and backups); object
  storage such as S3 (a new stack component, unneeded locally).
- **Note:** FastAPI needs `python-multipart` for file uploads.

## R5. Synchronous extraction

- **Decision:** the upload request stores the file, runs extraction and returns the result
  (typically under 30 s; hard timeout 60 s). The frontend shows a progress indicator.
- **Rationale:** no job queue to build or run (out of scope); fits demo scale.
- **Alternatives:** background worker with polling (more moving parts; revisit if uploads get
  slow or numerous).

## R6. Eval set and runner

- **Decision:**
  - `backend/evals/extraction/generate.py` builds the 80 cases deterministically (fixed random
    seed) with `reportlab` (PDFs, at least 4 layouts per type with different label wording,
    table vs free text, and amount formats) and `Pillow` (photo-like versions: slight rotation,
    blur, uneven lighting, JPEG compression). Ground truth is written alongside as JSON.
    Generated files are not committed; the generator is.
  - `backend/evals/extraction/run.py` sends all cases through the same extraction code using
    the **Message Batches API** (half price; results matched by `custom_id`), scores exact match
    per field after normalisation, and reports accuracy per field and per variant (PDF / photo)
    plus the share of wrong values marked `high`. Exit code non-zero if the bar (SC-003, SC-004)
    is missed. `--model` runs it for each candidate model.
- **Cost:** roughly $1 per run on Opus 5.5 with batching; pennies on Haiku 5.5.
- **Alternatives:** hand-made certificates (slow, few layouts); committing the files (large
  binaries in git).

## R7. Eval in CI, and the fork limitation

- **Decision:** a CI job `extraction-eval` runs on pushes to `main` and on manual dispatch when
  files under `backend/app/documents/extraction/` or `backend/evals/` change, using an
  `ANTHROPIC_API_KEY` repository secret.
- **Limitation found:** GitHub does not give repository secrets to workflows triggered by pull
  requests from forks, and this project's PRs come from a fork. So the eval can't run
  automatically on those PRs. Until that changes, every PR touching extraction includes the
  output of a local eval run, the lead reviews it, and CI re-runs the eval on `main` after
  merge. If the lead gives the developer branch access in the main repository, PR runs work as
  normal. `pull_request_target` is not used: it would run untrusted PR code with secrets.
- **Rationale:** keeps the key safe while still gating changes, with the remaining gap stated
  openly.

## R8. Testing without the API

- **Decision:** the extraction code takes a client interface; unit and API tests use a fake
  that returns recorded responses, so `pytest` and normal CI need no API key or credits. Only
  the eval calls the real API.

## R9. Access for later features

- **Decision:** `confirmed_documents(user_id, tax_year)` in `backend/app/documents/service.py`
  is the only way other features read figures; it returns confirmed documents and their fields
  only (FR-009). Unconfirmed figures have no other read path apart from the owner's review
  endpoints.

## R10. Frontend

- **Decision:** two pages under `RequireAuth`: **Documents** (list, upload form with type
  choice, demo notice, retry and delete) and **Review** (the original file beside the fields:
  PDFs in an embedded viewer, images as an image; low-confidence fields highlighted with their
  reason; confirm per field and for the document).
