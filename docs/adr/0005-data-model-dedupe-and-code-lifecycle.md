# 0005. Data model: hash-based dedupe, and codes are never reused

Status: accepted, 2026-09-22 (`docs/PLAN.md` §1)

## Context

- **Freed codes can be hijacked.** The original spec hard-deleted expired
  rows. That frees the code, and the alias rules accept every 7-character
  base62 code, so a stranger could claim a freed code and take over links
  people have already shared. Public stats even show which codes had the
  most clicks.
- **The dedupe race.** Dedupe used a non-unique index on the raw URL text, so
  two identical requests at the same moment could create two rows.
- **Index row size.** Indexing the raw text can also exceed Postgres's B-tree
  row limit.
- **A redundant index.** `idx_urls_short_code` duplicates the index that the
  UNIQUE constraint already creates.

## Decision

- Add `url_hash BYTEA` (a SHA-256 of the canonical URL, computed in the app),
  with a partial unique index on rows that are neither aliases nor expiring.
  Inserts use `INSERT … ON CONFLICT DO NOTHING RETURNING`, then re-select.
- Dedupe applies only when neither an alias nor an expiry is requested.
- **Codes are never freed.** Cleanup *retires* expired rows: it sets
  `retired_at`, clears the URL and hash, and keeps `short_code`. Abuse
  takedowns set `disabled_at`. Retired and disabled codes return 410 and can
  never be claimed again.
- Drop the redundant index. Add a partial index on `expires_at` for cleanup.
  Constraints follow a naming convention, so violations map to error codes.

## Consequences

- The table grows with retired rows, one small row per link ever made. That's
  documented.
- Two identical concurrent requests give one 201 and one 200, with one row.
- The dedupe rule reveals whether a URL was shortened before (201 vs 200).
  That's documented.
