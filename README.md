# URL Shortener

> **Work in progress.** This README is a skeleton. Each section gets filled in
> when the build reaches it; see [`docs/LEARNING-PLAN.md`](docs/LEARNING-PLAN.md).

<!--
How this skeleton works: the comment under each heading says when that
section's content first exists (a step in docs/LEARNING-PLAN.md) and where it
comes from. Replace the comment with the real content once you reach that step.
-->

## What it does

<!-- Available now. Source: CLAUDE.md §1. -->

## Run locally

<!-- First at step 7 (slice 1): the real `docker compose` commands for Postgres
     and Redis, and how to start the backend. Grows at step 14 (frontend) and
     step 15 (the expired-link cleanup job). -->

## Environment variables

<!-- First at step 7: the .env.example files for backend and frontend. Grows as
     slices add settings. The spec names FRONTEND_ORIGIN and REDIS_URL (§10);
     the database variable's name is chosen when config.py is written. -->

## Migrations

<!-- First at step 9 (slice 2): the Alembic command that creates the `urls`
     table, and how to run it against the local database. -->

## Architecture and decisions

<!-- Grows with each slice. Source: CLAUDE.md §3 (the diagram), plus the
     decisions behind cache-aside redirects, the atomic click count and opaque
     7-character codes (§6-7). Module 15 asks for "the architecture and the
     decisions behind it". -->

## Out of scope

<!-- Available now. Source: CLAUDE.md §5 (auth and user accounts, link
     editing, QR codes, per-click history). -->

## Known limitations

<!-- Available now, then grows. Known so far:
     - CLAUDE.md §12: aggregate-only click analytics; the dedupe index is on the
       raw URL text; no multi-region setup or read replicas.
     - docs/qna/007: the SSRF check can't catch a domain whose DNS changes
       after the link is created, or a target that redirects onward.
     Add every corner you cut, and make each entry specific by step 20 (Module
     12's example: "expired-link cleanup isn't wired to a scheduler — it's a
     manual script"). -->

## Reliability target

<!-- Step 18: an indicator and target for redirects (an SLI and SLO), e.g. "99%
     of redirects within 200 ms, weekly", and how it is measured. -->

## How it was built

<!-- Step 20: the agent workflow as it actually ran. Each slice went through
     testing-agent -> verification-agent -> push-agent and one PR. Include
     what Claude Code did, what you reviewed and changed, and why (Module 15).
     Sources: docs/PLAN.md, the PRs, docs/qna/. -->

## License

<!-- Available now. Two licences, explained in NOTICE: MIT for the course's
     files (LICENSE-COURSE) and PolyForm Strict 1.0.0 for everything else
     (LICENSE). -->
