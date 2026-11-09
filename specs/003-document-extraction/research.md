# Research: Document Upload + AI Extraction (003)

Each decision: what was chosen, why, and what else was considered.

## R1. Calling Gemini (replaced Claude on 2026-11-08; see plan.md "Stack change")

- **Decision:** Google's official SDK (`google-genai`), one `client.aio.models.generate_content`
  call per document. The PDF or JPG/PNG is sent as an inline part (`Part.from_bytes` with its
  media type), followed by the instructions; the system prompt is the `system_instruction`.
  Output is constrained to JSON with the schema from the Pydantic model for the document type
  (`response_mime_type="application/json"`, `response_json_schema`), and the reply text is
  validated with `model_validate_json`.
- **Model:** a setting, `EXTRACTION_MODEL`, default **`gemini-3.5-flash-lite`**, chosen by the eval
  on 2026-11-09 (R6, task T029): 280 of 280 fields correct (100% on PDFs and photos, 0% of wrong
  values marked high), about 2 s per document. `gemini-3.8-flash` was dropped: on the free tier a
  salary PDF hit Google's 60-second deadline twice (`504`), and it refuses the `minimal` thinking
  level (`400`). A synthetic set is cleaner than real documents, so real accuracy may be lower. Thinking is a setting, `EXTRACTION_EFFORT` (`minimal`, `low`,
  `medium`, `high`; default `low`): this is reading, not reasoning.
- **Blocked replies and errors:** a reply blocked for safety, cut off, empty or not matching the
  schema, or a call that errors or times out (60 s), marks the document failed with a short
  reason; it can be retried. Gemini has no server-side refusal fallback. SDK errors are told
  apart by type and status code (`ClientError` 429 = free limit reached, 401/403 = key refused;
  `ServerError` = Google's side; httpx2 timeouts and connection errors), never by matching message
  text, and never shown or logged with their details.
- **Free tier:** limits are per project and shown in AI Studio; a `429 RESOURCE_EXHAUSTED` is
  shown as "the free limit may be used up; try later". Free-tier content is used to improve
  Google's products, so only synthetic documents are uploaded (Principle V).
- **Rationale:** JSON-schema output removes parsing failures; native PDF and image input means no
  OCR step; free.
- **Earlier decision (Claude, superseded):** the Anthropic SDK with structured outputs, an effort
  setting and the server-side refusal fallback; dropped because no key was available.
- **Alternatives:** asking for JSON in the prompt only (can still produce invalid JSON); tool
  calls to get JSON (structured outputs is the direct feature for this); OCR first (rejected in
  the design).

## R2. What the model returns

- **Document type (2026-11-09, FR-005a):** the answer also says which kind of document it is
  (`salary_certificate`, `bank_profit_certificate` or `other`); a mismatch with the user's
  choice fails the extraction with a clear reason. Found in manual testing: a profit
  certificate uploaded as a salary certificate gave a review of empty fields.
- **Tax-year periods (2026-11-09):** certificates often print the period, e.g. "1 July 2025
  to 30 June 2026"; the normaliser turns July-to-June periods into the "2025-26" form.
- **"Not found" fields** show no confidence on the review page: a confidence there means
  only that the model is sure the figure is absent, which reads as noise.

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
- **Amended 2026-11-09 (lead's request, FR-018):** in the deployed app files go to a private
  Google Cloud Storage bucket (`UPLOAD_BUCKET`), as `gs://<bucket>/<user_id>/<random
  uuid>.<ext>`; without it, the disk as above. `app/documents/storage.py` saves to whichever is
  configured and reads or deletes by the stored location's form, so files from before the switch
  still work. The bucket has public access prevention enforced and uniform bucket-level access;
  the server reaches it with the VM's own Google identity (Application Default Credentials), so
  there is no key in the code or `.env`. The official `google-cloud-storage` client runs in a
  worker thread. Free tier: 5 GB in us-central1, the VM's region. Tests never reach Google: they
  use the disk, and the bucket code is tested with an in-memory fake client.
  - **Alternatives:** keeping the VM disk (files tied to one VM; the lead asked for buckets); a
    service-account key file on the VM (a long-lived secret; Google advises against it); signed
    public URLs for viewing (a link anyone holding it could open).
- **Accepted limit (code review, 2026-11-05):** the 10 MB check runs after the request body has
  arrived, so an oversized upload uses bandwidth and temporary disk before its `413`. Fine at
  demo scale; in production a reverse proxy's body-size limit stops it earlier. The upload is
  multipart, so it can't use feature 002's JSON-only rule; the session cookie's `SameSite=Lax`
  keeps other sites' form posts from carrying the session.

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
  - `backend/evals/extraction/run.py` sends every case through the app's own extractor, **one
    request at a time** (the free tier has no Batch API), pacing itself under the per-minute
    limit and stopping with a clear message if the day's limit is reached; it scores exact match
    per field after normalisation, and reports accuracy per field and per variant (PDF / photo)
    plus the share of wrong values marked `high`. Exit code non-zero if the bar (SC-003, SC-004)
    is missed. `--model` runs it for each candidate model.
- **Cost:** free; a run is 80 requests, so a low daily limit may spread it over two days.
- **Alternatives:** hand-made certificates (slow, few layouts); committing the files (large
  binaries in git).

## R7. Eval in CI, and the fork limitation

- **Decision:** a CI job `extraction-eval` runs on pushes to `main` and on manual dispatch when
  files under `backend/app/documents/extraction/` or `backend/evals/` change, using an
  `GEMINI_API_KEY` repository secret.
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
