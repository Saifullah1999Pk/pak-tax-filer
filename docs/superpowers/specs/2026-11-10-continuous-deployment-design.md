# Design: deployment and continuous deployment (feature 001, User Story 5)

**Date:** 2026-11-10 · **Status:** draft for approval

## Intent

The lead asked for a free deployment (done on 2026-11-09: one Google Cloud e2-micro VM,
`docker-compose.prod.yml`, PR #30) and then: "implement CI/CD ... once your tests pass deploy it
also directly". CI already runs on every pull request (001, User Story 4). This adds CD: after a
change is merged into `main` and CI passes there, the live site updates itself, with no SSH and
no rebuild on the VM.

## Goals, non-goals, anti-goals

- **Goals:** deploy automatically after CI passes on `main`; deploys take minutes, not the 20+
  minutes a VM build takes; a manual run can redeploy any earlier commit (rollback); the workflow
  fails visibly if the site doesn't come back.
- **Non-goals:** staging environments, blue-green or zero-downtime deploys, more VMs, a domain.
- **Anti-goals:** anything that could deploy unreviewed code (fork pull requests, other
  branches); a key that grants a shell on the VM; secrets in the repository, images or logs.

## Approaches considered

| | Approach | Trade-off |
|---|---|---|
| **A (chosen)** | GitHub builds the images and pushes them to GitHub's container registry (GHCR); then it signs in to the VM, which pulls them and restarts | Fast deploys and no CPU strain on the e2-micro; the compose file names images as well as build contexts |
| B | GitHub signs in to the VM, which runs `git pull` and builds | Smallest change, but 20+ minute deploys that slow the live site |
| C | The VM polls the registry and updates itself | No key on GitHub, but another process on a 1 GB VM and failures invisible from GitHub |

The user picked A.

## How it works (decided)

1. **Trigger:** the "CI" workflow completes successfully for a **push to `main` in this
   repository** (`workflow_run`, checking the event, branch and repository, so CI runs for fork
   pull requests can never deploy). Also a manual run with a commit to deploy (rollback).
2. **Build:** two images, `backend` (from `backend/`) and `web` (from `frontend/` with
   `deploy/web.Dockerfile`), tagged with the commit SHA and pushed to
   `ghcr.io/awais786/pak-tax-filer-{backend,web}` using the workflow's own short-lived token.
3. **Deploy:** the workflow connects with SSH as the VM user, using a key made only for deploys.
   On the VM that key is locked by `authorized_keys` to one forced command, `deploy/deploy.sh`,
   with no shell, port forwarding or terminal. The workflow sends the commit SHA (checked to be
   40 hex characters) and passes its short-lived registry token on standard input, never on the
   command line.
4. **On the VM, `deploy.sh`:** checks out that commit (so the compose file and Caddyfile match
   the images), logs in to GHCR with the token, pulls both images for that SHA, restarts with
   `up -d --no-build` (migrations run as the backend starts), logs out, and removes old images.
5. **Check:** the workflow polls the live site (`/api/auth/me` should answer 401, the page 200)
   for up to about 3 minutes and fails the run if it doesn't.
6. **Secrets** (repository Actions secrets): `DEPLOY_SSH_KEY` (private key), `DEPLOY_HOST`
   (`user@34.55.150.199`), `DEPLOY_KNOWN_HOSTS` (the VM's host key, checked against the VM
   itself, so the workflow can't be tricked into deploying to another machine). Also
   `GEMINI_API_KEY`, which the extraction-eval workflow has been missing.
7. **Images stay private:** the VM logs in with each run's token, so the packages needn't be
   made public. Images contain no secrets either way.
8. **Manual fallback stays:** the compose file keeps its `build:` sections, so
   `docker compose -f docker-compose.prod.yml up -d --build` on the VM still works.

## Constraints

Free tier only (GitHub Actions and GHCR are free for public repositories). The key and secrets
are created by the user; Claude never sees the private key's value after generating commands for
it. Synthetic data only, as before.

## Left to the builder

Action versions, image cache settings, how many old images to keep, the exact polling loop.
Spec Kit: amend `specs/001-repo-foundations` (User Story 5, requirements, tasks); update
`docs/deployment.md`.
