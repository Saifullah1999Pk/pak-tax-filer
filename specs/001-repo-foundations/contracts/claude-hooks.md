# Contract: Claude Code hooks and permissions

Shared through `.claude/settings.json`; scripts in `.claude/hooks/`. Each hook reads Claude
Code's JSON event from standard input.

## Tax-rates guard (`PreToolUse`)

- **Matches tools:** `Edit`, `Write`, `MultiEdit`, `Bash`.
- **Triggers when:** the tool's `file_path` is inside `backend/app/tax/rates/`, or a `Bash`
  `command` contains `backend/app/tax/rates` (either slash direction).
- **When triggered, outputs:**

  ```json
  {
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "ask",
      "permissionDecisionReason": "Tax-rates module: rates must come from FBR's gazetted documents (constitution, Principle II). Approve only if this change cites its FBR source."
    }
  }
  ```

- **Otherwise:** exits 0 with no output (normal permission rules apply).
- **Never** returns `deny`: it asks, it does not block (spec FR-009).
- Covers spec FR-008, FR-009, User Story 2.

## Format-on-write (`PostToolUse`)

- **Matches tools:** `Edit`, `Write`, `MultiEdit`.
- **Formats:** `.py` with Ruff; `.ts`, `.tsx`, `.js`, `.jsx`, `.css` with Prettier. Other files
  are left alone.
- **On formatter failure:** the file is kept as written; the error is reported back to Claude
  (exit code 2 with the message on standard error). The write itself is never undone.
- Covers spec FR-010.

## Permissions

| Rule | Actions |
|---|---|
| allow | pytest, Ruff, `npm test`/Vitest, Prettier, read-only git (`status`, `diff`, `log`, `show`, `branch`), `docker compose ps`/`logs` |
| ask | `git push`, `rm`, `git rm` |
| deny | reading `.env`, `.env.*` |

Anything not listed falls back to Claude Code's default of asking. Covers spec FR-011, FR-012.
