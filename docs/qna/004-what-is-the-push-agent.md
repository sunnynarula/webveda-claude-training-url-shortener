# 004. What the push-agent is

**Asked:** 2026-09-22 · **Updated:** 2026-09-22

> What is the push-agent?

## Short answer

It's the last of the course's three subagents. It turns a finished slice into
a branch, a commit, a push and a pull request, but only after it's been told
that the testing and verification agents both passed. It never commits to
`main` and never merges. Merging is your decision.

## Answer

**Where it sits.** Last in the workflow: implement → testing-agent →
verification-agent → **push-agent** → you review and merge the PR.

**What it does, in order:**

1. It checks that the caller said both agents passed. If either verdict is
   missing or was FAIL, it refuses and says why.
2. It runs `git status` and `git diff` to see what changed.
3. If you're on `main`, it creates a branch named
   `<type>/<short-description>` first.
4. It stages only the files that belong to this change. It never runs
   `git add .`.
5. It writes a conventional commit message (`feat:`, `fix:`, `test:`,
   `chore:`).
6. It commits, then runs `git push -u origin <branch>`.
7. It opens a PR with `gh pr create`, putting both verdicts in the
   description.
8. It reports the branch, the commit hash and the PR URL, then stops.

**The refusal is deliberate.** Module 12 lists running it early, "or arguing
with it when it refuses", as a pitfall: "That refusal is the whole point."
Plan step 7 has you try exactly that.

**What its gate can actually check.** It starts with a fresh context and
doesn't see your conversation, so "both passed" means whatever the handoff
message says. It doesn't re-run the tests or read the verdicts itself, so a
session that simply claims both passed will get a push. That's why
`CLAUDE.md` §8 calls the order "discipline", and why the §13 stretch goal adds
a hook that reruns the tests before `git push`.

**Which of its rules are actually enforced:**

| Rule | What enforces it today | What could enforce it |
|---|---|---|
| Push only after both checks pass | The caller's word | A hook that reruns tests before `git push` (§13, plan step 13); CI plus branch protection (plan step 16) |
| Never commit to `main` | Its prompt | Branch protection on `main` (plan step 16), depending on which settings you choose |
| Never merge | Its prompt | Nothing planned. Merging stays with you. |
| Never force-push | Its prompt | A hook that blocks `--force` (not in the plan) |
| Never push secrets | Its prompt, plus `.gitignore`: `git add` refuses ignored files such as `.env` unless forced | — |

**How it's built.** It uses the same pattern as the other two agents: a
Markdown file in `.claude/agents/` with a YAML header.

- The `description` tells the main session when *not* to use it: "Use only
  after testing-agent and verification-agent both report PASS."
- `tools: Bash, Read, Grep, Glob` means it has no Edit or Write. It never
  needs them, because every git and `gh` step runs through Bash.
- `model: inherit` means it uses the same model as your session.

At startup it loads every level of `CLAUDE.md`, including your personal
`~/.claude/CLAUDE.md`. Any rule you keep there about pushing or opening PRs
applies to it as well.

**What it needs:** an authenticated `gh` and a remote to push to. If it can't
open a PR, `ASSIGNMENT.md` says to run `gh auth login` and check that
`gh repo view` works from inside the repo.

**How to call it:** *"Use the push-agent to commit and open a PR"*, with both
verdicts in the same message. Typing `@"push-agent (agent)"` makes sure that
exact agent runs.

## Sources

- `.claude/agents/push-agent.md` (header, the refusal check, steps, "never"
  rules).
- `ASSIGNMENT.md` §4 and Troubleshooting; `CLAUDE.md` §8 and §13;
  `docs/LEARNING-PLAN.md` steps 7, 13 and 16; `.gitignore` (`.env` and
  `.env.*` ignored, except `.env.example`).
- Course repo, `modules/module-12-url-shortener-project.md` lines 52 and 72.
- <https://code.claude.com/docs/en/sub-agents> (what a subagent loads at
  startup, including `~/.claude/CLAUDE.md`; that it doesn't see the
  conversation; `@"name (agent)"`). Fetched 2026-09-22 against Claude Code
  v2.1.278.
- **Not verified:** exactly which branch-protection settings make GitHub
  reject direct pushes to `main`, and how the agent behaves when a personal
  `CLAUDE.md` rule conflicts with its job. Neither has been tried in this
  repo yet.

## Related

- [003. What the verification agent is](003-what-is-the-verification-agent.md)
- [002. What "a slice" means](002-what-is-a-slice.md)
