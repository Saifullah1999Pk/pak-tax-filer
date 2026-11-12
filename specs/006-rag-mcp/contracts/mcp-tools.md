# Contract: MCP Server

Python MCP SDK, stdio transport, inside the backend container. Exactly three tools (constitution,
Principle VII). Every call requires `PAKTAX_TOKEN` in the server's environment to be a valid
personal access token (see [data-model.md](../data-model.md)); otherwise the call returns an
error result "invalid or expired token".

## .mcp.json (repo root)

```json
{
  "mcpServers": {
    "pak-tax-filer": {
      "command": "docker",
      "args": ["compose", "exec", "-T", "-e", "PAKTAX_TOKEN", "backend", "python", "-m", "app.mcp_server"],
      "env": { "PAKTAX_TOKEN": "${PAKTAX_TOKEN}" }
    }
  }
}
```

The token value comes from the developer's own environment, never from a committed file.

## search_tax_documents

- **Input:** `query` (string, 1–1,000 characters).
- **Output:** up to 5 passages: `title`, `kind`, `location`, `page`, `text`, `score`; or an
  empty list with `not_covered: true` when below the relevance cut-off. No written answer.

## calculate_income_tax

- **Input:** none; the tax year and ATL status come from the token owner's taxpayer profile
  (feature 002). No profile → 004's `needs_atl_answer` body.
- **Output:** exactly the body of `GET /api/tax/{profile tax year}` (004's
  [tax-api contract](../../004-tax-engine/contracts/tax-api.md)) for the token's owner, built
  from their **confirmed** certificates only; the same `blocked_reason` values; always the
  practitioner label.

## validate_salary_information

- **Input:** `tax_year` (string), `gross_salary`, `taxable_salary`, `tax_deducted` (decimal
  strings).
- **Output:** `{ "ok": bool, "issues": [{ "field": "…", "reason": "…" }] }` from 003's rule
  checks, with `tax_year` compared to the token owner's profile tax year. Never a tax figure.

## Behaviour common to the tools (amended 2026-11-12, from the backend review)

- **Limits:** `search_tax_documents` counts against the same limits as Ask (30 an hour per user,
  the app's 200 a day). Past one, the call returns an error result with Ask's message ("…try
  again later" or "…reached today's limit…"); no search is made.
- **Language:** a query mostly in non-Latin letters (e.g. Urdu) returns `not_covered` without
  being counted or searched, as Ask does. The query is trimmed first.
- **No corpus yet:** search returns `not_covered` (Ask says "not ready yet").
- **No profile:** `calculate_income_tax` returns 004's `needs_atl_answer` body for the newest
  tax year the app has rates for; `validate_salary_information` compares `tax_year` with that
  same year.
- **Errors:** an invalid token, a limit or an unreachable embedding service is an MCP error
  result (`isError: true`) whose text says why; never a partial result.
