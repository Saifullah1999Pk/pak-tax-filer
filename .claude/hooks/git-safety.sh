#!/usr/bin/env bash
# PreToolUse hook (Bash): flag unsafe/destructive git operations and force a
# confirmation prompt (even in auto-accept modes) instead of silently blocking.
set -uo pipefail

input=$(cat)
command=$(printf '%s' "$input" | jq -r '.tool_input.command // empty')

[[ -z "$command" ]] && exit 0

reason=""

if echo "$command" | grep -qE 'git[[:space:]]+push[^|&;]*\b(origin[[:space:]]+)?(main|master)\b'; then
  reason="direct push to main/master"
elif echo "$command" | grep -qE 'git[[:space:]]+push[^|&;]*(--force\b|--force-with-lease|(^|[[:space:]])-f([[:space:]]|$))'; then
  reason="force push"
elif echo "$command" | grep -qE 'git[[:space:]]+reset[^|&;]*--hard'; then
  reason="git reset --hard (discards uncommitted work)"
elif echo "$command" | grep -qE 'git[[:space:]]+clean[^|&;]*-[a-zA-Z]*f'; then
  reason="git clean -f (permanently deletes untracked files)"
elif echo "$command" | grep -qE 'git[[:space:]]+branch[^|&;]*-D\b'; then
  reason="git branch -D (force branch delete)"
elif echo "$command" | grep -qE '(--no-verify|--no-gpg-sign)'; then
  reason="hook/signing bypass flag (--no-verify / --no-gpg-sign)"
elif echo "$command" | grep -qE 'git[[:space:]]+(filter-branch|push[^|&;]*--mirror)'; then
  reason="history-rewriting git operation"
fi

if [[ -n "$reason" ]]; then
  jq -n --arg reason "$reason" \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "ask", permissionDecisionReason: ("Repo policy flags this as an unsafe git operation: " + $reason + ". Confirm this is intentional and explicitly approved before proceeding.")}}'
fi

exit 0
