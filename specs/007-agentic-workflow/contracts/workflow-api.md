# Contract: Workflow API and page

Base path `/api/workflow`. All endpoints need `current_user` and 002's `require_profile`
(`401` / `409` "Set up your profile first."). Follows the
[API conventions](../../001-repo-foundations/contracts/api-conventions.md).

## Run object

```json
{ "step": "gate", "tax_year": "2025-26", "fingerprint": "…", "inputs_changed": false,
  "document": { "message": "…", "missing": [] },
  "validation": { "message": "…", "issues": [{ "document_id": "…", "certificate": "Salary certificate uploaded 05 Nov 2026", "field": "taxable_salary", "reason": "…" }] },
  "research": { "note": "…", "passages": [{ "id": "…", "source": "Income Tax Ordinance 2001", "kind": "law", "location": "§149(1)", "page": 12, "text": "…" }] },
  "gate": { "figures": { "taxable_salary": "1800000.00", "tax_deducted": "75000.00", "gross_profit": "0.00", "tax_withheld": "0.00" }, "on_atl": true },
  "approved_at": null, "done_at": null }
```

The steps are plain code (amended 2026-11-16, below): there is no `fallback` field.
`"inputs_changed": true` (added 2026-11-12) when steps 1–3 re-ran because the inputs changed after
an approval, which they cleared; the page asks for a fresh approval. Cleared on approve and start.
When the app's steps change (a new steps version, as on 2026-11-16), each saved run re-runs once on
its next request and any approval clears, but `inputs_changed` stays `false`: the inputs didn't.

## Endpoints

| Endpoint | Does | Success | Errors |
|---|---|---|---|
| `GET /api/workflow` | Current run; re-runs steps 1–3 first if inputs changed | `200` run, or `404` none started | — |
| `POST /api/workflow/start` | Start or restart; runs steps 1–3 | `200` run | — |
| `POST /api/workflow/approve` | Record approval at the gate | `200` run (`step: "result"`) | `409` not at the gate, or inputs changed since the run was shown |
| `POST /api/workflow/back` | Leave the gate | `200` run (`step: "document"`) | `409` not at the gate |
| `GET /api/workflow/result` | 004's tax result (same body as `GET /api/tax/{tax_year}`) plus `passages` | `200` | `409` "Approval needed." when not approved for the current inputs |
| `POST /api/workflow/done` | Mark done | `200` run (`step: "done"`) | `409` not at the result step |

The run's `fingerprint` is its `outputs_fingerprint` (added 2026-11-04: `approve` needs it).
`approve` sends the `fingerprint` the user saw (`{"fingerprint": "…"}`); a mismatch means the
inputs changed and returns `409`.

## Page

`/workflow` (under `RequireAuth` and `RequireProfile`), shown as "Guided filing" in the Filing
group of the navigation (computer top bar, phone Filing sheet) and linked from the home page
(amended 2026-11-12): a step indicator; while steps 1–3 run, each step's progress message in
turn ("Checking your documents…", "Checking the figures…", "Finding the law that applies…"); each step's message (links to 003's pages when something is missing); the gate with
figures, tax year, ATL status, issues, passages, **Approve** and **Go back**; the result with
004's breakdown, the passages as "Where this comes from", the practitioner label, and **Mark
done**.

## Amendments 2026-11-12 (from the review)

- `POST /approve`, `/back` and `/done` before any run was started answer `404` "No guided run
  yet.", as `GET` does.
- The gate's `figures` are stored with the step outputs, from the same read of the certificates
  as the run's `fingerprint`, and `GET /result` checks the approval and calculates from one
  read: a certificate confirmed in between can't reach an approved result.
- `GET /api/workflow` may re-run steps 1–3 when the inputs changed since they ran; it is safe to
  repeat and bounded to one re-run per change.

## Amendment 2026-11-16: no AI in the guided run

The lead: "if our code doesn't need reasoning capability then no need to add AI". Each step's
facts were always decided by code; the agents only reworded them, and made the page slow. Now:

- The steps are plain code (`app/workflow/steps.py`): the document step lists what's confirmed and
  missing, the validation step runs 003's rules, and the research step reads fixed sections of the
  Ordinance from 006's corpus (`§12(1)`, `§149(1)` for salary; `§7B(1)`, `§151(1)` for bank
  profit), with no search. The agent tools, the `fallback` field and the question limits are
  removed: nothing calls the AI, so nothing is counted against 006's limits.
- Runs saved before this change re-run once on their next request (the fingerprint includes the
  steps' version), which also clears an approval made on them.
