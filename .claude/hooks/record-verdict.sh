#!/usr/bin/env bash
# SubagentStop hook: record a gate agent's final message against the commit it
# ran on. The push-agent pushes only when all three gate agents have a PASS
# recorded for HEAD. The hook writes the file, not the model, so a verdict
# can't be claimed without the agent actually running.
set -euo pipefail

input=$(cat)
agent=$(jq -r '.agent_type // empty' <<<"$input")
case "$agent" in
  testing-agent|verification-agent|security-reviewer) ;;
  *) exit 0 ;;
esac

root="${CLAUDE_PROJECT_DIR:-$(jq -r '.cwd' <<<"$input")}"
sha=$(git -C "$root" rev-parse HEAD)
dirty=$(git -C "$root" status --porcelain --untracked-files=no | wc -l | tr -d ' ')

mkdir -p "$root/.review/verdicts"
{
  echo "agent: $agent"
  echo "commit: $sha"
  echo "uncommitted_changes: $dirty"
  echo "recorded: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "---"
  jq -r '.last_assistant_message // ""' <<<"$input"
} > "$root/.review/verdicts/${agent}@${sha}.txt"
