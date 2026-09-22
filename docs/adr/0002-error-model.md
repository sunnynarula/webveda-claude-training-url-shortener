# 0002. One error model (RFC 9457)

Status: accepted, 2026-09-22 (`docs/PLAN.md` §1)

## Context

Out of the box, the stack returns errors in three different shapes:
- FastAPI's `HTTPException` returns `{"detail": "..."}`.
- Validation errors return a list that echoes the user's input back.
- Unhandled exceptions become a plain-text 500 from Starlette's
  `ServerErrorMiddleware`. That middleware sits outside every user middleware,
  so the 500 also loses the CORS and `X-Request-ID` headers, and the browser
  reports a CORS failure instead of the real error.

## Decision

- Every error is RFC 9457 `application/problem+json` with `type`, `title`,
  `status` and `detail`, plus a machine-readable `code` and the `request_id`.
- Handlers cover the router's own 404 and 405 (`StarletteHTTPException`),
  413, 422 and 429. 422 responses list the problem fields and never echo input
  values.
- A pure-ASGI catch-all middleware sits innermost. It turns any unhandled
  exception into the same JSON 500, so the outer request-ID and CORS
  middleware still add their headers.
- When several errors apply, report 429 > 413 > 422 > 400 > 409.

## Consequences

- Tests assert on `code`, not on wording, so messages can change without
  breaking them.
- The frontend has one error shape to render.
- A route that isn't found and a short code that isn't found share status
  404, so tests tell them apart by `code`.
