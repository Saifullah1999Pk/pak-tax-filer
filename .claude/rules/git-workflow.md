# Git Workflow & Branch Safety

- Never commit or push unless explicitly requested in the current task.
- Never push directly to `main`, and never force-push, hard-reset, or
  rewrite history without explicit approval for that specific action —
  approval for one such operation doesn't carry over to the next.
- Work on a feature branch for anything beyond a trivial fix; let `main`
  stay deployable.
- Review the diff (`git status` / `git diff`) before considering a task
  done — know exactly what changed and why.
- Write commit messages that explain *why*, not just *what*.
- Investigate before overwriting: if you find uncommitted or unfamiliar
  work, don't discard it — stash, commit, or ask first.
