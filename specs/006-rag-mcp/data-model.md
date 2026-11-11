# Data Model: RAG Tax Assistant and MCP Server (006)

Created by Alembic migration `0006_rag_mcp` (enables the `vector` extension if not already on).
Timestamps are UTC.

## corpus_documents

| Column | Type | Rules |
|---|---|---|
| `id` | text | primary key, from `sources.yaml` (e.g. `ito-2001-2025-07-31`, `pral-itr-manual-2026`) |
| `title` | text | required |
| `kind` | enum | `law` or `guidance` |
| `url` | text | official FBR address |
| `sha256` | text | 64 hex characters; must match the downloaded file |
| `built_at` | timestamptz | when the passages were last built |

## passages

| Column | Type | Rules |
|---|---|---|
| `id` | UUID | primary key |
| `document_id` | text | references `corpus_documents.id`, deleted with it |
| `location` | text | stable, e.g. `§149(1)`, `ch. 14.3` |
| `page` | int | 1-based PDF page |
| `text` | text | 150–400 words target |
| `embedding` | vector(768) | HNSW index, cosine distance (Gemini `gemini-embedding-001` at 768 dimensions; amended 2026-11-11) |

The whole corpus is replaced in one transaction on each build.

## ask_requests

| Column | Type | Rules |
|---|---|---|
| `id` | UUID | primary key |
| `user_id` | UUID | references `users.id`, deleted with the user |
| `created_at` | timestamptz | indexed with `user_id`; rows older than 1 day deleted |

No question or answer text is stored (FR-009).

## personal_access_tokens

| Column | Type | Rules |
|---|---|---|
| `id` | UUID | primary key |
| `user_id` | UUID | references `users.id`, deleted with the user |
| `name` | text | required, 1–50 characters |
| `token_hash` | text | SHA-256 of the token; unique |
| `prefix` | text | first 8 characters, for display |
| `created_at` | timestamptz | |
| `expires_at` | timestamptz | `created_at` + 90 days |
| `revoked_at` | timestamptz | null until revoked |
| `last_used_at` | timestamptz | updated on each tool call |

A token is valid when its hash matches, `revoked_at` is null and now < `expires_at`.

## In-code structures (never stored)

- **RetrievedPassage:** passage id, document title and kind, location, page, text, score.
- **ClaudeAnswer** (structured output): `answer`, `citations` (passage ids), `not_covered`,
  `uncovered_part`, `asks_own_tax_figure`.
- **AskResult:** `status` (`answered`, `not_covered`, `limited`, `unavailable`), `answer`,
  `citations` (title, kind, location, page), `uncovered_part`, `tax_page_line`, `label`.
