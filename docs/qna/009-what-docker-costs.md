# 009. What Docker really costs on this laptop

**Asked:** 2026-09-22 · **Updated:** 2026-09-22

> What does docker really cost and if you think we can manage I am open to trying it.

## Short answer

Running Postgres and Redis in Docker should use roughly 100–150 MB more RAM
than running them natively, which is about 5–8% of the 1.8 GiB that was free
when measured. It also needs a 63 MB Compose install and a few hundred MB of
disk. The databases themselves cost about the same either way; the extra is
Docker's own helper processes. That's manageable, and it keeps you on the
course's path. The 100–150 MB is an estimate built from a real side-by-side
test with Redis (below).

## Answer

### The measurement (2026-09-22)

Redis was run twice with the same settings: once natively as this user on a
spare port, and once in Docker using `redis:7-alpine`. Memory is RSS, the RAM
a process actually holds, measured the same way on both sides.

| What | Native | Docker |
|---|---|---|
| `redis-server` itself | 7.2 MB | 8.7 MB |
| Helper process per container (`containerd-shim`) | — | 10.5 MB |
| Port forwarding for the published port (two `docker-proxy` processes) | — | 8.4 MB |
| Docker's daemons (`dockerd` and `containerd`) | 33.7 MB. They're idle, but already running because they start at boot. | 112.1 MB after pulling and running one container |

`docker stats` reported only 3.2 MiB for the container. It counts just the
memory charged to the container's own resource group, not shared libraries,
so it isn't comparable with the RSS figures above.

After the test, the container, the image and the native test instance were
all removed. Nothing was left behind.

### What that means for Postgres plus Redis

- **The databases cost about the same either way.** On Linux a container is
  an ordinary process with fences around it, not a virtual machine. Redis
  used 7.2 MB natively and 8.7 MB in Docker.
- **Each container adds about 19 MB:** the helper plus the port forwarding.
  For two containers that's about 38 MB.
- **The daemons grew by about 78 MB once they were used.** This was measured
  just after downloading an image. `dockerd` and `containerd` are written in
  Go, which hands memory back to the system lazily, so their long-run size
  may be lower. That wasn't measured.
- **Estimate:** 100–150 MB more than native. Postgres itself wasn't run in
  Docker, so its share is inferred from the Redis result.
- **Disk:** Compose is a 14 MB download and 63 MB installed. The image
  downloads are `postgres:18-alpine` at 114 MB and `redis:7-alpine` at 15 MB,
  plus more once unpacked. With 18 GB free, disk isn't the constraint.

### Perspective: what's using the memory now

At the same moment, Claude Code's processes held about 1.5 GB, and a Gradle
daemon left running by another project held about 1 GB. Docker's extra
100–150 MB is small next to either. Stopping an idle Gradle daemon
(`./gradlew --stop` in the project that started it) frees far more memory
than skipping Docker would.

### Can we manage it? Yes, with four habits

1. **Use the small Alpine images:** `postgres:18-alpine`, which matches the
   natively installed Postgres 18, and `redis:7-alpine`.
2. **Bind the ports to `127.0.0.1` in the compose file**, so the databases
   aren't reachable from your network.
3. **Run `docker compose down` when you stop working.** The daemons then drop
   back to idle.
4. **Keep the native services stopped while the containers run.** Both want
   ports 5432 and 6379. They're stopped and disabled at boot today.

Native stays available as a fallback. The app only sees connection URLs from
its settings, so switching between the two changes the README's "Run locally"
section, not the code.

### What Docker buys you here

- **You stay on the course's path.** `docker-compose.yml` is in the spec's
  repo layout (§4), and plan steps 7 and 11 use `docker compose` commands.
- **One file pins the versions**, and anyone reading the README can reuse it.
- **One command starts or stops everything.** The official Postgres image
  creates the database and user from environment variables, so there are no
  database accounts to set up on your system.

### To start

Install Compose, which needs your password: `sudo apt install
docker-compose-v2`. Step 7 then writes the compose file.

## Sources

- A script run on 2026-09-22 (kept in the session scratchpad, not in the
  repo). It started native `redis-server` 7.0.15 on port 6390 with no
  persistence, measured it and shut it down. It then pulled
  `redis:7-alpine`, ran it on `127.0.0.1:6391`, measured `redis-server`,
  `containerd-shim`, `docker-proxy`, `dockerd` and `containerd` with
  `ps -o rss`, and removed the container and the image.
- Afterwards, `docker ps -aq` and `docker images -q redis` both returned
  nothing, and nothing answered on port 6390.
- Docker Hub API, `hub.docker.com/v2/repositories/library/<image>/tags/<tag>`:
  compressed linux/amd64 sizes for `postgres:18-alpine`, `postgres:18`,
  `redis:7-alpine` and `redis:7`.
- `apt-cache show docker-compose-v2` (download and installed size);
  `df -h /` (18 GB free); `free -h` (1.8 GiB available);
  `ps -eo rss,comm --sort=-rss` (largest memory users).
- `CLAUDE.md` §4 (`docker-compose.yml`); `ASSIGNMENT.md` §1 (native install
  allowed); `docs/LEARNING-PLAN.md` steps 7 and 11.
- **Not verified:** Postgres's memory inside Docker, the daemons' long-run
  size, and the on-disk size of the Postgres image.

## Related

- [008. The tech stack](008-tech-stack.md) (Compose missing; native Postgres
  and Redis installed)
