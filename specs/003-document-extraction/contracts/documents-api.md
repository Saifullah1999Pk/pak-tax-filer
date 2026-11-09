# Contract: Documents API

Base path `/api/documents`; all endpoints need `current_user` (feature 002). Follows
[API conventions](../../001-repo-foundations/contracts/api-conventions.md): JSON bodies (except
the upload), money as decimal strings, errors as `{"detail": "..."}`, and `404` for documents
that don't exist **or belong to someone else**.

## Document object

```json
{
  "id": "…", "doc_type": "salary_certificate", "tax_year": "2025-26",
  "status": "needs_review", "failure_reason": null, "media_type": "application/pdf", "page_count": 1,
  "created_at": "2026-11-03T10:00:00Z", "confirmed_at": null,
  "fields": [
    { "name": "gross_salary", "value": "1800000.00", "confidence": "high",
      "source_page": 1, "source_label": "Gross Salary", "rule_reason": null,
      "user_edited": false, "confirmed": false }
  ]
}
```

State-changing requests (`PATCH`, `POST` confirm/retry, `DELETE`) must send
`Content-Type: application/json`, even with an empty body `{}` (feature 002, research R3); the
upload is the one multipart request.

`value` is a decimal string for amounts, `"2025-26"` for `tax_year`, or `null` if not found.
`media_type` (`application/pdf`, `image/jpeg` or `image/png`) tells the review page whether to
show the original as a PDF or an image.

## Endpoints

| Method and path | Purpose | Success | Errors |
|---|---|---|---|
| `POST /api/documents` (multipart: `file`, `doc_type`) | Upload and extract | `201` document (`needs_review` or `failed`) | `413` over 10 MB; `415` not PDF/JPEG/PNG; `422` over 5 pages, encrypted or unreadable, or not the chosen type (FR-005a: nothing is saved); `409` "Set up your profile first." (feature 002's `require_profile`); `429` "Daily limit reached: 10 extractions per 24 hours. Try again later." (FR-017, checked after the file checks, before storing or the AI) |
| `GET /api/documents` | List own documents, newest first | `200` array (without `fields`) | |
| `GET /api/documents/{id}` | One document with fields | `200` | `404` |
| `GET /api/documents/{id}/file` | Original file for the review page | `200` with its media type | `404` |
| `PATCH /api/documents/{id}/fields/{name}` body `{"value": "…"?, "confirmed": true?}` | Edit and/or confirm a field | `200` field (rule checks re-run) | `404` (also for a field name the type doesn't have); `409` document confirmed; `422` invalid value, or confirming a field that is empty or negative |
| `POST /api/documents/{id}/confirm` | Confirm the document | `200` document | `409` with the names of unconfirmed or not-found fields; `409` if its tax year isn't the profile's (FR-008) |
| `POST /api/documents/{id}/retry` | Re-run a failed extraction | `200` document | `409` not failed; `429` daily limit reached (FR-017) |
| `DELETE /api/documents/{id}` | Delete document, fields and file | `204` | `404` |

## Internal service for later features

`confirmed_documents(user_id, tax_year) -> list[ConfirmedDocument]`: confirmed documents and
their field values only (FR-009, R9). No endpoint exposes unconfirmed figures except the owner's
review endpoints above.
