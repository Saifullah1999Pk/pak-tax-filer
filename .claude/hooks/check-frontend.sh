#!/usr/bin/env bash
# PostToolUse hook (Write|Edit): lint a just-written/edited frontend file with the
# project's own "lint" npm script, if one exists. Never blocks the edit - reports
# results back to Claude via additionalContext.
set -uo pipefail

input=$(cat)
file_path=$(printf '%s' "$input" | jq -r '.tool_response.filePath // .tool_input.file_path // empty')

[[ -z "$file_path" ]] && exit 0
case "$file_path" in
  *.js|*.jsx|*.ts|*.tsx|*.vue) ;;
  *) exit 0 ;;
esac
[[ ! -f "$file_path" ]] && exit 0

dir=$(dirname "$file_path")
pkg_json=""
d="$dir"
while [[ "$d" != "/" && "$d" != "." ]]; do
  if [[ -f "$d/package.json" ]]; then
    pkg_json="$d/package.json"
    break
  fi
  d=$(dirname "$d")
done

if [[ -z "$pkg_json" ]]; then
  jq -n '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: "No package.json/frontend project found yet - skipping frontend lint check."}}'
  exit 0
fi

lint_script=$(jq -r '.scripts.lint // empty' "$pkg_json")
if [[ -z "$lint_script" ]]; then
  jq -n '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: "No \"lint\" script defined in package.json yet - skipping frontend lint check."}}'
  exit 0
fi

pkg_dir=$(dirname "$pkg_json")
output=$(cd "$pkg_dir" && npm run lint --silent 2>&1)
status=$?

if [[ $status -eq 0 ]]; then
  exit 0
fi

jq -n --arg out "$output" --arg file "$file_path" \
  '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: ("Frontend lint found issues (triggered by " + $file + "):\n" + $out)}}'
exit 0
