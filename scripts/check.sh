#!/usr/bin/env bash
# The one gate: the laptop, the testing-agent, CI and (from step 13) the
# pre-push hook all run this, so "it passed" means the same thing everywhere.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$root/.review"
cd "$root/backend"

echo "== dependencies (uv sync --locked)"
uv sync --locked --quiet

echo "== lint (ruff check)"
uv run ruff check .

echo "== format (ruff format --check)"
uv run ruff format --check .

echo "== types (mypy --strict)"
uv run mypy

if [ -d alembic ]; then
  echo "== migrations (alembic upgrade head)"
  uv run alembic upgrade head
fi

echo "== tests (pytest, branch coverage >= 90%)"
uv run pytest --cov --cov-report=term-missing:skip-covered --cov-fail-under=90 \
  --junitxml="$root/.review/pytest.xml"

echo "== suppression ratchet"
uv run python "$root/scripts/ratchet.py"

echo "== licences: runtime dependencies must be permissive"
runtime=$(uv export --no-dev --no-hashes --no-header --no-emit-project --format requirements.txt \
  | grep -E '^[A-Za-z0-9]' | sed -E 's/[=<>!~; ].*//' | tr '\n' ' ')
# shellcheck disable=SC2086
uv run pip-licenses --from=mixed --partial-match --packages $runtime \
  --allow-only="MIT;BSD;Apache;PSF;ISC"

echo "== licences: development tools may also be MPL-2.0"
uv run pip-licenses --from=mixed --partial-match \
  --allow-only="MIT;BSD;Apache;PSF;ISC;Mozilla Public License 2.0;MPL-2.0" > /dev/null

echo "check.sh: all gates passed"
