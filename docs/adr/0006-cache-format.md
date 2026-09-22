# 0006. Cache format and TTL

Status: accepted, 2026-09-22 (`docs/PLAN.md` §1)

## Context

The spec caches `url:{code}` → URL for a fixed hour. A link that expires, or is
disabled for abuse, would keep redirecting from the cache for up to an hour.

## Decision

- **Key and value:** `url:v1:{code}` → `{url, expires_at, disabled}`. The `v1`
  lets the format change later without clashing with old entries.
- **Every cache hit** re-checks `expires_at` against the injected clock, and
  checks `disabled`.
- **TTL** = min(1 hour, time until `expires_at`). It's set with
  `SET … PXAT`, and nothing is cached when that comes to zero or less.
- **Disable and retire** evict the key immediately.
- **The store is disposable:** `maxmemory` with `volatile-lru`, and
  persistence off. Every key has a TTL.

## Consequences

- An expired or disabled link can't be served from a stale cache entry.
- Losing the cache only costs speed, never correctness.
