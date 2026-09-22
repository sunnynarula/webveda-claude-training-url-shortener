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
- **`channel_binding=require` is dropped, and that costs a real protection.**
  Read in asyncpg 0.31.0 while implementing slice 1: `protocol/scram.pyx` sets
  the client's channel-binding flag to `b"n,,"` unconditionally, so asyncpg
  never does channel binding; and in `connect_utils.py`, `ssl="require"`
  without a root certificate file sets `verify_mode = CERT_NONE`. Neon's own
  connection string asks for both TLS *and* channel binding, and channel
  binding is what makes `require` safe against an interceptor when the
  certificate isn't checked. With asyncpg we get neither.
  - Note also that `ssl="verify-full"` as a *string* makes asyncpg look for
    `PGSSLROOTCERT` or `~/.postgresql/root.crt` and raise if neither exists.
    It does not fall back to the system trust store.
  - **Candidate fix, untested:** pass an `ssl.SSLContext` from
    `ssl.create_default_context()` in `connect_args` instead of a mode string,
    which verifies the certificate chain and the hostname against the system
    CA store. To be decided and tested in slice 9, against the real database.
- Whether the hosted instance is a free demo or a paid production setup is
  decided at step 17.
