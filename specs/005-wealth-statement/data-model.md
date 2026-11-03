# Data Model: Wealth Statement and Reconciliation (005)

Created by Alembic migration `0005_wealth`. Money is `numeric(14,0)` (whole rupees, never a
float, Principle I). Timestamps are UTC. Everything is deleted with the user.

## wealth_statements

| Column | Type | Rules |
|---|---|---|
| `id` | UUID | primary key |
| `user_id` | UUID | required; references `users.id` |
| `tax_year` | text | `2025-26` (TY2026) |
| `previous_net_assets` | numeric(14,0) | nullable (null = not entered → not ready); **may be negative** |
| `other_exempt_income` | numeric(14,0) | ≥ 0, default 0 (line 7032, user part) |
| `foreign_remittance` | numeric(14,0) | ≥ 0, default 0 (7035) |
| `inheritance` | numeric(14,0) | ≥ 0, default 0 (7036) |
| `gifts_received` | numeric(14,0) | ≥ 0, default 0 (7037) |
| `family_contribution` | numeric(14,0) | ≥ 0, default 0 (7088) |
| `gifts_given` | numeric(14,0) | ≥ 0, default 0 (7091) |
| `certificate_ids` | UUID[] | sorted ids of confirmed certificates at last save |
| `saved_at` | timestamptz | set on every save |

Unique on (`user_id`, `tax_year`). Created on first save.

## wealth_assets

| Column | Type | Rules |
|---|---|---|
| `id` | UUID | primary key |
| `statement_id` | UUID | references `wealth_statements.id`, deleted with it |
| `position` | int | display order |
| `category` | enum | `immovable_property`, `investments`, `advances_receivables`, `cash_in_hand`, `bank_account`, `equipment`, `animals`, `motor_vehicle`, `precious_possession`, `household_effects`, `personal_items`, `assets_in_others_names`, `other_asset` (research R4) |
| `description` | text | required, 1–200 characters |
| `amount` | numeric(14,0) | ≥ 0; value at cost |

## wealth_liabilities

| Column | Type | Rules |
|---|---|---|
| `id` | UUID | primary key |
| `statement_id` | UUID | references `wealth_statements.id`, deleted with it |
| `position` | int | display order |
| `description` | text | required, 1–200 characters |
| `creditor` | text | optional, up to 200 characters |
| `amount` | numeric(14,0) | ≥ 0 |

## wealth_expenses

| Column | Type | Rules |
|---|---|---|
| `statement_id` | UUID | references `wealth_statements.id`, deleted with it |
| `category` | enum | `rent`, `rates_taxes`, `vehicle`, `electricity`, `water`, `gas`, `telephone`, `asset_insurance`, `medical`, `educational`, `club`, `functions`, `donations_zakat`, `other_household`, `foreign_travel`, `local_travel` (research R3) |
| `amount` | numeric(14,0) | ≥ 0 |

Primary key (`statement_id`, `category`). A missing category means zero.

## In-code structures (never stored)

- **WealthInputs:** previous net assets; asset and liability amounts; user inflows and outflows;
  certificate sums rounded per §219 (taxable salary, gross salary, tax deducted, bank profit, tax
  withheld); TY2026 rates from 004 (`profit_limit`).
- **ReconciliationResult:** `not_ready_reason` (+ certificate for `gross_below_taxable`),
  `net_assets`, `increase`, `inflows` and `outflows` by line, `unreconciled`, `direction`
  (`reconciled`, `inflows_exceed_growth`, `growth_exceeds_inflows`), `where_to_look` (fixed
  list), `steps` (`description`, `form_line`, `result`), `summary` or null.
