# Learning Plan: Claude Code, Learned Through the URL Shortener

This is the plan for **learning**, not for building. The URL shortener is only
the vehicle. Each lab uses one slice of the build to practise one Claude Code
mechanism from the course ("Claude Code: Zero to Hero"), with a prediction
written first, a deliberate experiment, and a recorded result.

The build plan lives separately in `docs/PLAN.md`, written in Lab 1.

---

## The loop: run every lab this way

1. **Fresh session.** Start `claude` from the repo root, then `/rename lab-N-<topic>`.
   One lab per session. The docs' first rule is that context is the scarce
   resource, so don't carry one lab's clutter into the next.
2. **Predict.** Before running anything, write down in `docs/LEARNING-LOG.md` what
   you expect to happen. A prediction you can be wrong about is what turns
   doing into learning.
3. **Do** the steps.
4. **Break it once.** Every lab has one experiment that deliberately breaks the
   mechanism, run on a throwaway branch (`git switch -c break/lab-N`) that never
   gets merged. Seeing a mechanism fail teaches what it was actually doing.
5. **Capture evidence, not impressions.** The command and its output, the
   verdict text, `/context` numbers, a screenshot.
6. **Record.** One `LEARNING-LOG.md` entry per lab (template at the bottom), plus
   commits whose messages carry the lesson. History is the learning record.
7. **Measure context.** Run `/context` at the start and end of every lab.

---

## The spine: from advice to enforcement

The course climbs a ladder. Each rung makes a rule harder to skip:

| Rung | Mechanism | Can it be skipped? | Lab |
|---|---|---|---|
| 1. Advice | `CLAUDE.md` | Yes. Claude may not follow it | 5 |
| 2. Delegation | Subagents with a `tools:` list | Their tools can't be exceeded, but calling them is optional | 2, 4 |
| 3. Procedure | Skills and slash commands | Only runs when invoked | 6 |
| 4. Enforcement | Hooks | No, not inside Claude Code | 9 |
| 5. Portability | Plugins | (packages rungs 1–4) | 12 |
| 6. Outside Claude | CI + branch protection | No, not even for a human | 11 |

**Carry this question through every lab:** for each rule in this project,
which rung is it on, and which rung *should* it be on?

---

## Ground rules

- **Work in the course's permission modes, not bypass.** In bypass mode no
  permission prompt ever appears, so you never experience what the modes do. Lab 0
  sets this repo to start in `acceptEdits`. Launch plain `claude`, without any
  bypass flag or alias.
- **Do it by hand once before automating it.** Run the three agents manually
  before `/ship-slice` does it for you, and before a hook enforces it.
- **Two rounds maximum on any review loop.** Reviewers asked to find gaps always
  find some.
- **Log findings, don't chase them.** A lab is finished when its mechanism is
  understood, not when the app is perfect.
- **One concern per commit, with the lesson in the body.**

---

## Labs

Build slices come from `ASSIGNMENT.md` §3. Each lab rides on the slice named
beside it.

| Lab | Topic | Course module | Rides on | Time |
|---|---|---|---|---|
| 0 | Baseline: what Claude sees | 4, 5, 9 | before any code | 30–45 min |
| 1 | Interview, then plan | 7 | before any code | 60–90 min |
| 2 | Expert review: personas in parallel | 7, 13 | the plan | 60–90 min |
| 3 | TASKS.md as a checkpoint | 8 | the plan | 30 min + ongoing |
| 4 | The three-agent workflow, by hand | 12 | slice 1: scaffold | 90–120 min |
| 5 | CLAUDE.md engineering | 5 | after slice 1 | 45–60 min |
| 6 | Skills and plugins | 9 | slice 2: schema | 60 min |
| 7 | Four reviewers, one diff | 6, 9, 13 | slice 3: shorten + SSRF | 45 min |
| 8 | MCP vs CLI | 10 | slice 4: redirect + clicks | 45 min |
| 9 | Hooks: discipline into gates | 11 | after slices 5–6 | 90 min |
| 10 | Context management | 13 | slice 7: frontend | 30 min |
| 11 | CI, branch protection, Claude in GitHub | 14 | after slice 8 | 90 min |
| 12 | Package it as a plugin | 11 | the finished harness | 60–90 min |
| 13 | Submission and reflection | 12 | the finished project | 60 min |

### Lab 0: Baseline, what Claude sees before you type (Modules 4, 5, 9)

1. `/exit`, then start a fresh `claude` in the repo root.
2. Ask *"which agent types do you have?"* Expect `testing-agent`,
   `verification-agent`, `push-agent`.
3. **Predict, then check:** how much of the context window do your global
   `CLAUDE.md`, this project's `CLAUDE.md`, memory, and tool definitions take up
   before you have typed anything? Run `/context`.
4. Run `/memory` and see which memory files load.
5. Create `.claude/settings.json` with `{"permissions": {"defaultMode": "acceptEdits"}}`.
   Project settings override your user default (`auto`). Commit it.
6. Create `docs/LEARNING-LOG.md` from the template below and commit it.

- **Break it:** on a break branch, move one agent file out of `.claude/agents/`,
  restart, and ask for the agent list. Then move it back.
- **Versus your setup:** what does your personal harness cost in context here,
  where none of its vault machinery applies?

### Lab 1: Interview, then plan (Module 7; docs: *Let Claude interview you*, *Explore → Plan*)

1. `claude --permission-mode plan`
2. Ask Claude to interview you with `AskUserQuestion` about building what
   `CLAUDE.md` and `ASSIGNMENT.md` describe: *"dig into the hard parts I might not
   have considered"*. Then have it write the build plan.
3. Read the whole plan. Use `Ctrl+G` to edit it directly. Push back on at least
   one gap (the Module 7 exercise).
4. Save the approved plan as `docs/PLAN.md` and commit it.

- **Break it:** in a separate session outside plan mode, on a break branch, ask
  *"build the whole thing"*. Press `Esc` after a few minutes. Did it do the SSRF
  check? The atomic counter? This is the one-shot pitfall Module 12 warns about.
- **Versus your setup:** your pre-brief and plan agents.

### Lab 2: Expert review with personas, in parallel (Modules 7 and 13)

1. Write three reviewer agents in `.claude/agents/`: `security-reviewer`,
   `reliability-reviewer`, `claude-practices-reviewer`. Each gets a persona in
   the body, a `description` saying when to use it, and **read-only tools**
   (`Read, Grep, Glob`). The practices reviewer also gets `WebFetch`, so it can read
   <https://code.claude.com/docs/en/best-practices> and Anthropic's current
   model-specific prompting guidance.
2. **Predict:** does a new agent file in the existing folder load without a restart?
3. **Sequential pass (Module 7):** in one session, have Claude review `docs/PLAN.md`
   as each persona in turn. Save the output.
4. **Parallel pass (Module 13):** in a fresh session, *"Use the security-reviewer,
   reliability-reviewer and claude-practices-reviewer subagents in parallel on
   docs/PLAN.md. Report only gaps that affect correctness or the stated
   requirements. Synthesize."*
5. Compare the two passes: what did fresh, separate contexts catch that one
   shared context missed, and the other way round?
6. You decide which findings to act on. Revise the plan, two rounds at most.
   Commit the reviewers and the revisions separately.

- **Break it:** give one reviewer `Edit` in its tools and ask it to "fix what you
  find". This shows why reviewers stay read-only.
- **Versus your setup:** your `deep-plan-review` (Architecture, Pragmatist, Risk).

### Lab 3: TASKS.md as a checkpoint (Module 8)

1. Have Claude turn `docs/PLAN.md` into `TASKS.md`, with one item per slice and
   per setup step. Commit it.
2. Tell Claude to tick items off as it finishes them. That rule sits on
   rung 1, so watch whether it is actually followed.
3. **Resume test (during Lab 4):** mid-slice, `/clear`, then *"read TASKS.md and
   continue"*. Spot-check the "done" items against the actual code.

- **Break it:** tick an item that isn't done. Does a fresh session trust the
  checkbox, or check the code?
- **Versus your setup:** your `repo-do issue` tracker.

### Lab 4: The three-agent workflow, by hand (Module 12). Slice 1: scaffold

1. In `acceptEdits` mode, build slice 1 (repo structure plus `docker-compose.yml`)
   from the plan. Review it with `/diff` before going further.
2. By hand, in order: *"Use the testing-agent…"*, then read the verdict. *"Use the
   verification-agent…"*, then read. *"Use the push-agent to commit and open a PR"*.
3. Merge the PR yourself. Merging is a human decision.

- **Break it (two experiments):**
  1. Call the push-agent first, without saying the others passed. Expect a refusal.
  2. On a break branch, delete the `tools:` line from `verification-agent.md`,
     and ask it to fix something it found. Watch it edit. Restore it.
- **Versus your setup:** your adversarial reviewer is a prompt template run on a
  general-purpose agent. Theirs is a typed agent.

### Lab 5: CLAUDE.md engineering (Module 5; docs: *Write an effective CLAUDE.md*)

1. **Predict** which lines fail the docs' test: *"Would removing this cause Claude
   to make mistakes?"*
2. Run `/doctor` and compare its proposed cuts with your prediction.
3. Apply the docs' include/exclude table:
   - Add the real commands from the scaffold (run tests, lint, start the stack).
   - Move the API contract and schema out into `docs/SPEC.md`.
4. **Predict, then check with `/context`:** does referencing `docs/SPEC.md` with an
   `@` import actually save context, or is it loaded anyway?
5. Make one **knowledge skill**, e.g. `url-safety` holding the SSRF rules, with a
   description saying to use it when working on URL validation.
6. In a fresh session, ask a question that the moved text answers. Did Claude
   find the answer?

Each change is its own commit.

- **Versus your setup:** apply the same test to one section of your global
  `CLAUDE.md`.

### Lab 6: Skills and plugins (Module 9). Slice 2: schema and migration

1. Install the `pyright-lsp` and `typescript-lsp` plugins from the official
   marketplace (`/plugin`), **at project scope**, so the choice lands in
   `.claude/settings.json` and in history. Read each plugin's files first (the
   Module 9 pitfall), and check its README for anything it needs installed.
2. Write a `/ship-slice` project skill that runs testing → verification → push
   agents in order and stops on any FAIL. Set `disable-model-invocation: true`,
   because it pushes. `skill-creator` can help.
3. Ship slice 2 with `/ship-slice`.

- **Break it:** give the Lab 5 knowledge skill a vague description, such as
  "helps with code". Does it still load when you edit `security.py`?
- **Versus your setup:** your `repo-do` verbs. There, discovery needed a written
  rule. Here, a skill's description does the surfacing.

### Lab 7: Four reviewers, one diff (Modules 6, 9, 13). Slice 3: shorten and SSRF

1. On a break branch, **plant a known bug** in the finished slice, e.g. let
   `169.254.169.254` through the SSRF check.
2. Run all four reviewers on that diff:
   - the `verification-agent`,
   - `/code-review`,
   - `/security-review`,
   - optionally the `security-guidance` plugin. Read it first: it runs hooks and
     extra model calls on every turn.
3. Build a table: reviewer × caught or missed × noise × cost.

- **Versus your setup:** your adversarial reviewer on the same planted bug.

### Lab 8: MCP vs CLI (Module 10). Slice 4: redirect and click counting

1. Add a **read-only** Postgres MCP server at project scope (`.mcp.json`) pointed at
   the local Docker database. Choose one the Module 10 way: Anthropic's connector
   directory or the vendor's own docs, following the maintainer's instructions.
2. Run the concurrent-redirect test, then check `click_count` two ways: through
   MCP, and through `docker compose exec … psql` from Bash.
3. Compare accuracy and `/context` cost. The docs claim CLI tools are the most
   context-efficient. Check whether that holds here.

- **Break it:** stop the database container. How does each path report the
  failure?

### Lab 9: Hooks, turning discipline into gates (Module 11; `CLAUDE.md` §13 stretch goal)

1. Add the three `PreToolUse` hooks from §13:
   - the testing-agent may only edit test files,
   - the verification-agent can't run commands that change anything,
   - the push-agent reruns the tests before any `git push`.

   Follow Claude Code's subagent and hooks docs.
2. Browse them with `/hooks`.

- **Break it:** this is the lab. Attempt each violation and watch it get blocked.
- **Versus your setup:** your Stop hook replaced an agent nobody remembered to
  run. When a rule keeps failing, change the mechanism.

### Lab 10: Context management (Module 13). Slice 7: frontend

This lab is threaded through the others, with one deliberate session here:

1. During a long frontend session, watch `/context` grow.
2. Try `/compact Focus on …` against `/clear` plus a `TASKS.md` resume. Which one
   continues better?
3. Use `/rewind` to undo an experiment, and `/btw` for a side question that stays
   out of the history.

### Lab 11: CI, branch protection, and Claude in GitHub (Module 14)

1. Add a GitHub Actions workflow for lint, type-check and tests, through a PR.
2. Protect `main` so the workflow must pass. This works because the repo is
   public; on the free plan a private repo can't do it (checked on
   `sunnynarula/arduino`).
3. Open a PR with a failing test and confirm the merge is blocked.
4. Run `/install-github-app`, choosing the review workflow, then mention `@claude`
   on a PR. If it asks for the `workflow` token scope, run `gh auth refresh -s workflow`.
5. Run `claude -p` locally to see what the Action runs.

GitHub-side settings (protection, the app, secrets) are not in git history.
Record them in the log.

### Lab 12: Package it as a plugin (Module 11)

1. Bundle the three workflow agents, the three reviewers, `/ship-slice`, the
   knowledge skill and the hooks under one `.claude-plugin/plugin.json`.
2. Test it in a scratch project with `claude --plugin-dir`. Use `/reload-plugins`
   after edits, and note the namespacing (`/<plugin>:ship-slice`).

- **Versus your setup:** what would it take to package your own `~/.claude`
  harness this way?

### Lab 13: Submission and reflection (Module 12)

1. Write `README.md`: what the app does, how to run it (compose, env vars,
   migrations), and what is out of scope.
2. Write **known limitations** that are specific, never vague.
3. Close the learning log with your top five lessons, plus an **"adopt back into
   my own setup"** list.
4. Submit the repo link.

---

## Learning-log entry template

```markdown
## Lab N: <topic> (<date>)

**Predicted:**
**Happened (evidence):**
**Surprised me:**
**Versus my own setup:**
**Rung:** which rung of the ladder this lab's rule ended on, and which it should be on
```
