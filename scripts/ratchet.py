#!/usr/bin/env python3
"""Suppression ratchet: counts of lint/type/coverage/test suppressions may only go
down. Fails if any count rises above .quality-baseline.json. Lower the baseline
in its own reviewed commit when counts fall.
"""

import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
PATTERNS = {
    "noqa": re.compile(r"#\s*noqa"),
    "type_ignore": re.compile(r"#\s*type:\s*ignore"),
    "pragma_no_cover": re.compile(r"pragma:\s*no\s*cover"),
    "skip": re.compile(r"pytest\.mark\.skip|pytest\.skip\("),
    "xfail": re.compile(r"pytest\.mark\.xfail|pytest\.xfail\("),
}


def count() -> dict[str, int]:
    counts = dict.fromkeys(PATTERNS, 0)
    sources = [*BACKEND.rglob("*.py"), *(ROOT / "scripts").glob("*.py")]
    for path in sources:
        if ".venv" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for key, pattern in PATTERNS.items():
            counts[key] += len(pattern.findall(text))
    config = tomllib.loads((BACKEND / "pyproject.toml").read_text(encoding="utf-8"))
    tool = config.get("tool", {})
    ignores = tool.get("ruff", {}).get("lint", {}).get("per-file-ignores", {})
    counts["ruff_per_file_ignores"] = sum(len(rules) for rules in ignores.values())
    counts["coverage_omit"] = len(tool.get("coverage", {}).get("run", {}).get("omit", []))
    return counts


def main() -> int:
    baseline = json.loads((ROOT / ".quality-baseline.json").read_text(encoding="utf-8"))
    current = count()
    risen = {k: (baseline.get(k, 0), v) for k, v in current.items() if v > baseline.get(k, 0)}
    for key, value in sorted(current.items()):
        print(f"  {key:22} {value:3}  (baseline {baseline.get(key, 0)})")
    if risen:
        print("ratchet: suppressions rose: " + ", ".join(f"{k} {a}->{b}" for k, (a, b) in risen.items()))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
