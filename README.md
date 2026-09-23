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

<!-- Grows at step 14 (frontend) and step 15 (the expired-link cleanup job). -->

You need Docker with Compose v2, and [uv](https://docs.astral.sh/uv/), which
installs the right Python (3.12) itself.

1. **Start Postgres and Valkey** (a Redis-compatible store). Both listen on
   `127.0.0.1` only.

   ```bash
   cp .env.example .env          # then set POSTGRES_PASSWORD in .env
   docker compose up -d --wait
   ```

   The first start also creates `urlshortener_test`, the database the tests
   use.

2. **Configure and start the backend.**

   ```bash
   cd backend
   cp .env.example .env          # put the same password in DATABASE_URL
   uv sync
   uv run python -m app          # serves http://127.0.0.1:8000, logging JSON
   ```

   From another terminal:

   ```bash
   curl -i http://127.0.0.1:8000/api/health/live
   ```

3. **Run every check CI runs** — lint, formatting, types, tests with branch
   coverage, the suppression ratchet and the licence gate. It is run from the
   repository root, not from `backend/`:

   ```bash
   cd ..
   scripts/check.sh
   ```

Stop the services with `docker compose down`, adding `-v` to delete the
database volume too.

## Environment variables

<!-- Grows as slices add settings, and at step 14 for the frontend. -->

The backend reads these from the environment. In development it also reads
`backend/.env`; copy [`backend/.env.example`](backend/.env.example) to make
one. The tests never read either `.env` file.

| Variable | Required | Default | What it's for |
|---|---|---|---|
| `DATABASE_URL` | yes | | Postgres connection URL. A Neon-style URL ending in `?sslmode=require&channel_binding=require` works as it is. |
| `REDIS_URL` | yes | | The Valkey (or Redis) URL, for example `redis://localhost:6379/0`. |
| `PUBLIC_BASE_URL` | yes | | The origin short links are built on, for example `https://sho.rt`. |
| `FRONTEND_ORIGIN` | yes | | The one origin allowed to call the API from a browser (CORS). |
| `LOG_LEVEL` | no | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL`. |
| `HOST` | no | `127.0.0.1` | The address `python -m app` listens on. |
| `PORT` | no | `8000` | The port `python -m app` listens on. |

`PUBLIC_BASE_URL` and `FRONTEND_ORIGIN` must be bare origins: a scheme and a
host with an optional port, and no path, query or fragment. They must use
`https`, except that `http` is allowed for the local hosts: `localhost`,
`127.0.0.1` and `[::1]`. They must also be printable ASCII, so a host written
in another script goes in its punycode form. The app refuses to start
otherwise.

The root [`.env.example`](.env.example) holds the Compose variables
(`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`).

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

- **Course files** (`CLAUDE.md`, `ASSIGNMENT.md`, `.claude/agents/testing-agent.md`,
  `verification-agent.md`, `push-agent.md`) are MIT-licensed by the course's
  author. See [`LICENSE-COURSE`](LICENSE-COURSE).
- **Everything else** is under the
  [PolyForm Noncommercial License 1.0.0](LICENSE). It's free for any
  noncommercial purpose: you may use it, change it and share it, as long as
  the licence and its `Required Notice:` line go with every copy.
- **Commercial use** needs a separate licence.
  [Open an issue](https://github.com/sunnynarula/webveda-claude-training-url-shortener/issues)
  to ask for one.
- **Credit:** if you show, demo or write about this project, please credit
  Sunny Narula and link to this repository.
- **Contributions:** outside pull requests need a signed Contributor License
  Agreement (CLA) first, so the project can keep offering commercial licences.
  Until the CLA is set up, please open an issue instead of a pull request.

[`NOTICE`](NOTICE) lists exactly which files are under which licence.
