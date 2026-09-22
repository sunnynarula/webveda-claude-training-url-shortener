# 001. What goes in a README, and how to keep it updated automatically

**Asked:** 2026-09-22 · **Updated:** 2026-09-22

> Is there a standard for what goes in the Readme? Like a claude best practice or something? Also how do we update the readme automatically as we build the project

## Short answer

There is no Claude-specific README standard. Claude's docs only separate the
README (for people) from `CLAUDE.md` (for Claude). For this project, the
course's Module 12 list is the standard that counts. Claude still has to write
each update, but the two parts that usually fail can be automated: noticing
that an update is due, and checking that it happened.

## Answer

### Part 1: Is there a standard?

**No official one.** Two conventions are widely used:

- **GitHub's docs** say a README typically covers what the project does, why
  it's useful, how to get started, where to get help, and who maintains it.
- **Standard Readme** is a written spec aimed at open-source libraries. Its
  required sections are Title, Short Description, Table of Contents (optional
  under 100 lines), Install, Usage, Contributing and License.

**Claude's guidance is about who reads which file, not about which sections
to include.** Claude Code's best-practices page has no README guidance at all.
Its advice is about `CLAUDE.md`. The AGENTS.md convention (a shared file of
instructions for coding agents, the multi-tool counterpart of `CLAUDE.md`)
states the split directly: *"README.md files are for humans: quick starts,
project descriptions, and contribution guidelines."* Build steps, tests and
conventions meant for agents go in the agent file instead.

The two files do overlap. The best-practices list of what belongs in
`CLAUDE.md` includes "Bash commands Claude can't guess" and "required env
vars", and those are also the README's setup facts. Claude Code's memory docs
show one way to share them: a `CLAUDE.md` line `See @README for project
overview`. An import like that loads the whole README into every session at
launch. Step 8 of the learning plan is where you decide whether `CLAUDE.md`
repeats the facts or imports the README.

**For this project, the course's list is the standard**, because the
submission is judged against it. Module 12 asks for three things: what the
service does, how to run it locally (the `docker compose` commands,
environment variables, migrations), and what's deliberately out of scope. The
submission rules add a written list of known limitations. That is GitHub's
list applied to a service instead of a library.

Compared with both general standards, one thing is missing: licensing. This
repo has two licences, explained in `NOTICE`. The course files are under MIT
and everything else is under PolyForm Strict. A short License heading that
points at `NOTICE` would tell a reader which licence covers which files.

### Part 2: How to keep it updated automatically

The writing itself needs Claude. It's best done in the same session as the
change, while the command and its output are still in the conversation. The
writing is rarely what goes wrong. What goes wrong is that nobody notices an
update is due, and nothing checks that it happened. Both of those can be
automated.

The rule to enforce: **by the end of each slice, the README has every command,
env var and migration a reader needs.**

The options, from weakest to strongest:

| # | Mechanism | What it does | Where it fits in the plan | Limits |
|---|---|---|---|---|
| 1 | A line in `CLAUDE.md` | Tells Claude to update the matching README section in the same change | Step 8 (tuning `CLAUDE.md`), or now | Advisory only. The docs call `CLAUDE.md` "context, not enforced configuration". Nothing checks that Claude followed it. |
| 2 | A checklist item for `verification-agent` | Fails the slice when the diff changes how the project runs and the README wasn't updated | Now. The agent already runs on every slice. | A model's judgement, but it sits inside the existing gate: `push-agent` refuses to run unless it's told verification passed |
| 3 | A test that reads the README | For example: every variable name in the `.env.example` files must appear in `README.md` | Step 7, when the `.env.example` files first appear. CI then runs it at no extra cost from step 16. | Deterministic, but only for facts a script can check (names, not prose) |
| 4 | A hook | Fires automatically when Claude edits a file or finishes a turn (see below) | Step 13 (hooks) | The most automatic option, but it needs the most setup and has the most ways to go wrong |

**Hook designs (untested sketches):**

- **Trigger:** a `PostToolUse` hook on `Edit|Write` checks whether the edited
  file is `docker-compose.yml`, an `.env.example` or a migration. If it is,
  the hook adds a note Claude sees, such as "update the README's Environment
  variables section". Watch out: `additionalContext` must be nested inside
  `hookSpecificOutput`. If it sits at the top level, it's silently ignored.
- **Gate:** a `Stop` hook stops Claude from finishing the turn while those
  files have changed and the README hasn't. Things the docs say you need to
  know:
  - Claude Code overrides a Stop hook after 8 blocks in a row.
  - The script should exit early when `stop_hook_active` is true, so it nudges
    once instead of looping.
  - A `prompt` hook can't look at files, because it's a single Haiku call on
    the hook's input.
  - An `agent` hook can read the diff, but agent hooks are experimental, and
    as a Stop hook it would run at the end of every turn.
- **Fully automatic, in CI:** `claude -p` (headless mode) can run in CI and
  draft the update itself. It needs credentials in CI and spends tokens on
  every run. Step 16 of the plan already covers `claude -p`.

**Recommended for this project:**

- **Option 2 now.** It covers what needs judgement: commands, migrations and
  limitations.
- **Option 3 at step 7.** It catches the course's named pitfall, a missing env
  var, without relying on judgement, and it becomes a CI gate at step 16 with
  no extra work.
- **Option 4 as the step 13 exercise.**

Option 1 is optional. It saves a round of FAIL-then-fix, but it costs a line
in every session's context.

## Sources

- `docs/LEARNING-PLAN.md` steps 2, 7, 8, 13 and 16;
  `.claude/agents/verification-agent.md` (its checklist);
  `.claude/agents/push-agent.md` line 11 (refuses unless told both agents
  passed); `NOTICE`.
- Course repo, `modules/module-12-url-shortener-project.md` lines 58, 60, 66
  and 73 (what the README must cover, the known-limitations writeup, the
  headings-first habit, the `.env` pitfall).
- <https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes>
  (what a README typically includes)
- <https://github.com/RichardLitt/standard-readme/blob/main/spec.md> (sections
  and which are required; "designed for open source libraries")
- <https://agents.md> (README for humans, AGENTS.md for agents)
- <https://code.claude.com/docs/en/best-practices> (no README guidance;
  `CLAUDE.md` include list; `CLAUDE.md` is advisory while hooks are
  deterministic; Stop hook overridden after 8 consecutive blocks; `claude -p`
  in CI)
- <https://code.claude.com/docs/en/memory> (the `See @README for project
  overview` example; imports load at launch; "context, not enforced
  configuration")
- <https://code.claude.com/docs/en/hooks> and
  <https://code.claude.com/docs/en/hooks-guide> (handler types; prompt hooks
  use Haiku by default and make one call; agent hooks are experimental;
  `stop_hook_active`; `additionalContext` must sit inside
  `hookSpecificOutput`)
- All pages fetched 2026-09-22 against Claude Code v2.1.278. **Not verified:**
  the hook and test designs above are sketches and have not been built or run.

## Related

- None yet.
