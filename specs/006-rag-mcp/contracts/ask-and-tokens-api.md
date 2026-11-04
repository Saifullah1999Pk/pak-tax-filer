# Contract: Ask and Tokens API

Cookie-authenticated (`current_user`, 002). Follows the
[API conventions](../../001-repo-foundations/contracts/api-conventions.md).

## POST /api/ask

Request: `{ "question": "Is my medical allowance taxable?" }` (1–1,000 characters).

Response `200` (locations and pages illustrative):

```json
{
  "status": "answered",
  "answer": "…",
  "citations": [
    { "title": "Income Tax Ordinance, 2001 (amended up to 31.07.2025)", "kind": "law", "location": "§12(2)", "page": 61 },
    { "title": "Normal Income Tax Return User Manual v1.1 (PRAL, 2026)", "kind": "guidance", "location": "ch. 6.1", "page": 11 }
  ],
  "uncovered_part": null,
  "tax_page_line": null,
  "label": "Not yet reviewed by a tax practitioner. Not tax advice."
}
```

`status` values:
- `answered`: checks passed; `uncovered_part` names any part not covered (partial answer).
- `not_covered`: `answer` is "I can only answer from [the sources], and they don't cover this.";
  no citations.
- `limited`: 30 questions in the past hour; "Please try again later."; no answer generated.
- `unavailable`: Claude error or timeout; "Please try again later."

`tax_page_line` is "To see your own calculated tax, open the Tax page." when the question asks
for the user's own tax figure, otherwise null. It is never written by Claude.

Errors: `401` not logged in; `422` empty or over-long question.

## GET /api/tokens

`[{ "id": "…", "name": "Claude Code laptop", "prefix": "ptx_a1b2", "created_at": "…",
"expires_at": "…", "revoked_at": null, "last_used_at": null }]`. Full values never returned.

## POST /api/tokens

Request `{ "name": "Claude Code laptop" }` → `201` with the list item plus `"token": "ptx_…"`,
shown once only.

## DELETE /api/tokens/{id}

Revokes immediately → `204`. Another user's token → `404`.
