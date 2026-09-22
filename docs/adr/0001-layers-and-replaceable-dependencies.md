# 0001. Layers and replaceable dependencies

Status: accepted, 2026-09-22 (`docs/PLAN.md` §1)

## Context

Several tests have to control things the code normally gets from the outside
world:
- **Time:** expiry, the moment a link turns 410, the cache TTL.
- **Randomness:** a short-code collision followed by a retry.
- **DNS:** the SSRF checks.
- **Background timing:** proving a click is recorded *after* the redirect was
  sent.

If route handlers call `datetime.now()`, `secrets` or the resolver directly,
these tests can't be written, or they turn flaky.

## Decision

- The code is layered: routers → `LinkService` → `LinkRepository`,
  `LinkCache` and `ClickRecorder`.
- The outside world reaches the code through four small protocols, each
  provided as a FastAPI dependency that tests override: `Clock`,
  `CodeGenerator`, `Resolver` and `ClickRecorder`.
- Business rules take the time from the injected `Clock` and pass it into
  queries as a parameter. They never use SQL `now()`.
- Each seam is added in the slice that first needs it, not in advance.

## Consequences

- Tests are deterministic, and there's no monkeypatching of library internals.
  Patching `loop.getaddrinfo` would also intercept the database and Redis
  connections.
- If Vercel can't finish background tasks after all, a different
  `ClickRecorder` (for example, a queue) can replace the current one without
  touching the service.
