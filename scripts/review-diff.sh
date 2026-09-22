#!/usr/bin/env bash
# Write the diff a reviewer reads: .review/slice-N.diff, headed by the commit it
# covers, so every verdict can be tied to exactly that commit.
set -euo pipefail
[ $# -eq 1 ] || { echo "usage: scripts/review-diff.sh <slice-number>" >&2; exit 2; }
root="$(git rev-parse --show-toplevel)"
cd "$root"
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "commit first: reviews must see a commit" >&2; exit 1; }
base=$(git merge-base main HEAD)
out=".review/slice-$1.diff"
mkdir -p .review
{
  echo "HEAD: $(git rev-parse HEAD)"
  echo "BASE: $base"
  echo
  git log --oneline "$base..HEAD"
  echo
  git diff --stat "$base..HEAD"
  echo
  git diff "$base..HEAD"
} > "$out"
echo "$out (HEAD $(git rev-parse --short HEAD))"
