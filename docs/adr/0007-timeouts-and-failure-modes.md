# 0007. Timeouts and failure modes

Status: accepted, 2026-09-22 (`docs/PLAN.md` §1)

## Context

- **Redis.** redis-py 8.1.0's defaults (`redis/_defaults.py`) are 5-second
  socket and connect timeouts, plus 10 retries with backoff. A Redis that
  stops answering would stall each redirect for seconds, or far longer if
  packets are silently dropped.
- **Postgres.** asyncpg defaults to a 60-second connect timeout and no query
  timeout.
- **Held connections.** A database session held open by a `yield` dependency
  stays open while the background click task runs. With a small pool, that can
  deadlock.

## Decision

- **Redis:** about 200 ms connect and read timeouts, no retries, and a bounded
  pool.
- **Postgres:** asyncpg `command_timeout`; SQLAlchemy `pool_timeout`,
  `pool_pre_ping`, and `pool_recycle` under 5 minutes. `statement_timeout`
  is set on the app's database role, because a per-session `SET` doesn't
  survive a transaction-mode pooler.
- **Short sessions:** lookups use short `async with` session blocks, and
  never a request-long session.
- **Failure behaviour:**
  - If Redis fails, redirects fall back to Postgres and the error is logged.
  - `/shorten` fails closed with 503 when the rate limiter can't count.
  - With Postgres down, a cache hit still redirects, and the failed click
    update is logged.

## Consequences

- Tests cover a *stopped* Redis and a *silent* one (a socket that accepts
  connections but never replies), with a latency bound. They also cover a
  database pool of size 1.
