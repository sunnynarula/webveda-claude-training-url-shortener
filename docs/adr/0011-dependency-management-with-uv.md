# 0011. Dependency management with uv

Status: accepted, 2026-09-22 (`docs/PLAN.md` §4)

## Context

The spec lists a `requirements.txt` with no lockfile. Installs would then not
be reproducible: CI could test one set of versions while the deployment
installs another.

## Decision

- Manage the backend with `uv`: dependencies in `backend/pyproject.toml` and
  exact versions in `backend/uv.lock`. Development tools go in a dependency
  group.
- `.python-version` pins Python 3.12.
- `scripts/check.sh` and CI run `uv sync --locked`, which fails if the
  lockfile is out of date.
- The container images in Compose and CI are pinned by digest.

## Consequences

- Upgrades are deliberate commits to `uv.lock`, and Dependabot proposes them.
- `uv` is installed per user (`~/.local/bin/uv`).
