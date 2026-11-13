# Contract: Claims and Approvals API (009)

Follows `docs/api-conventions.md`: paths under `/api/`, JSON in `snake_case`, money as decimal
strings (`"4200.00"`), `{"detail": "..."}` errors, the session cookie. Every endpoint needs a
login (`401`) and a profile (`409` "Set up your profile first.", 002's `require_profile`);
state-changing JSON endpoints need `Content-Type: application/json` (`415`). A claim that
isn't the caller's to see is `404` "Claim not found." (never revealing that it exists).

## The claim object

```json
{
  "id": "…", "policy": "medical", "policy_year": "2025-26", "status": "decided",
  "bill_date": "2026-03-04", "period_start": null, "period_end": null,
  "read_total": "5000.00", "confirmed_total": "5000.00",
  "lines": [
    {"id": "…", "description": "Panadol", "amount": "4200.00", "category": "medicine",
     "read_description": "Panadol", "read_amount": "4200.00", "read_category": "medicine",
     "confidence": "high", "result": "approved", "rule": "allowed: medicine"},
    {"id": "…", "description": "Pampers", "amount": "800.00", "category": "baby_product",
     "read_description": "Pampers", "read_amount": "800.00", "read_category": "baby_product",
     "confidence": "high", "result": "cut", "rule": "banned: baby_product"}
  ],
  "decision": {
    "outcome": "approved", "decided_by": "policy",
    "approved_amount": "4200.00", "cut_amount": "800.00", "eligible_amount": "4200.00",
    "budget_left": "95800.00", "flag_reasons": [], "approver_note": null
  },
  "failure_reason": null,
  "label": "Provisional, pending the accounts department. Synthetic demo policy.",
  "created_at": "…"
}
```

`decision` is `null` until the claim is decided or flagged; for a flagged claim it has
`outcome: null`, the `eligible_amount` and the `flag_reasons` (`[{"code": "other_line", "text":
"A line is in \"other\": a person must check it."}]`). Codes: `unreadable`, `other_line`,
`no_date`, `outside_period`, `total_changed`, `several_months`.

## Endpoints

| Method and path | Purpose | Success | Errors |
|---|---|---|---|
| `POST /api/claims` (multipart: `file`, `policy`) | Upload and read a bill | `201` claim (`needs_confirmation`, or `failed` with its reason) | `413` over 10 MB; `415` not PDF/JPEG/PNG; `422` over 5 pages, encrypted, unreadable, unknown policy, or not a bill; `429` "Daily limit reached: 10 bills per 24 hours. Try again later." or the app's limit; `503` storage unavailable |
| `GET /api/claims` | The caller's claims, newest first | `200` list of claims (without lines) | — |
| `GET /api/claims/budget` | Budget left per policy for the current period | `200` `{"medical": {"budget": "100000.00", "used": "4200.00", "left": "95800.00", "period": "2025-26"}, "mobile": {…, "period": "2026-03"}, "label": "…"}` | — |
| `GET /api/claims/{id}` | One claim (owner; or an approver, if flagged and not theirs) | `200` claim | `404` |
| `GET /api/claims/{id}/file` | The bill file (same rule) | `200` the file, its media type | `404` |
| `PUT /api/claims/{id}/lines` | Replace lines, date or period, total (owner, `needs_confirmation` only) | `200` claim | `404`; `409` "This claim can't be changed now."; `422` invalid line (empty description, amount ≤ 0, unknown category), no lines, total ≤ 0 |
| `POST /api/claims/{id}/confirm` | Confirm and decide (owner, `needs_confirmation` only) | `200` claim (`decided` or `flagged`) | `404`; `409` as above |
| `POST /api/claims/{id}/retry` | Read a `failed` claim again (counts as a reading) | `200` claim | `404`; `409` "Only a claim that couldn't be read can be retried."; `429` |
| `POST /api/claims/{id}/withdraw` | Withdraw (owner; `needs_confirmation`, `flagged` or `failed`) | `200` claim (`withdrawn`) | `404`; `409` "A decided claim is final." |
| `GET /api/claims/{id}/explanation` | The agent's explanation of the decision | `200` `{"explanation": "…", "fallback": false}` (`fallback: true` when the code's template is shown) | `404`; `409` "Nothing has been decided yet." |
| `GET /api/approvals` | Approver: flagged claims, oldest first, never their own | `200` list of claims (with owner email, without lines) | `404` for a non-approver |
| `POST /api/approvals/{id}` `{"outcome": "approved", "amount": "1800.00", "note": "…"}` or `{"outcome": "rejected", "note": "…"}` | Approver decides a flagged claim | `200` claim (`decided`, `decided_by: approver`) | `404` (not an approver, own claim, not flagged); `409` "This claim was withdrawn." / "already decided"; `422` empty note, amount ≤ 0 or above the eligible amount ("The most this claim can be approved for is Rs 2,000.") |

`GET /api/auth/me` (002) gains `"is_approver": false|true`.

## CLI

`python -m app.cli make-approver --email someone@example.com` and `remove-approver --email …`;
exit 1 with "No such user." when the email is unknown.
