# 003. What the verification agent is

**Asked:** 2026-09-22 · **Updated:** 2026-09-22

> what is the verification agent?

## Short answer

It's the second of the course's three subagents: a reviewer that checks a
slice against `CLAUDE.md` and a 14-item checklist, then returns
`VERDICT: PASS` or `FAIL` with a list of issues. It's meant to change nothing,
but for now that is only an instruction. Its tools don't enforce it.

## Answer

**Where it sits.** It's the second check in the workflow in `CLAUDE.md` §8:
implement → testing-agent → **verification-agent** → push-agent. The tests
check that the code does what the tests say. The verification agent checks
the code against the spec, including the rules the course says rushed builds
get wrong. Module 12 describes it as an agent that "reviews the implementation
against the spec and returns a clear pass/fail verdict".

**What it checks:** 14 items in four groups.

| Group | Items | What they cover |
|---|---|---|
| Correctness | 3 | Endpoints and status codes match §6; every request and response body is a Pydantic model; the idempotency rule is implemented |
| Reliability | 4 | Click count updated in one atomic statement; click tracking runs after the redirect; Redis is checked before Postgres; the health check really tests both |
| Security | 6 | Non-http(s) schemes and private IP ranges rejected; reserved aliases blocked; rate limiting backed by Redis; CORS limited to `FRONTEND_ORIGIN`; no secrets committed; no stack traces in error responses |
| Process | 1 | The testing-agent was run for this change and passed |

**What it returns:**

```
VERDICT: PASS | FAIL
Issues:
- [severity] description (file:line if applicable)
```

It lists every issue rather than stopping at the first. On FAIL it says so
plainly and does not recommend going on to the push-agent.

**How it's built.** This is the Claude Code part. It's a Markdown file in
`.claude/agents/` with a YAML header:

- `name: verification-agent` is the agent type's name.
- `description` is what the main session reads to decide when to use it.
  Only the name and description sit in every session's context, about 73
  tokens in `/context`.
- `tools: Read, Grep, Glob, Bash` lists the tools it gets. There's no Edit and
  no Write.
- `model: inherit` means it uses the same model as your session.
- The body of the file becomes its system prompt.

Claude Code watches `.claude/agents/`, so an edit to the file takes effect
within seconds, with no restart.

When it runs, it starts with a fresh context. It gets its own prompt, the
handoff message the main session writes, every level of `CLAUDE.md` (so the
spec is already loaded) and a snapshot of `git status`. It doesn't see your
conversation. Only its report comes back to the main session.

**What it can't guarantee:**

- **"Read-only" is an instruction, not a restriction.** It has no Edit or
  Write, but Bash can change files. `CLAUDE.md` §13's stretch goal (plan step
  13) adds a hook so it "can't run mutating Bash commands".
- **Its Process check depends on the caller.** It can't see the conversation,
  so it only knows the testing-agent passed if the handoff message says so,
  unless it re-runs the checks itself.
- **Its checklist covers the whole spec, not one slice.** Tell it which slice
  it's reviewing.
- **Its verdict is a model's judgement.** The Claude Code docs warn that a
  reviewer asked to find gaps usually reports some even when the work is
  sound, and suggest limiting it to gaps that affect correctness or the
  requirements. Its prompt says "List every issue found".

**How to call it:** *"Use the verification-agent to review this against
CLAUDE.md"* (the phrasing `ASSIGNMENT.md` §4 suggests). Typing
`@"verification-agent (agent)"` makes sure that exact agent runs, rather than
leaving the choice to Claude.

**Compared with the built-in reviews:** `/code-review` looks for bugs in the
diff using a fresh subagent, and `/security-review` checks for security
problems. The verification agent checks this project's own rules. Plan step
10 compares all of them on a planted SSRF bug.

## Sources

- `.claude/agents/verification-agent.md` (header, checklist, output format).
- `CLAUDE.md` §8 (the workflow) and §13 (the hook stretch goal);
  `ASSIGNMENT.md` §4 (how to call it); `docs/LEARNING-PLAN.md` steps 10
  and 13.
- Course repo, `modules/module-12-url-shortener-project.md` line 52.
- `/context` in this session: `verification-agent`, project, 73 tokens.
- <https://code.claude.com/docs/en/sub-agents> (header fields; the body
  becomes the system prompt; what a subagent loads at startup; that it
  doesn't see the conversation; `@"name (agent)"`; changes picked up without
  a restart).
- <https://code.claude.com/docs/en/best-practices> (`/code-review`; the
  warning about reviewers over-reporting).
- All fetched 2026-09-22 against Claude Code v2.1.278.

## Related

- [002. What "a slice" means](002-what-is-a-slice.md)
- [004. What the push-agent is](004-what-is-the-push-agent.md)
- [001. What goes in a README, and how to keep it updated automatically](001-readme-standard-and-auto-updates.md)
  (option 2 there adds an item to this checklist)
