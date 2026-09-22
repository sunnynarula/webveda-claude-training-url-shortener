# Q&A

Questions asked while working through this project. Each one has its own
file in [`qna/`](qna/). New entries come from the `/qna` skill.

| # | Question | Short answer | Asked |
|---|---|---|---|
| [001](qna/001-readme-standard-and-auto-updates.md) | Is there a standard for what goes in a README, and how do we keep it updated automatically? | No Claude-specific standard; the course's Module 12 list governs. Updates can be triggered and checked automatically (agent checklist, test, hook), but Claude still writes them. | 2026-09-22 |
| [002](qna/002-what-is-a-slice.md) | What does a slice mean? | One reviewable piece of the build. The assignment defines eight; each goes through the three agents and ships as its own PR. | 2026-09-22 |
| [003](qna/003-what-is-the-verification-agent.md) | What is the verification agent? | The second of the three subagents: checks a slice against `CLAUDE.md` and a 14-item checklist and returns PASS or FAIL. "Read-only" is only an instruction until a hook enforces it. | 2026-09-22 |
| [004](qna/004-what-is-the-push-agent.md) | What is the push-agent? | The last of the three subagents: branches, commits, pushes and opens a PR once told both checks passed. Never commits to `main`, never merges. | 2026-09-22 |
