#!/usr/bin/env bash
# PreToolUse hook for Edit/Write/MultiEdit/NotebookEdit: the files that define
# the tests and the gates can't change silently. The testing-agent may edit the
# acceptance tests; any other change to these files needs the developer's
# approval. Edits made through Bash bypass this hook, so the verification-agent
# also diffs the frozen tests.
set -euo pipefail

input=$(cat)
agent=$(jq -r '.agent_type // "main"' <<<"$input")
path=$(jq -r '.tool_input.file_path // .tool_input.notebook_path // empty' <<<"$input")
[ -z "$path" ] && exit 0

root="${CLAUDE_PROJECT_DIR:-$(jq -r '.cwd' <<<"$input")}"
rel="${path#"$root"/}"

reason=""
case "$rel" in
  backend/tests/unit/*) ;;  # the implementer's own unit tests
  backend/tests/*|frontend/tests/*)
    [ "$agent" = "testing-agent" ] || reason="acceptance tests are the testing-agent's, and frozen after RED" ;;
  scripts/check.sh|scripts/red-check.py|scripts/review-diff.sh|scripts/ratchet.py|.quality-baseline.json)
    [ -e "$path" ] && reason="this file defines the gates" ;;
  .github/workflows/*)
    [ -e "$path" ] && reason="CI defines the gates" ;;
  .claude/settings.json|.claude/hooks/*|.claude/agents/*)
    [ -e "$path" ] && reason="this file enforces the workflow" ;;
esac
[ -z "$reason" ] && exit 0

jq -n --arg r "$rel: $reason. Approve only if you asked for this change." \
  '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "ask", permissionDecisionReason: $r}}'
