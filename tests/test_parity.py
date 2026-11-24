from __future__ import annotations

import json
from pathlib import Path

from tasks_assistant.ledger import read_ledger, summarize_ledger


def test_baseline_checks_json_preserves_schema(baseline: Path) -> None:
    data = json.loads((baseline / "checks.json").read_text(encoding="utf-8"))

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


def test_baseline_verdict_json_preserves_schema(baseline: Path) -> None:
    data = json.loads((baseline / "verdict.json").read_text(encoding="utf-8"))

    assert set(data) == {
        "task_id",
        "attempt",
        "final_verdict",
        "downgraded",
        "downgrade_reasons",
        "builder",
        "verifier",
        "usage",
        "cost_usd",
        "verdict",
    }
    assert set(data["verdict"]) == {
        "verdict",
        "summary",
        "criteria",
        "findings",
        "protected_files_changed",
        "tests_weakened",
    }


def test_baseline_report_matches_ledger(baseline: Path) -> None:
    entries = read_ledger(baseline / "ledger.jsonl")
    expected = json.loads((baseline / "report.json").read_text(encoding="utf-8"))

    assert summarize_ledger(entries) == expected["summary"]


def test_baseline_prompt_preserves_sections(baseline: Path) -> None:
    prompt = (baseline / "verifier-prompt.md").read_text(encoding="utf-8")

    assert "# Role: Independent verifier" in prompt
    assert "## Contract (source of truth, written by a human)" in prompt
    assert "## Deterministic checks (executed by the container, not by an LLM)" in prompt
    assert "## Proposed diff" in prompt
    assert "<untrusted_diff>" in prompt
    assert "## What you must return" in prompt
