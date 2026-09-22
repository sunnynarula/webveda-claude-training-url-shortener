# 005. How often the push-agent pushes

**Asked:** 2026-09-22 · **Updated:** 2026-09-22

> how often does the push agent push? It seems like we are pushing per slice from your description.

## Short answer

Yes, once per slice. Each run of the push-agent makes one commit, one push and
one pull request, and the course runs it once at the end of every slice. That's
about eight pushes across the build, plus an extra run whenever a slice needs a
fix after review. It never runs on a schedule; something has to call it.

## Answer

**One run means one push.** Each time it's called and told that both checks
passed, the push-agent commits, runs `git push -u origin <branch>` once, opens
a PR and stops. Nothing inside it repeats.

**How often it's called.** The course ties it to slices. The assignment says:
*"After each slice, run the agent workflow before moving to the next one."*
`CLAUDE.md` §8 says to run the three agents "for every change". That can mean
more than once per slice, because of reruns (see point 3 below). With eight
slices, expect about eight pushes. Each goes on its own branch, with its own
PR that you merge.

**What calls it.** Never a timer. Either you ask for it, or Claude hands work
to it. The subagent docs say Claude can hand work to an agent automatically
when a task matches that agent's description. This agent's description says to
use it only after both checks pass. The plan's `/ship-slice` skill (step 9)
runs all three agents, and it's marked manual-only because it pushes.

**What it leaves to you between pushes.** Its instructions end once it has
reported the PR, so three things are left to you:

1. **It never pushes `main`, so docs committed directly to `main` stay
   local.** When it runs at the end of slice 1 on `main`, it creates the
   slice's branch from your local `main`. Any commits that are on your local
   `main` but not yet on GitHub go into slice 1's PR. When this was written,
   local `main` held 8 such commits, all docs: the plan, the `/qna` skill and
   the Q&A entries. Pushing `main` before slice 1 keeps that PR to the slice.
2. **After you merge a PR, nothing takes you back to `main`.** It creates a
   branch only when you're on `main`, and it never switches back or pulls.
   Before the next slice, run `git checkout main && git pull`. If you skip
   that, the next slice would be built on the previous slice's branch. That
   hasn't been tried yet, and neither the plan nor the course includes this
   step.
3. **A rerun for a fix repeats `gh pr create`.** If you rerun it on the same
   branch after review feedback, it commits and pushes to that branch, which
   updates the open PR. But its last step runs `gh pr create` again, and gh
   normally refuses to open a second PR for a branch that already has one.
   That's gh's usual behaviour, not tried in this repo. Expect it to report
   the error, or tell it up front that the PR already exists.

## Sources

- `.claude/agents/push-agent.md` (one commit and one `git push` per run; it
  creates a branch only when on `main`; it ends by reporting the PR).
- `ASSIGNMENT.md` line 51 ("After each slice"); `CLAUDE.md` §8 ("for every
  change"); `docs/LEARNING-PLAN.md` step 7 ("merge the PR") and step 9
  (`/ship-slice` is manual-only "because it pushes").
- `grep` for `git pull`, `checkout main` and similar across the plan,
  `ASSIGNMENT.md`, `CLAUDE.md` and the agent files: nothing covers syncing
  `main` after a merge.
- `git status -sb` on 2026-09-22: `main...origin/main [ahead 8]`.
- <https://code.claude.com/docs/en/sub-agents> (automatic delegation based on
  an agent's description).
- **Not verified:** what the agent actually does when it's started on an old
  branch, and gh refusing a second `gh pr create` (gh 2.45.0 is installed;
  neither has been tried here).

## Related

- [004. What the push-agent is](004-what-is-the-push-agent.md)
- [002. What "a slice" means](002-what-is-a-slice.md)
