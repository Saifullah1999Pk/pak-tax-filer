#!/usr/bin/env bash
# PreToolUse hook (Edit|Write|MultiEdit|Bash): any change to the tax-rates module pauses for
# human approval, because rates must come from FBR's gazetted documents (constitution,
# Principle II). It asks; it never blocks (spec FR-009). Contract:
# specs/001-repo-foundations/contracts/claude-hooks.md
set -uo pipefail

input=$(cat)
file_path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')
command=$(printf '%s' "$input" | jq -r '.tool_input.command // empty')

# Compare with forward slashes so Windows paths (backslashes) match too.
file_path=${file_path//\\//}
command=${command//\\//}

guarded=false
if [[ -n "$file_path" && ( "$file_path" == */app/tax/rates/* || "$file_path" == app/tax/rates/* ) ]]; then
  guarded=true
elif [[ -n "$command" ]]; then
  # Any path to the folder, from any directory: "tax/rates" (from the repo root, backend/ or
  # backend/app/), or a rates module named from backend/app/tax/ ("rates/ty2026.py"). Feature
  # 010 once edited ty2026.py from backend/ without a prompt (review, 2026-11-16).
  if [[ "$command" == *tax/rates* || "$command" =~ rates/(ty[0-9]+|model|__init__)\.py ]]; then
    guarded=true
  fi
fi

if [[ "$guarded" == true ]]; then
  jq -n '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "ask", permissionDecisionReason: "Tax-rates module: rates must come from FBR'"'"'s gazetted documents (constitution, Principle II). Approve only if this change cites its FBR source."}}'
fi

exit 0
