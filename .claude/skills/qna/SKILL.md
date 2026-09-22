---
name: qna
description: Answer a question and file it in the project's Q&A log (docs/QnA.md index, one file per question in docs/qna/). Checks existing answers first.
argument-hint: <your question>
disable-model-invocation: true
allowed-tools:
  - Read
  - Grep
  - Glob
  - Write
  - Edit
  - Bash(git add *)
  - Bash(git commit *)
---

# Q&A: answer the question, then file it

**The question:** $ARGUMENTS

**Settings** (change these to reuse the skill in another project):
- Q&A folder: `docs/qna/`, one file per question
- Index: `docs/QnA.md`

## 1. Look before answering

- Read `docs/QnA.md`. If it is missing, create it from the index template below.
- Search the index and `docs/qna/` for the question's key terms. Search the
  specific names and symbols involved, not just your own paraphrase of the
  question.
- **If an existing entry already answers it:**
  - Re-check anything in it that can go stale (versions, commands, file
    paths, prices, behaviour of tools) before relying on it.
  - Answer from it and cite the file.
  - If it needs correcting or extending, update **that** file: bump
    *Updated*, and add a one-line *Changed:* note saying what changed and why.
    Do not create a near-duplicate.
  - Then go to step 4.

## 2. Answer

- Verify facts before stating them: read the code or the docs, or run a
  read-only command. A filed answer becomes a durable record, so anything not
  verified is labelled as such.
- Lead with a one-line answer, then explain in plain terms.

## 3. File it

- Number: the highest `NNN` in `docs/qna/` plus 1, starting at `001`.
- Write `docs/qna/NNN-<short-kebab-title>.md` from the entry template.
- Add one row to the table in `docs/QnA.md`.

## 4. Record

- Stage only the Q&A files: `git add docs/QnA.md docs/qna/<the file>`.
- Commit with `docs(qna): NNN <short title>`, or `docs(qna): update NNN <short title>`
  when an existing entry changed.
- **Never push.**
- Reply with the answer, then one line: `Filed as docs/qna/NNN-....md`.

## Entry template (`docs/qna/NNN-<short-kebab-title>.md`)

```markdown
# NNN. <Question as a short title>

**Asked:** YYYY-MM-DD · **Updated:** YYYY-MM-DD

> <The question exactly as asked, typos and all>

## Short answer

<One or two sentences.>

## Answer

<The full answer, in plain terms.>

## Sources

- <How it was verified: a file, a docs page, a command and its output, or a course module>

## Related

- [NNN. Title](NNN-other-entry.md)
```

## Index template (`docs/QnA.md`)

```markdown
# Q&A

Questions asked while working through this project. Each one has its own
file in [`qna/`](qna/). New entries come from the `/qna` skill.

| # | Question | Short answer | Asked |
|---|---|---|---|
```
