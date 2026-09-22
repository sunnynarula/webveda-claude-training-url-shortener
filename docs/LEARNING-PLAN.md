# Project Plan: What to Do, and What to Explore at Each Step

The steps for **this** project, in the instructor's order (`ASSIGNMENT.md` §3,
plus Modules 12–14). Each step says what to **do** on the URL shortener, and
what to **explore** while doing it: a built-in command, a plugin from the
official marketplace (`/plugin`), or a skill from **skills.sh**.

The approved build plan from step 3 is [`docs/PLAN.md`](PLAN.md). It adds:
- test-first slices
- a Fable security reviewer on every slice
- production hardening
- a deploy-and-operate slice 9

Where this file and the plan differ, the plan wins.

**skills.sh** is Vercel's open directory of agent skills. You install from it
with `npx skills add <owner/repo>` (see `npx skills --help`). Read a skill's
`SKILL.md` before installing it (Module 9's warning), and install into this
project so the skill lands in the repo's history.

**How to work through it**
- Use a fresh session per step: `claude`, then `/rename step-N-<name>`.
- Use `acceptEdits` mode, set in step 1. Don't use bypass mode.
- Ship every code step through the three agents, testing → verification →
  push, which ends in a PR that you merge yourself.

---

## Phase A: before any code

### Step 0: Setup (done)
The GitHub repo is public and tagged `training`. The agents are in
`.claude/agents/`. `LICENSE-COURSE` covers the course files, and `LICENSE`
(PolyForm Strict) covers the rest.

### Step 1: Restart and see what Claude loads (done)
**Do:**
- `/exit`, then start plain `claude` in the repo root.
- Ask *"which agent types do you have?"*
- Create `.claude/settings.json` with `{"permissions": {"defaultMode": "acceptEdits"}}` and commit it.

**Explore:**
- **Command** `/context`: predict first how much space your global `CLAUDE.md` takes before you type anything, then check.
- **Command** `/memory`: see which memory files load.
- **Command** `/permissions`, and cycle modes with `Shift+Tab`.
- **Command** `/help`: skim the full list of built-in commands.

### Step 2: Draft the README skeleton (Module 12)
**Do:** write `README.md` as **headings only**: what it does, run locally,
env vars, migrations, out of scope, known limitations. The course's reason:
filling it in as you go beats reconstructing setup steps from memory.

**Explore:**
- **Command** `!` prefix: run shell commands yourself inside the session, e.g. `!ls`.

### Step 3: Plan the build (Module 7)
**Do:** in plan mode, have Claude interview you, then write the plan for the
8 slices. Save the approved plan as `docs/PLAN.md`.

**Explore:**
- **Command** `claude --permission-mode plan`, or `/plan` before a prompt.
- **Docs pattern** *"Interview me in detail using the AskUserQuestion tool … dig into the hard parts"* (from the best-practices page).
- **Shortcut** `Ctrl+G`: open the plan in your editor and edit it directly.
- **Commands** `/model` and `/effort`: try a stronger model or higher effort for planning, then switch back for building.
- **Plugin** `feature-dev`: read (don't adopt) how its exploration and architecture agents structure a plan, and compare with yours.

### Step 4: Explain-back before code (Module 12)
**Do:** ask Claude to explain, in its own words, why the SSRF check and the
atomic click counter matter. If it can't, re-read `CLAUDE.md` §6 together.

**Explore:**
- **Plugin** `learning-output-style`: at decision points, Claude asks *you* to write the meaningful piece of code. Turn it on now, for the security slices.
- **Plugin** `explanatory-output-style`: adds "why" insights to Claude's answers. Try it, and compare with the learning style.

### Step 5: Get the plan reviewed by experts (Modules 7 and 13)
**Do:**
- Write `security-reviewer` and `reliability-reviewer` agents in `.claude/agents/`, each with a persona and read-only tools.
  - The `security-reviewer` runs on Fable (`model: fable`) and gets only `Read, Grep, Glob`, so it can't change anything.
  - It skips your global `CLAUDE.md` (`omitClaudeMd`).
  - It reviews every slice later on, not just the plan (`docs/PLAN.md` §3).
- Run them **in parallel** on `docs/PLAN.md`, telling them to report only gaps that affect correctness or the requirements. Record Fable's real token use.
- *Changed by decision on 2026-09-22 (`docs/PLAN.md`, Amendments): the plan review was skipped, because four expert reviews had already covered it. Only the `security-reviewer` was created, and its first run is on slice 1.*
- Decide what to change, two rounds at most. Commit the reviewers and the plan revisions.

**Explore:**
- **Plugin** `pr-review-toolkit`: read its reviewer agents as examples of persona writing.
- **skills.sh** `obra/superpowers`, the `requesting-code-review` skill: another take on structuring a review request.
- **Docs** <https://code.claude.com/docs/en/best-practices>: have one pass check the plan against it (the Module 7 "best practices" lens).

### Step 6: TASKS.md (Module 8)
**Do:** turn `docs/PLAN.md` into a `TASKS.md` checklist that Claude ticks
off as slices finish. Give each slice a **contract** section (its interface
and acceptance list) for you to approve before RED (`docs/PLAN.md` §2).
Commit it.

**Explore:**
- **Commands** `/rename`, `/resume` and `claude --continue`: treat each slice as a named session.
- Later, mid-slice: `/clear`, then *"read TASKS.md and continue"*. Does it pick up the right place?

### Step 6b: Harness setup (`docs/PLAN.md` §7)
**Do:** each of these is its own commit:
- your licence switch to PolyForm Noncommercial
- the spec decisions and ADRs
- the testing, verification and push agents updated
- `.claude/settings.json` (acceptEdits, ask before `git push`, the verdict hook and the frozen-files hook)
- `.review/` added to `.gitignore`

Then install Compose, and push `main` for the last time before protecting it.

**Explore:**
- **Command** `/hooks`: see the two new hooks.
- **Try:** as main Claude, edit a frozen test file and watch the hook block it.

---

## Phase B: build the eight slices

### Step 7: Slice 1, skeleton, Compose, CI and test harness (ASSIGNMENT §3.1)
**Do:**
- Build slice 1 as `docs/PLAN.md` §8 describes:
  - the structure from `CLAUDE.md` §4, with its seams and error model
  - Compose running Postgres 18 and Valkey
  - `scripts/check.sh`
  - CI, and then branch protection
  - the test harness
- Work on its own branch. Review with `/diff`, run the agents **by hand**, and merge the PR with a merge commit.

**Explore:**
- **Command** `/diff`, and `!docker compose ps`.
- **Plugin** `pyright-lsp`: deferred. mypy already checks types, and it would be another long-running process on a low-spec laptop. `typescript-lsp` moves to step 14.
- **Plugin** `claude-code-setup`: let it recommend hooks, skills and MCP servers for this codebase. Compare its list with this plan.
- **Try:** call the push-agent before the other two have passed, and watch it refuse.

### Step 8: Tune CLAUDE.md now that real commands exist (Module 5)
**Do:** add the real run, test and lint commands. Cut what fails the docs'
test *"Would removing this cause Claude to make mistakes?"* Consider moving
the API contract and schema out to `docs/SPEC.md`. Make each change its own commit.

**Explore:**
- **Command** `/doctor`: proposes cuts to a committed `CLAUDE.md`.
- **Command** `/init` on a throwaway branch: see what Claude would write by itself, and diff it against the instructor's version.
- **Plugin** `claude-md-management`: audits `CLAUDE.md` quality.
- **Command** `/context` before and after: does an `@docs/SPEC.md` import save context, or is it loaded anyway?

### Step 9: Slice 2, schema and Alembic migration (ASSIGNMENT §3.2, `CLAUDE.md` §7)
**Do:** create the `urls` table and indexes via an Alembic migration. Never
hand-edit the schema.

**Explore:**
- **Plugin** `context7`: fetches current documentation for SQLAlchemy 2 async and Alembic, instead of whatever version the model remembers.
- **skills.sh** `supabase/agent-skills`, the `supabase-postgres-best-practices` skill: compare its index advice with the partial index in `CLAUDE.md` §7 and the limitation in §12.
- **Write your first skill:** `/ship-slice`. It scripts the per-slice loop in `docs/PLAN.md` §2 (contract → RED → GREEN → REFACTOR → gates → reviews → push) and stops on FAIL. Mark it manual-only (`disable-model-invocation: true`) because it pushes. For help:
  - **skills.sh** `mattpocock/skills`: `write-a-skill` / `writing-great-skills`
  - the `skill-creator` skill

  The same skills are also in the plugin marketplace as `mattpocock-skills`: one set of skills, two ways to get it.

### Step 10: Slice 3, `POST /api/v1/shorten` (ASSIGNMENT §3.3, `CLAUDE.md` §6)
**Do:** validation, the SSRF guard in `security.py`, reserved aliases, and the
idempotency rule. Ship it with `/ship-slice`.

**Explore:**
- **skills.sh** `obra/superpowers`, the `test-driven-development` skill: write the 400, 409 and 200-deduplication tests *before* the code.
- **Plugin** `learning-output-style` (from step 4): write the SSRF check yourself.
- **Command** `/security-review` on the diff.
- **Plugin** `security-guidance`, optional. Read it first: it reviews at the end of every turn and on every commit, RED commits included.
- **Try:** on a break branch, let `169.254.169.254` through. Which catches it: the Fable security-reviewer, the verification-agent, `/code-review`, `/security-review`, or the plugin?

### Step 11: Slice 4, `GET /{short_code}` (ASSIGNMENT §3.4)
**Do:** cache-aside through Redis, and the atomic click count in
`BackgroundTasks`. Prove with a concurrent test that no clicks are lost.

**Explore:**
- **MCP** (Module 10): add a **read-only** Postgres MCP server with `claude mcp add … --scope project`, and check it with `/mcp`. Check `click_count` through it, then with `!docker compose exec … psql`. Which is cheaper in `/context`?
- **Command** `!docker compose exec redis redis-cli`: watch the `url:{code}` keys appear.

### Step 12: Slice 5, stats endpoint (ASSIGNMENT §3.5)
**Do:** `GET /api/v1/urls/{short_code}`. It's a small slice, so use it to try tools cheaply.

**Explore:**
- **Command** `/simplify`: a review for reuse and simplification that applies its fixes.
- **Plugin** `code-simplifier`: compare it with `/simplify`.
- **Command** `/rewind` (or `Esc` twice): try an alternative design, then roll it back.

### Step 13: Slice 6, rate limiting, CORS, health (ASSIGNMENT §3.6, `CLAUDE.md` §9–10)
**Do:**
- **Rate limiting:** our own async limiter backed by Valkey. slowapi's Redis calls are synchronous, which `CLAUDE.md` §2 rules out.
- **CORS** limited to `FRONTEND_ORIGIN`.
- **Health:** `/api/health/live` plus a `/api/health` that really checks Postgres and Valkey.
- **Security headers** (`docs/PLAN.md` §8).

Then add the **hooks** stretch goal from `CLAUDE.md` §13, on top of the verdict and frozen-files hooks from step 6b:
- the testing-agent may only edit tests,
- the verification-agent can't change anything,
- the push-agent reruns the tests before `git push`.

**Explore:**
- **Plugin** `hookify`: create hooks from plain-language rules, and compare with writing them by hand.
- **Command** `/hooks`: browse what's configured.
- **Try:** attempt each thing a hook forbids, and watch it get blocked.

### Step 14: Slice 7, React frontend (ASSIGNMENT §3.7)
**Do:** a form that calls `/shorten` and shows the result.

**Explore:**
- **Plugin** `typescript-lsp` (moved here from step 7): install it at project scope so Claude can check types while it edits the frontend.
- **skills.sh** `vercel-labs/agent-skills`, the `vercel-react-best-practices` skill.
- **Plugin** `frontend-design`: for the visual design of the page.
- **Plugin** `playwright`, or Claude in Chrome: have Claude click through the form end to end.
- **Command** `/run`: launch and drive the app to see it working.
- **Commands** `/compact Focus on …` vs `/clear` + `TASKS.md`: this is the longest session, so compare the two.

### Step 15: Slice 8, expiry cleanup and takedown (ASSIGNMENT §3.8, `CLAUDE.md` §11)
**Do:**
- Cleanup *retires* expired codes (removes the URL and keeps the code, so it's never reused) rather than deleting them.
- A **disable** command handles abuse takedowns.
- A protected `/api/internal/cleanup` entry point handles scheduled runs.

`docs/PLAN.md` §8 has the details.

**Explore:**
- **Command** `/goal`: set a finish condition ("expired codes retired and evicted from the cache, tests pass"), and let a separate checker keep Claude working until it's met.

---

## Phase C: ship it (Module 14)

### Step 16: Extend CI (`CLAUDE.md` §13, Module 14 chapter 1)
**Do:**
- CI and branch protection already exist from slice 1. Now add the Claude GitHub App review.
- Open a PR with a failing test and confirm that `ci-ok` blocks the merge.

**Explore:**
- **Command** `/install-github-app`: add the review workflow, then mention `@claude` on a PR. If it asks for the `workflow` token scope, run `gh auth refresh -s workflow`.
- **CLI** `claude -p "…"`: headless mode, which is what the GitHub Action runs.
- **gh** `gh pr checks` and `gh run view --log-failed`: let Claude read why CI failed.

### Step 17: Deploy, which is slice 9 (Module 14 chapter 2)
**Do:** slice 9 in `docs/PLAN.md` §8.
- **First, decide:** run a demo on free tiers (non-commercial), or production at about $40–60 a month.
- **Set up:** a managed Postgres and a Redis-compatible store. Secrets go in the platform's environment variables, never committed.
- **Deploy:** migrations run over the direct database URL, then the deploy. Rollback means rolling forward only.
- **Operate:** backups with a restore drill, and a takedown runbook.

The course uses the Vercel CLI (`vercel link`, `vercel env`, `vercel deploy`, `vercel --prod`).

**Explore:**
- **skills.sh** `neondatabase/agent-skills`, the `neon-postgres` skill, if you choose Neon for the database.
- **Predict, then check:** does the click count still go up after the redirect when the backend runs serverless? `BackgroundTasks` runs *after* the response is sent.

### Step 18: Reliability (Module 14 chapter 3)
**Do:** write down an indicator (SLI) and a target (SLO) for redirects, e.g.
"99% of redirects within 200 ms, weekly". Measure it from forwarded logs plus
an external probe, and alert on how fast the error budget is being used.
Add it to the README.

---

## Phase D: wrap up

### Step 19: Package your harness as a plugin (Module 11)
**Do:** bundle the three agents, the two reviewers, `/ship-slice` and the hooks
under one `.claude-plugin/plugin.json`. Test it in a scratch folder.

**Explore:**
- **Plugin** `plugin-dev`: its skills cover the plugin, hook and agent formats.
- **CLI** `claude --plugin-dir ./plugin`, and **Command** `/reload-plugins` after edits.

### Step 20: Submit (Module 12)
**Do:**
- Fill in the README.
- Make the known-limitations section specific, e.g. "cleanup isn't scheduled in production", not "some edge cases".
- Submit the repo link.

**Explore:**
- **Plugin** `session-report`: see what the project cost in tokens and which agents and skills you actually used. Worth a line in your write-up.
