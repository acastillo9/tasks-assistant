from __future__ import annotations

import json
from copy import deepcopy

from tasks_assistant.checks import run_check, run_checks
from tasks_assistant.contract import TaskContract


def test_runs_contract_checks_and_writes_evidence(
    contract: TaskContract, demo_repo, tmp_path
) -> None:
    summary = run_checks(contract, demo_repo, 1, tmp_path)

    assert summary["allPassed"] is True
    assert summary["results"][0]["passed"] is True
    assert summary["results"][0]["logPath"].endswith("01-tests.log")
    assert (tmp_path / "checks.json").exists()


def test_checks_json_preserves_camel_case_keys(
    contract: TaskContract, demo_repo, tmp_path
) -> None:
    run_checks(contract, demo_repo, 1, tmp_path)
    data = json.loads((tmp_path / "checks.json").read_text(encoding="utf-8"))

    assert set(data) == {
        "taskId",
        "attempt",
        "startedAt",
        "finishedAt",
        "repo",
        "allPassed",
        "results",
    }
    assert set(data["results"][0]) == {
        "name",
        "run",
        "required",
        "passed",
        "exitCode",
        "signal",
        "durationMs",
        "timedOut",
        "logPath",
        "tail",
    }


def test_failing_check_marks_layer_1_as_fail(
    contract: TaskContract, demo_repo, tmp_path
) -> None:
    failing = deepcopy(contract)
    failing["checks"] = [{"name": "fails", "run": "sh -c 'exit 3'", "timeout_s": 10}]

    summary = run_checks(failing, demo_repo, 1, tmp_path)

    assert summary["allPassed"] is False
    assert summary["results"][0]["exitCode"] == 3
    assert summary["results"][0]["passed"] is False


def test_advisory_check_that_fails_does_not_break_all_passed(
    contract: TaskContract, demo_repo, tmp_path
) -> None:
    advisory = deepcopy(contract)
    advisory["checks"] = [
        {"name": "advisory", "run": "sh -c 'exit 7'", "timeout_s": 10, "required": False}
    ]

    summary = run_checks(advisory, demo_repo, 1, tmp_path)

    assert summary["allPassed"] is True
    assert summary["results"][0]["passed"] is False
    assert summary["results"][0]["required"] is False


def test_timeout_kills_process_group(contract: TaskContract, demo_repo, tmp_path) -> None:
    timing_out = deepcopy(contract)
    timing_out["checks"] = [{"name": "timeout", "run": "sleep 5", "timeout_s": 1}]

    summary = run_checks(timing_out, demo_repo, 1, tmp_path)
    result = summary["results"][0]

    assert result["timedOut"] is True
    assert result["exitCode"] is None
    assert result["signal"] == "SIGKILL"
    assert result["passed"] is False


def test_maps_signals(contract: TaskContract, demo_repo, tmp_path) -> None:
    signalled = deepcopy(contract)
    signalled["checks"] = [{"name": "signal", "run": "kill -TERM $$", "timeout_s": 10}]

    summary = run_checks(signalled, demo_repo, 1, tmp_path)
    result = summary["results"][0]

    assert result["exitCode"] is None
    assert result["signal"] == "SIGTERM"
    assert result["passed"] is False


def test_truncates_capture_and_keeps_tail(contract: TaskContract, demo_repo, tmp_path) -> None:
    huge = deepcopy(contract)
    huge["checks"] = [
        {
            "name": "huge",
            "run": "python3 -c 'import sys; sys.stdout.write(\"x\" * 600000)'",
            "timeout_s": 30,
        }
    ]

    summary = run_checks(huge, demo_repo, 1, tmp_path)
    result = summary["results"][0]
    log = (tmp_path / "01-huge.log").read_text(encoding="utf-8")

    assert "capture: truncated (tail kept)" in log
    assert len(result["tail"]) == 6000
    assert result["tail"] == "x" * 6000


def test_spawn_error_writes_log(contract: TaskContract, demo_repo, tmp_path) -> None:
    missing = deepcopy(contract)
    missing["checks"] = [{"name": "missing", "run": "command-that-does-not-exist-12345"}]

    summary = run_checks(missing, demo_repo, 1, tmp_path)
    result = summary["results"][0]

    assert result["passed"] is False
    assert result["exitCode"] == 127
    assert "not found" in result["tail"].lower()


def test_run_check_direct_writes_log(contract: TaskContract, demo_repo, tmp_path) -> None:
    log_path = tmp_path / "check.log"
    result = run_check(contract["checks"][0], str(demo_repo), str(log_path))

    assert result["passed"] is True
    assert log_path.exists()
    assert log_path.read_text(encoding="utf-8").startswith("$ uv run --project . pytest -q")
