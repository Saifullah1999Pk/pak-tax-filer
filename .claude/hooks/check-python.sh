#!/usr/bin/env bash
# PostToolUse hook (Write|Edit): lint a just-written/edited .py file with pylint.
# Never blocks the edit - reports results back to Claude via additionalContext.
set -uo pipefail

input=$(cat)
file_path=$(printf '%s' "$input" | jq -r '.tool_response.filePath // .tool_input.file_path // empty')

[[ -z "$file_path" ]] && exit 0
[[ "$file_path" != *.py ]] && exit 0
[[ ! -f "$file_path" ]] && exit 0

repo_root=$(git -C "$(dirname "$file_path")" rev-parse --show-toplevel 2>/dev/null || pwd)

pylint_cmd=""
if [[ -x "$repo_root/.venv/bin/pylint" ]]; then
  pylint_cmd="$repo_root/.venv/bin/pylint"
elif [[ -x "$repo_root/venv/bin/pylint" ]]; then
  pylint_cmd="$repo_root/venv/bin/pylint"
elif command -v pylint >/dev/null 2>&1; then
  pylint_cmd="pylint"
elif python3 -c "import pylint" >/dev/null 2>&1; then
  pylint_cmd="python3 -m pylint"
fi

if [[ -z "$pylint_cmd" ]]; then
  jq -n '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: "pylint is not installed in this project yet - skipping Python lint check. Add pylint once the Django app exists."}}'
  exit 0
fi

output=$($pylint_cmd "$file_path" 2>&1)
status=$?

if [[ $status -eq 0 ]]; then
  exit 0
fi

jq -n --arg out "$output" --arg file "$file_path" \
  '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: ("pylint found issues in " + $file + ":\n" + $out)}}'
exit 0
