# 0008. Rate limiting

Status: accepted, 2026-09-22 (`docs/PLAN.md` §1)

## Context

The spec names "slowapi (or equivalent)". slowapi uses the synchronous
`limits` storage API (confirmed in its source), so its Redis calls would block
the async event loop, which §2 forbids. Three more problems:
- **Order.** A limiter written as a FastAPI dependency runs after the body
  has been parsed, so malformed requests never count.
- **IPv6.** A client can rotate through its /64 and dodge a per-address limit.
- **Separate INCR and EXPIRE.** They can leave a counter with no expiry, which
  blocks that client forever.

## Decision

- Write our own limiter as ASGI middleware on `redis.asyncio`, scoped to the
  paths it protects.
- INCR and EXPIRE run atomically, in a Lua script or MULTI.
- IPv6 clients are keyed per /64.
- Where the client IP comes from is an explicit setting. Behind a proxy, only
  its address is trusted, and never `*`.
- A 429 carries `Retry-After`.
- `POST /shorten` gets 10 a minute (assumed). Read endpoints get lenient
  limits.

## Consequences

- One test runs two app instances sharing one Valkey and checks that they
  enforce a single combined limit, which proves the limiter isn't in-memory
  (§10).
