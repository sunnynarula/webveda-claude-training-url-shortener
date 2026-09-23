"""`scripts/red-check.py` is a gate, so it gets tests of its own (issue #16).

It runs as a script rather than being imported, so these drive it the way the loop
does: a JUnit report in, an exit code and a report out.
"""

import json
import subprocess
import sys
from pathlib import Path

RED_CHECK = Path(__file__).resolve().parents[3] / "scripts" / "red-check.py"

TEST_ID = "tests.test_settings::test_missing_origin_setting_is_a_settings_error"


def junit(cases: dict[str, str]) -> str:
    """A JUnit report. Each case maps a test id to `failure`, `error`, `skipped` or
    `passed`."""
    body = []
    for name, outcome in cases.items():
        classname, _, case = name.partition("::")
        inner = "" if outcome == "passed" else f"<{outcome} message='x'/>"
        body.append(f'<testcase classname="{classname}" name="{case}">{inner}</testcase>')
    return f"<testsuites><testsuite>{''.join(body)}</testsuite></testsuites>"


def run(
    tmp_path: Path, cases: dict[str, str], expected: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    report = tmp_path / "red.xml"
    report.write_text(junit(cases), encoding="utf-8")
    recorded = tmp_path / "expected.json"
    recorded.write_text(json.dumps(expected), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(RED_CHECK), str(report), str(recorded)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_run_where_everything_fails_is_a_good_red_run(tmp_path: Path) -> None:
    result = run(tmp_path, {"m::test_a": "failure", "m::test_b": "failure"}, {})

    assert result.returncode == 0, result.stdout
    assert "2 failing as expected" in result.stdout


def test_an_unrecorded_pass_is_still_reported(tmp_path: Path) -> None:
    """The check's whole point: a test that passes before the code exists is usually
    vacuous, and silence about it would be worse than a false alarm."""
    result = run(tmp_path, {"m::test_a": "failure", "m::test_b": "passed"}, {})

    assert result.returncode == 1
    assert "vacuous?" in result.stdout


def test_a_recorded_pass_is_accepted_with_its_reason(tmp_path: Path) -> None:
    """Issue #16: slice 1's RED run reported two problems that were legitimate, and the
    developer had to overrule the gate from memory."""
    result = run(
        tmp_path,
        {"m::test_a": "failure", f"{TEST_ID}[public_base_url]": "passed"},
        {TEST_ID: "the skeleton already declares the field required"},
    )

    assert result.returncode == 0, result.stdout
    assert "recorded: the skeleton already declares the field required" in result.stdout
    assert "1 recorded pass(es)" in result.stdout


def test_a_record_that_no_longer_applies_is_a_problem(tmp_path: Path) -> None:
    """The record is self-cleaning: once the test starts failing like the others, the
    entry is stale and has to go, or it would excuse a future pass nobody looked at."""
    result = run(tmp_path, {"m::test_a": "failure"}, {"m::test_a": "recorded long ago"})

    assert result.returncode == 1
    assert "STALE" in result.stdout


def test_a_test_that_errors_is_never_excused(tmp_path: Path) -> None:
    """An error means the test could not run. Recording it would hide a broken suite."""
    result = run(
        tmp_path,
        {"m::test_a": "failure", "m::test_b": "error"},
        {"m::test_b": "trying to excuse an error"},
    )

    assert result.returncode == 1
    assert "ERROR" in result.stdout
