# Data Model: Policy-Based Bill Approval Agent (009)

Created by Alembic migration `0009_claims`. Money is `Numeric(14,2)`, read and written as
`Decimal`; timestamps are UTC.

## claims

| Column | Type | Rules |
|---|---|---|
| `id` | UUID | primary key |
| `user_id` | UUID | the employee; foreign key to `users`, delete cascades |
| `policy` | text | `medical` or `mobile` |
| `policy_year` | text | the profile's tax year at upload, e.g. `2025-26` |
| `status` | text | `reading`, `failed`, `needs_confirmation`, `flagged`, `decided`, `withdrawn` |
| `file_path` | text | where 003's storage keeps the bill |
| `media_type` | text | `application/pdf`, `image/jpeg` or `image/png` |
| `page_count` | integer | 1–5 |
| `model` | text | the model that read it; null before reading |
| `failure_reason` | text | why reading failed; null otherwise |
| `bill_date` | date | as confirmed (medical; mobile may also have one); null if none |
| `period_start`, `period_end` | date | the billing period, as confirmed (mobile); null otherwise |
| `read_total` | numeric | the total as read; null if unreadable |
| `confirmed_total` | numeric | the total the employee confirmed; null before confirming |
| `period_key` | text | the budget period: `2025-26` (medical) or `2026-03` (mobile); set when decided or flagged |
| `approved_amount` | numeric | set when decided; Rs 0 when rejected |
| `cut_amount` | numeric | the lines cut by the policy; set when decided or flagged |
| `eligible_amount` | numeric | what the policy allows, capped at the budget left at that moment; recomputed at each decision |
| `flag_reasons` | JSON list | codes and texts, e.g. `{"code": "other_line", "text": "…"}`; empty unless flagged |
| `decided_by` | text | `policy` or `approver`; null until decided |
| `approver_id` | UUID | foreign key to `users`; set when an approver decides |
| `approver_note` | text | required with an approver's decision |
| `outcome` | text | `approved` or `rejected`; null until decided |
| `created_at`, `confirmed_at`, `decided_at` | timestamptz | `created_at` required |

Index on (`user_id`, `policy`, `period_key`, `status`) for the budget sum; on (`status`) for the
queue.

## claim_lines

| Column | Type | Rules |
|---|---|---|
| `id` | UUID | primary key |
| `claim_id` | UUID | foreign key to `claims`, delete cascades |
| `position` | integer | order on the bill |
| `description` | text | as confirmed (1–200 characters) |
| `amount` | numeric | as confirmed; more than 0 |
| `category` | text | one of the policy's categories |
| `read_description`, `read_amount`, `read_category` | text, numeric, text | as read; null for a line the employee added |
| `confidence` | text | `high`, `medium`, `low`; null for an added line |
| `result` | text | `approved`, `cut` or `flag`; null until decided or flagged |
| `rule` | text | the policy rule applied, e.g. `banned: baby_product`; null until then |

## users (changed)

| Column | Type | Rules |
|---|---|---|
| `is_approver` | boolean | default false; set only by `app.cli make-approver` / `remove-approver` |

## extraction_attempts (changed)

| Column | Type | Rules |
|---|---|---|
| `kind` | text | `document` (default, existing rows) or `bill`; per-user limits count by kind, the app-wide limit counts both |

## Status transitions

```text
reading → failed                      (couldn't read; Retry → reading)
failed → needs_confirmation           (the employee enters the lines; no read total, so
                                       confirming always flags it "unreadable")
reading → needs_confirmation          (read; the employee edits lines)
needs_confirmation → decided          (confirm; the policy settles it: outcome approved)
needs_confirmation → flagged          (confirm; a flag reason applies)
flagged → decided                     (an approver: outcome approved or rejected, with a note)
needs_confirmation | flagged | failed → withdrawn   (the employee)
```

`decided` and `withdrawn` are final. Only `decided` claims with outcome `approved` count toward
the budget. With the `reject_bill` setting, a banned line makes confirm → `decided` with outcome
`rejected` and Rs 0.

## Policy (in code, not stored)

`app/claims/policies/`: `POLICIES[policy_year][policy]` → name, categories, banned categories,
budget amount, budget period (`policy_year` | `month`), banned-items setting, changed-total share,
and the written source of each rule. 2025-26: medical (Rs 100,000 a year; categories `medicine`,
`consultation`, `lab_test`, `baby_product`, `energy_drink`, `equipment`, `other`; banned
`baby_product`, `energy_drink`, `equipment`) and mobile (Rs 3,000 a month; categories `plan`,
`data`, `device`, `other`; banned `device`). Provisional, pending the accounts department.

## Telemetry (008)

Two new `app.feature` values: `claims_reading` (`generate_content`) and `claims_explanation`;
outcomes as before. No new attribute.
