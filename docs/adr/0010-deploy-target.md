# 0010. Deploy target: Vercel, with one origin

Status: accepted, 2026-09-22 (`docs/PLAN.md` §1, §8 slice 9)

## Context

The course deploys to Vercel. The architect review worried that serverless
hosts may not finish `BackgroundTasks` after the response is sent, which would
break click counting. The DevOps review checked Vercel's Python runtime: it
ends a request only once the ASGI app returns, so background tasks do complete.

Separately, Vercel's Hobby plan is for non-commercial, personal use only.

## Decision

- Deploy on Vercel, with the frontend and the API on **one origin**. In
  production, routing keeps `/api/*` and `/{code}` on the API. In
  development, Vite's proxy does the same job.
- CORS stays strict for development and for anyone deploying on other hosts.
- `ClickRecorder` (ADR 0001) stays swappable.
- Slice 9 verifies on the live deployment that a redirect's click is counted.
- Migrations run from CI over the database's *direct* URL, before deploying.
  The app uses the *pooled* URL.
- Rollback means rolling forward only.

## Consequences

- The connection-URL handling must cope with Neon-style URLs. asyncpg rejects
  `sslmode` and `channel_binding` in the query string, so those are translated
  into explicit TLS settings (slice 1 test).
- Whether the hosted instance is a free demo or a paid production setup is
  decided at step 17.
