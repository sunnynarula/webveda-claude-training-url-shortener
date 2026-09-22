# 006. Why one push and PR per slice, and not one at the end

**Asked:** 2026-09-22 · **Updated:** 2026-09-22

> why a per slice push and pr? What priciple is this? Why not one push when we are done? Is the instructor expecting me to merge the 8 prs to experience the flow?

## Short answer

It's the principle of working in small batches, which continuous integration
is built on: change a little, check it, merge it, repeat. A PR per slice gives
each slice its own review, its own record and, once CI exists, its own
automated gate. The course's instructions add up to one PR per slice, merged
by you. They never say "eight", but eight slices with one PR each is what they
produce.

## Answer

### The principle

It's called **working in small batches**. DORA, the long-running research
programme on software delivery, defines it as *"an essential principle in any
discipline where feedback loops are important, or you want to learn quickly
from your decisions."* Its guidance is to merge small changes into the main
branch at least once a day. It also says that *"any batch of code that takes
longer than a week to complete and check is too big."*

Two other ideas apply it:

- **Small code reviews.** Google's engineering practices say small changes are
  "reviewed more quickly", "reviewed more thoroughly", "less likely to
  introduce bugs" and "simpler to roll back". They define a good change as
  *"one self-contained change"*, and say 100 lines is usually reasonable while
  1,000 is usually too large.
- **Continuous integration.** Module 14 defines it as *"every change gets
  merged frequently and verified automatically."*

A slice is the course's unit for one small batch (see 002).

### Why not one push at the end

A single PR at the end would hold the whole app. That would very likely be
well over the 1,000 lines Google calls usually too large (an estimate; the app
isn't built yet). In practice nobody reviews a change that size properly, so
it gets approved on trust. That's the failure Module 12 warns about: *"a
plausible-looking implementation that quietly skips the SSRF check."*

Merging per slice gives you:

- **A review you can actually do.** Each PR is one slice.
- **Feedback while fixing is cheap.** A wrong schema found at slice 2 is fixed
  before six more slices are built on top of it. DORA: small batches reduce
  "the time it takes to get feedback on changes."
- **A `main` that always works.** After each merge, `main` holds finished,
  checked code. If you stop halfway, what's merged is done.
- **Undo in one step.** Each slice is one PR you can revert on its own.
- **Checks with one subject.** The tests, the verification agent and later CI
  each look at one slice, so a failure points straight at it.
- **A check on the AI's work.** DORA says small batches act as *"a safety net
  for AI adoption."* When Claude writes the code, your review of each small PR
  is where you catch what it got wrong. Module 15: *"review the diff before it
  merges ... your review is the actual deliverable."*

**What one push at the end would save you:** ceremony. For a solo developer
with no second reviewer, each slice costs a branch, a PR and a merge. Also, CI
only arrives at plan step 16, after all eight slices. Until then a PR is a
point to review and a record of what happened, not an automated gate.

### Is the instructor expecting eight merged PRs?

The written materials point that way, without giving a number:

- `ASSIGNMENT.md` §3 says to run the agent workflow after each slice.
- `ASSIGNMENT.md` §4 says the push-agent *"opens a PR, it doesn't merge —
  that's still your call, do it from GitHub once you're happy."*
- The same section gives the reason: *"the whole point of the exercise is
  experiencing why a 'just push it' workflow breaks down."*
- Module 12 says to run the full sequence *"even if the slice feels too small
  to bother"*, and allows a PR link as the submission *"if your instructor
  wants to see the agent workflow in action."*
- The push-agent writes both verdicts into each PR description, so every PR
  is a record that the workflow ran.

So expect about eight PRs, one per slice, each merged by you. There will be
more if you split a slice; the count isn't the point. Whether the instructor
will actually open them only they can say. `ASSIGNMENT.md` §6 lets them ask for
a PR link instead of the repo link.

### When you merge

GitHub offers three ways to merge a PR. **Squash and merge** folds all of a
slice's commits into one, including any fix commits, so corrections disappear
from the history. **Create a merge commit** keeps every commit and records
where each slice landed. If the history is meant to be a learning record,
choose the merge commit.

## Sources

- <https://dora.dev/capabilities/working-in-small-batches/> (definition,
  benefits including "a safety net for AI adoption", merge-frequency guidance).
- <https://google.github.io/eng-practices/review/developer/small-cls.html>
  (why small changes are better; "one self-contained change"; 100 vs 1,000
  lines).
- `ASSIGNMENT.md` §3, §4 and §6 (lines 51, 73, 75 and 90).
- Course repo: `modules/module-12-url-shortener-project.md` lines 36, 56 and
  67; `modules/module-14-cicd-and-reliability.md` line 64 (continuous
  integration); `modules/module-15-beyond-claude-code.md` line 12 ("review the
  diff before it merges").
- `.claude/agents/push-agent.md` step 6 (both verdicts in the PR description);
  `docs/LEARNING-PLAN.md` step 16 (CI arrives after the slices).
- **Not verified:** the size of the finished app, and whether the instructor
  will look at the PRs.

## Related

- [005. How often the push-agent pushes](005-how-often-the-push-agent-pushes.md)
- [002. What "a slice" means](002-what-is-a-slice.md)
- [004. What the push-agent is](004-what-is-the-push-agent.md)
