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
