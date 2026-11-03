# PakTaxFiler — Engineering Rules

General-purpose rules for working in this repo. See the detailed rule files:

- @.claude/rules/security.md
- @.claude/rules/python-django.md
- @.claude/rules/git-workflow.md
- @.claude/rules/testing-quality.md

## Summary

- Never commit or push API tokens, passwords, credentials, private keys, or
  other secrets.
- Never push directly to `main` or run a destructive Git operation
  (force-push, hard reset, history rewrite) without explicit approval.
- Never commit or push unless explicitly requested.
- Follow Python, Django, and whatever project conventions already exist in
  this repo — don't introduce a competing style.
- Prefer simple, maintainable implementations over clever ones.
- Don't overwrite existing user changes — check `git status`/`git diff`
  before touching files you didn't just create.
- Review the diff before considering any task complete.
- Run the appropriate tests and linters, and report the actual results —
  never an assumed outcome.

Project scope, MVP decisions, and the non-negotiables (deterministic tax
math, FBR-sourced rates, synthetic data only, planning-via-brainstorming)
are in `README.md` — read it before making product decisions.
