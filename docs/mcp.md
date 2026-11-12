# Connecting an AI assistant (MCP)

Feature 006 (User Story 4). The app's MCP server lets a developer's AI assistant use three
tools as one PakTaxFiler user: `search_tax_documents`, `calculate_income_tax` and
`validate_salary_information` ([contract](../specs/006-rag-mcp/contracts/mcp-tools.md)). It runs
inside the backend container over stdio, so `docker compose up -d` must be running, and the
assistant must be started from the repo root (where `docker-compose.yml` is).

Results are not yet reviewed by a tax practitioner and are not tax advice.

## 1. Create a token

```bash
docker compose exec backend python -m app.cli create-token --email demo@example.com --name "Gemini CLI"
```

The `ptx_…` value is printed **once**; only its SHA-256 is stored, and it is valid for 90 days.
Put it in your own environment, never in a file in the repo:

```bash
export PAKTAX_TOKEN=ptx_…            # bash / zsh
$env:PAKTAX_TOKEN = "ptx_…"          # PowerShell
```

Revoke it with `docker compose exec backend python -m app.cli revoke-token --prefix ptx_ab12`
(its first 8 characters). A missing, wrong, expired or revoked token makes every tool call fail
with "invalid or expired token".

## 2a. Gemini CLI

Gemini CLI reads MCP servers from `~/.gemini/settings.json` (user) or `.gemini/settings.json`
(project), under `mcpServers`. Add this to your **user** settings, so nothing is committed:

```json
{
  "mcpServers": {
    "pak-tax-filer": {
      "command": "docker",
      "args": ["compose", "exec", "-T", "-e", "PAKTAX_TOKEN", "backend", "python", "-m", "app.mcp_server"],
      "env": { "PAKTAX_TOKEN": "$PAKTAX_TOKEN" },
      "timeout": 30000
    }
  }
}
```

The `env` entry matters: Gemini CLI doesn't pass inherited variables whose names contain
`TOKEN` to MCP servers unless the server's `env` names them, and it expands `$PAKTAX_TOKEN` from
your shell. Then, from the repo root: `gemini trust` (stdio servers only connect in a trusted
folder), and `gemini mcp list` should show `pak-tax-filer - Connected`; inside a session, `/mcp`
lists its three tools. Server names can't contain underscores.

(Checked against Gemini CLI's `docs/tools/mcp-server.md` on 2026-11-11.)

## 2b. Claude Code

`.mcp.json` at the repo root already declares the server, with `PAKTAX_TOKEN` taken from your
environment. Start `claude` from the repo root with the variable set, approve the project's
`pak-tax-filer` server when asked, and check it with `/mcp` (or `claude mcp list`).

## Try it

Ask the assistant, for example: "Search the tax documents for how a company car is taxed",
"Calculate my income tax", or "Check a salary certificate: gross 1,200,000, taxable 1,500,000,
tax deducted 30,000, tax year 2025-26". `search_tax_documents` counts against the same limits as
the Ask page (30 an hour per user, 200 a day for the app).
