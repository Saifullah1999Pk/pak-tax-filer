# Data Model: Agentic Workflow (007)

Created by Alembic migration `0008_workflow` (006 took 0007). All timestamps UTC.

## workflow_runs

| Column | Type | Rules |
|---|---|---|
| `id` | UUID | primary key |
| `user_id` | UUID | required; references `users.id`, deleted with the user |
| `tax_year` | text | required; the profile's tax year at start |
| `step` | enum | `document`, `validate`, `research`, `gate`, `result`, `done` |
| `step_outputs` | JSONB | outputs of steps 1–3 (below); empty until step 1 runs |
| `outputs_fingerprint` | text | fingerprint of the inputs `step_outputs` were made for |
| `approved_at` | timestamptz | null until approved; cleared on input change |
| `approved_fingerprint` | text | fingerprint at approval; cleared on input change |
| `done_at` | timestamptz | null until marked done |
| `created_at`, `updated_at` | timestamptz | required |

**Unique** on (`user_id`, `tax_year`): one active run (FR-002); starting again resets the row.

## step_outputs (JSON)

```json
{
  "document": { "message": "…", "missing": ["salary_certificate"], "fallback": false },
  "validation": { "message": "…", "issues": [{ "document_id": "…", "field": "…", "reason": "…" }], "fallback": false },
  "research": { "note": "…", "passages": [{ "id": "…", "source": "…", "location": "§149(1)", "page": 12 }], "fallback": false }
}
```

Only figures already stored by 003 appear here; no identity data (Principle V).

## Transitions

| From | Event | To |
|---|---|---|
| any | `inputs_changed` | re-run 1–3 → `gate` (or `document` if no confirmed salary certificate); approval cleared |
| — / `done` | `start` | `document` (row reset) |
| `document` | `missing_salary` | `document` |
| `document` → `validate` → `research` | `steps_ok` | next step, then `gate` |
| `gate` | `approve` | `result` (sets `approved_at`, `approved_fingerprint`) |
| `gate` | `back` | `document` |
| `result` | `mark_done` | `done` (sets `done_at`) |

`result` and `done` are only reachable while `approved_fingerprint` equals the current fingerprint.
