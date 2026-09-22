# 0009. Valkey instead of Redis

Status: accepted, 2026-09-22 (`docs/PLAN.md` §6)

## Context

Redis 7.2 and earlier are BSD-licensed. From 7.4, Redis is licensed under
RSALv2 or SSPLv1, and from 8.0 AGPLv3 is a third option (according to
`redis/redis` `LICENSE.txt`). The Docker tag `redis:7` means 7.4, so it's
source-available rather than open source. The project plans to sell
commercial licences, and a stack that needs RSAL, SSPL or AGPL components is a
burden on its commercial licensees.

## Decision

Use **Valkey** (BSD-3-Clause, the Linux Foundation fork of Redis 7.2) locally
and in CI, as the `valkey/valkey:8-alpine` image. The app still speaks the
Redis protocol through `redis.asyncio`, so any Redis-compatible managed service
works in production.

## Consequences

Nothing changes in the code. `REDIS_URL` keeps its name, because it names the
protocol, not the product.
