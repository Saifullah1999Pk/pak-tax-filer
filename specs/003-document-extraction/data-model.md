# Data Model: Document Upload + AI Extraction (003)

Created by Alembic migration `0004_documents`. Timestamps are UTC.

## documents

| Column | Type | Rules |
|---|---|---|
| `id` | UUID | primary key |
| `user_id` | UUID | required; references `users.id`, deleted with the user |
| `doc_type` | enum | `salary_certificate` or `bank_profit_certificate` |
| `tax_year` | text | the uploader's profile tax year at upload (`2025-26`; feature 002) |
| `file_path` | text | required; random name under `/data/uploads/<user_id>/` |
| `media_type` | text | `application/pdf`, `image/jpeg` or `image/png` |
| `page_count` | int | 1–5 |
| `status` | enum | `uploaded`, `extracting`, `needs_review`, `confirmed`, `failed` |
| `failure_reason` | text | set only when `failed` |
| `model` | text | model used for the last extraction |
| `created_at` | timestamptz | defaults to now |
| `confirmed_at` | timestamptz | set when confirmed |

**Lifecycle:** `uploaded` → `extracting` → `needs_review` → `confirmed`; `extracting` →
`failed`; `failed` → `extracting` (retry). `confirmed` is final. Deleting removes the row, its
fields and the file. Several confirmed documents per type and tax year are allowed (FR-010a).

## extracted_fields

| Column | Type | Rules |
|---|---|---|
| `id` | UUID | primary key |
| `document_id` | UUID | references `documents.id`, deleted with it |
| `name` | enum | salary: `tax_year`, `gross_salary`, `taxable_salary`, `tax_deducted`; bank: `tax_year`, `profit_amount`, `tax_withheld` |
| `amount` | numeric(14,2) | for money fields; null if not found; never a float (Principle I) |
| `text_value` | text | for `tax_year` only, normalised to `2025-26` |
| `confidence` | enum | `high`, `medium`, `low` |
| `source_page` | int | 1-based; null if not found |
| `source_label` | text | label as printed; null if not found |
| `rule_reason` | text | why a rule check lowered confidence; null otherwise |
| `user_edited` | bool | true once the user changes the value |
| `confirmed` | bool | default false |

Unique on (`document_id`, `name`). A document can be confirmed only when all its fields are
confirmed and none is still "not found" (the user enters a value or zero).

## extraction_attempts (added 2026-11-09, migration `0005_extraction_attempts`)

| Column | Type | Rules |
|---|---|---|
| `id` | bigint | primary key |
| `user_id` | UUID | required; references `users.id`, deleted with the user |
| `attempted_at` | timestamptz | defaults to now |

Indexed on (`user_id`, `attempted_at`). One row per AI call for a user's document (upload or
retry that reaches the AI), kept even if the document is later deleted, so deleting can't
reset the limit. A user with 10 rows in the last 24 hours, or an app with 100, is refused
(FR-017). Counted and written under one app-wide lock, committed before the AI call, so
requests sent together can't pass a limit and no lock is held while the AI answers.
