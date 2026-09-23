#!/usr/bin/env python3
"""Confirm a RED run: every test must *fail* (assertion or NotImplementedError),
never *error* (import, collection or fixture failure), pass or skip.

A test that passes before its implementation exists is usually vacuous, and that is
what this check is for. Occasionally one legitimately passes — in slice 1 the skeleton
declared two settings as required fields, so pydantic already refused to build without
them. Such a case is recorded in `.red-expected-passes.json` with a reason, in the same
commit that accepts it, rather than being argued with on every run (issue #16):

    {"tests.test_settings::test_missing_origin_setting": "why this passes already"}

A key with no `[parameters]` covers every parameterisation of that test. A recorded
entry that stops passing is itself a problem: the record is then stale and must go.

Usage: scripts/red-check.py <junit-xml> [expected-passes.json]
"""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

DEFAULT_EXPECTED = Path(__file__).resolve().parent.parent / ".red-expected-passes.json"


def load_expected(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return {str(key): str(reason) for key, reason in loaded.items()}


def reason_for(name: str, expected: dict[str, str]) -> str | None:
    """The recorded reason, matching either the exact id or the id without its
    parameters, so one entry can cover a parameterised test."""
    if name in expected:
        return expected[name]
    return expected.get(name.split("[", 1)[0])


def main(junit_path: str, expected_path: Path) -> int:
    expected = load_expected(expected_path)
    cases = ET.parse(junit_path).getroot().iter("testcase")
    failed, bad, accepted, seen = [], [], [], set()
    for case in cases:
        name = f"{case.get('classname')}::{case.get('name')}"
        kinds = {child.tag for child in case}
        if "error" in kinds:
            bad.append(f"ERROR   {name} (errored instead of failing: fix the test setup)")
        elif "skipped" in kinds:
            bad.append(f"SKIPPED {name}")
        elif "failure" in kinds:
            failed.append(name)
        elif (reason := reason_for(name, expected)) is not None:
            seen.add(name if name in expected else name.split("[", 1)[0])
            accepted.append(f"PASSED  {name} (recorded: {reason})")
        else:
            bad.append(f"PASSED  {name} (passes before the code exists: vacuous?)")

    for key in sorted(set(expected) - seen):
        bad.append(f"STALE   {key} (recorded as an expected pass, but it did not pass)")

    for line in accepted + bad:
        print(line)
    print(
        f"red-check: {len(failed)} failing as expected, "
        f"{len(accepted)} recorded pass(es), {len(bad)} problem(s)"
    )
    return 1 if bad or not failed else 0


if __name__ == "__main__":
    if not 2 <= len(sys.argv) <= 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], Path(sys.argv[2]) if len(sys.argv) == 3 else DEFAULT_EXPECTED))
