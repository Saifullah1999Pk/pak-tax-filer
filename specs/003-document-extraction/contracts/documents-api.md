# Contract: Documents API

Base path `/api/documents`; all endpoints need `current_user` (feature 002). Follows
[API conventions](../../001-repo-foundations/contracts/api-conventions.md): JSON bodies (except
the upload), money as decimal strings, errors as `{"detail": "..."}`, and `404` for documents
that don't exist **or belong to someone else**.

## Document object

```json
{
  "id": "…", "doc_type": "salary_certificate", "tax_year": "2025-26",
  "status": "needs_review", "failure_reason": null, "page_count": 1,
  "created_at": "2026-11-03T10:00:00Z", "confirmed_at": null,
  "fields": [
    { "name": "gross_salary", "value": "1800000.00", "confidence": "high",
      "source_page": 1, "source_label": "Gross Salary", "rule_reason": null,
      "user_edited": false, "confirmed": false }
  ]
}
```

`value` is a decimal string for amounts, `"2025-26"` for `tax_year`, or `null` if not found.

## Endpoints

| Method and path | Purpose | Success | Errors |
|---|---|---|---|
| `POST /api/documents` (multipart: `file`, `doc_type`) | Upload and extract | `201` document (`needs_review` or `failed`) | `413` over 10 MB; `415` not PDF/JPEG/PNG; `422` over 5 pages, encrypted or unreadable |
| `GET /api/documents` | List own documents, newest first | `200` array (without `fields`) | |
| `GET /api/documents/{id}` | One document with fields | `200` | `404` |
| `GET /api/documents/{id}/file` | Original file for the review page | `200` with its media type | `404` |
| `PATCH /api/documents/{id}/fields/{name}` body `{"value": "…"?, "confirmed": true?}` | Edit and/or confirm a field | `200` field (rule checks re-run) | `404`; `409` document confirmed; `422` invalid value |
| `POST /api/documents/{id}/confirm` | Confirm the document | `200` document | `409` with the names of unconfirmed or not-found fields |
| `POST /api/documents/{id}/retry` | Re-run a failed extraction | `200` document | `409` not failed |
| `DELETE /api/documents/{id}` | Delete document, fields and file | `204` | `404` |

## Internal service for later features

`confirmed_documents(user_id, tax_year) -> list[ConfirmedDocument]`: confirmed documents and
their field values only (FR-009, R9). No endpoint exposes unconfirmed figures except the owner's
review endpoints above.
