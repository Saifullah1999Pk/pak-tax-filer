# Quickstart: validating the RAG Assistant and MCP Server (006)

**Prerequisites:** features 001–005; network access to FBR for the first corpus build;
`ANTHROPIC_API_KEY` for the Ask page (not for the eval).

## 1. Build the corpus

```bash
docker compose exec backend python -m app.rag.build
```

Expected: both FBR files downloaded and checksum-verified; passages stored with locations like
`§149(1)` and `ch. 14.3`. Change one checksum in `sources.yaml` locally: the build stops with a
mismatch error. Revert.

## 2. Ask (User Stories 1 and 2)

1. Log in as the demo user, open **Ask**, ask "Is my medical allowance taxable?": a short
   answer with citations (document, location, page) and the practitioner label, within 10
   seconds (SC-004).
2. Ask "How is rental income taxed?": the not-covered message only.
3. Ask "How is my salary taxed and how is rental income taxed?": the salary part answered with
   citations; rental income named as not covered.
4. Ask "How much tax do I owe?": no figure; the fixed Tax page line.
5. `pytest -k ask_checks`: answers with a foreign citation or a wrong number are replaced by the
   refusal.
6. Ask 31 questions within an hour (or run `pytest -k ask_limit`): the 31st says "try again
   later".

## 3. Retrieval eval (User Story 3)

```bash
docker compose exec backend python -m evals.retrieval.run
```

Expected: hit@5 and refusal rate printed and at or above `thresholds.yaml`. Replace the search
with random passages locally: the run exits non-zero. Revert.

## 4. MCP tools (User Story 4; amended 2026-11-11)

1. Create a token: `docker compose exec backend python -m app.cli create-token --email
   demo@example.com` (shown once), and set `PAKTAX_TOKEN` in your shell.
2. **Claude Code:** start it in the repo; `/mcp` shows `pak-tax-filer` with exactly three tools.
   **Gemini CLI:** connect it as `docs/mcp.md` shows; its MCP list shows the same three tools.
3. In each, ask it to search for "§149": passages with citations.
4. Ask it to calculate your tax: the same figures as the Tax page, using your profile's ATL
   status.
5. Ask it to validate taxable salary 2,100,000 with gross 2,000,000: an issue is reported.
6. Revoke the token (`python -m app.cli revoke-token --prefix <its prefix>`): the next tool call
   is refused, in both clients.

## 5. All tests

```bash
docker compose exec backend pytest
docker compose exec frontend npm test
```
