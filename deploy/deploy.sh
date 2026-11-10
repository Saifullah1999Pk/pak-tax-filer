#!/usr/bin/env bash
# The only command the deploy key may run on the VM (feature 001, User Story 5; FR-024, FR-025).
# authorized_keys forces it for that key, so SSH puts what the workflow asked for in
# SSH_ORIGINAL_COMMAND: exactly "deploy <40-hex commit> <GitHub login>". The workflow's
# short-lived registry token arrives on standard input, never on a command line.
#
# It checks out that commit (so the compose file and Caddyfile match the images), logs in to
# GHCR in a throwaway Docker config, pulls both images for the commit, and starts them without
# building; migrations run as the backend starts. Design:
# docs/superpowers/specs/2026-11-10-continuous-deployment-design.md
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/awais786/pak-tax-filer.git}"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE=(docker compose -f "$APP_DIR/docker-compose.prod.yml")

refuse() {
  echo "Refused: $1" >&2
  exit 2
}

# Strict match of the whole request; anything else (a shell, another command, extra words or
# characters) is refused before git or docker run.
request="${SSH_ORIGINAL_COMMAND:-}"
if [[ ! "$request" =~ ^deploy\ ([0-9a-f]{40})\ ([A-Za-z0-9][A-Za-z0-9-]{0,38}(\[bot\])?)$ ]]; then
  refuse "expected 'deploy <40-hex commit> <GitHub login>'."
fi
sha="${BASH_REMATCH[1]}"
login="${BASH_REMATCH[2]}"

IFS= read -r token || true
if [ -z "${token:-}" ]; then
  refuse "no registry token on standard input."
fi

# The login lives only in this temporary config, removed however the script ends.
DOCKER_CONFIG="$(mktemp -d)"
export DOCKER_CONFIG
trap 'rm -rf "$DOCKER_CONFIG"' EXIT

echo "Deploying $sha"
git -C "$APP_DIR" fetch --quiet "$REPO_URL" "$sha"
git -C "$APP_DIR" checkout --quiet --detach "$sha"

printf '%s\n' "$token" | docker login ghcr.io -u "$login" --password-stdin > /dev/null
unset token

export IMAGE_TAG="$sha"
"${COMPOSE[@]}" pull --quiet backend web
"${COMPOSE[@]}" up -d --no-build --remove-orphans
# Old images (earlier commits) aren't in use any more; images of running containers are kept.
docker image prune -af > /dev/null || true
echo "Deployed $sha"
