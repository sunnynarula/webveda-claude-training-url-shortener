#!/usr/bin/env python3
"""Confirm a RED run: every test must *fail* (assertion or NotImplementedError),
never *error* (import, collection or fixture failure), pass or skip.

Usage: scripts/red-check.py <junit-xml>
"""

import sys
import xml.etree.ElementTree as ET


def main(path: str) -> int:
    cases = ET.parse(path).getroot().iter("testcase")
    failed, bad = [], []
    for case in cases:
        name = f"{case.get('classname')}::{case.get('name')}"
        kinds = {child.tag for child in case}
        if "error" in kinds:
            bad.append(f"ERROR   {name} (errored instead of failing: fix the test setup)")
        elif "skipped" in kinds:
            bad.append(f"SKIPPED {name}")
        elif "failure" in kinds:
            failed.append(name)
        else:
            bad.append(f"PASSED  {name} (passes before the code exists: vacuous?)")
    for line in bad:
        print(line)
    print(f"red-check: {len(failed)} failing as expected, {len(bad)} problem(s)")
    return 1 if bad or not failed else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
