# Quickstart: validating Document Upload + AI Extraction (003)

**Prerequisites:** features 001 and 002 running; a demo user; `GEMINI_API_KEY` (free, from AI Studio) in the local
`.env` (only for sections 1, 2 and 4); eval cases generated ([contracts/eval.md](contracts/eval.md)).

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -m evals.extraction.generate
```

## 1. Upload and extract (User Story 1)

1. Log in, open **Documents**: the demo notice is visible.
2. Upload a generated salary-certificate PDF as "Salary certificate": within 30 s the review page
   shows 4 fields with values, confidence, page and label.
3. Upload a generated photo of a bank certificate as "Bank profit certificate": 3 fields shown.
4. Upload an 11 MB file, a `.docx`, a 6-page PDF and an encrypted PDF: each refused with its
   reason ([documents-api.md](contracts/documents-api.md)).
5. Upload a generated case whose tax deducted exceeds gross salary: both fields shown as low
   confidence with the reason.

## 2. Review and confirm (User Story 2)

1. Try to confirm with fields unconfirmed: told which ones.
2. Edit one value, confirm every field, confirm the document: status `confirmed`; editing now
   refused.
3. Before confirming another document, call `confirmed_documents` (backend test or shell): it
   is not included; after confirming, it is.

## 3. Manage documents (User Story 3)

1. Set an invalid API key, upload: status `failed` with a reason; restore the key, **Retry**:
   `needs_review`.
2. Delete a document: gone from the list; its file is gone from `/data/uploads/`.
3. As a second demo user, request the first user's document and file by ID: `404` both.

## 4. Eval (User Story 4)

```bash
docker compose exec backend python -m evals.extraction.run --model gemini-3.8-flash
docker compose exec backend python -m evals.extraction.run --model gemini-3.5-flash-lite
```

Each prints the report and exits `0` or `1` against the bar. Record the cheapest passing model
in the PR and set `EXTRACTION_MODEL` to it.

## 5. Tests (no API key needed)

```bash
docker compose exec backend pytest
docker compose exec frontend npm test
```
