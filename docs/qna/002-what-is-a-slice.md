# 002. What "a slice" means

**Asked:** 2026-09-22 · **Updated:** 2026-09-22

> What does a slice mean?

## Short answer

A slice is one small piece of the build, small enough to review before you
start the next one. The assignment splits the URL shortener into eight
slices. Each one goes through the testing, verification and push agents and
ends as its own pull request.

## Answer

**Where the word comes from.** The assignment says: *"Don't ask Claude Code
to 'build the whole thing' in one shot. Work through it in slices, and run the
agent workflow (§4) after each one."* Module 12 gives the rule for sizing a
slice: *"Each slice should be small enough to actually review before you move
to the next one — a plan you can't check is not a plan, it's a hope."*

**The eight slices, in order:**

| Slice | What it builds | Spec | Plan step |
|---|---|---|---|
| 1 | Repo structure, plus `docker-compose.yml` for Postgres and Redis | `CLAUDE.md` §4 | 7 |
| 2 | The `urls` table, created by an Alembic migration | §7 | 9 |
| 3 | `POST /api/v1/shorten`: validation, SSRF guard, reserved aliases, idempotency | §6 | 10 |
| 4 | `GET /{short_code}`: cache-aside redirect, atomic click count | §6 | 11 |
| 5 | `GET /api/v1/urls/{short_code}`: stats | §6 | 12 |
| 6 | Rate limiting, CORS, `/api/health` | §9–10 | 13 |
| 7 | A React form that calls `/shorten` and shows the result | — | 14 |
| 8 | The expired-link cleanup script | §11 | 15 |

Plan step 8 isn't a slice. It tunes `CLAUDE.md` between slices 1 and 2.

**One slice, start to finish:** Claude implements it, then the
testing-agent, verification-agent and push-agent run in that order. The last
step opens a pull request, which you review and merge yourself. Only then does
the next slice start. The learning plan also gives each slice its own named
session.

**Why build this way, and why it matters with Claude in particular:**

- **It avoids a failure the course names.** Asking for the whole system in one
  prompt is *"the fastest way to end up with a plausible-looking
  implementation that quietly skips the SSRF check or does read-then-write
  click counting."* A small diff is one you can actually read.
- **A failed check points to its cause.** When the tests or the verification
  agent fail on one slice, the problem is in that slice. The assignment's
  words: *"don't let five features pile up untested."*
- **It keeps context small.** Claude's performance degrades as the context
  window fills up (Claude Code best practices). One slice per session keeps
  each session on one job.

**The course's term is looser than "vertical slice".** Elsewhere a vertical
slice usually means one feature built through every layer, from UI to
database. The course never uses the word "vertical". Its slices are chunks in
build order: the frontend is its own slice 7 rather than being built alongside
each endpoint.

**What the tools don't know.** The word "slice" appears in `ASSIGNMENT.md`
and the learning plan. It doesn't appear in `CLAUDE.md` (the file Claude loads
every session) or in any of the three agent files. Two consequences:

- A fresh session doesn't know the slice order or which slice you're on
  unless you tell it. `ASSIGNMENT.md` isn't loaded automatically, and neither
  is `TASKS.md`. Step 6 exists so there's one file to point Claude at: "read
  TASKS.md and continue".
- The verification-agent's checklist covers the whole spec, not one slice.
  When you run the agents after an early slice, tell them which slice they're
  reviewing.

## Sources

- `ASSIGNMENT.md` §3, lines 40 and 51 (the eight slices, and running the
  agent workflow after each).
- Course repo, `modules/module-12-url-shortener-project.md` lines 26, 36 and
  44 (the slice sizing rule, the whole-system-prompt pitfall, "rewards
  discipline more than speed").
- `docs/LEARNING-PLAN.md`: its working rules and steps 3, 6 and 7–15.
- `grep -i slice` over `CLAUDE.md` and `.claude/agents/*.md` found no matches.
  `grep -i vertical` over `ASSIGNMENT.md` and the course's `modules/` and
  `labs/` found no matches. `grep @ CLAUDE.md` found no imports.
- <https://code.claude.com/docs/en/best-practices> (performance degrades as
  the context window fills).
- <https://code.claude.com/docs/en/memory> (what loads at startup: `CLAUDE.md`
  files and their `@` imports).

## Related

- [001. What goes in a README, and how to keep it updated automatically](001-readme-standard-and-auto-updates.md)
