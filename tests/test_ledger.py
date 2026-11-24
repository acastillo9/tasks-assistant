from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tasks_assistant.ledger import (
    append_ledger,
    next_attempt,
    read_ledger,
    summarize_ledger,
)


def entry(task_id: str, attempt: int, ts: str, verdict: str, cost: float | None) -> dict[str, Any]:
    return {
        "ts": ts,
        "task_id": task_id,
        "attempt": attempt,
        "repo": "/tmp/repo",
        "checks_passed": True,
        "builder": {"provider": "deepseek", "model": "deepseek-chat"},
        "verifier": {"provider": "openrouter", "model": "anthropic/claude-sonnet-4.5"},
        "verdict": verdict,
        "model_verdict": verdict,
        "downgraded": False,
        "downgrade_reasons": [],
        "findings": {"blocker": 0, "major": 0, "minor": 0, "nit": 0},
        "criteria": {"pass": 1, "fail": 0, "not_verified": 0},
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        "cost_usd": cost,
        "latency_ms": 100,
    }


def test_missing_ledger_is_empty(tmp_path) -> None:
    assert read_ledger(tmp_path / "ledger.jsonl") == []


def test_reads_lines_ignoring_empty_ones(tmp_path) -> None:
    path = tmp_path / "ledger.jsonl"
    path.write_text(
        json.dumps(entry("t", 1, "2026-01-01T00:00:00.000Z", "PASS", 0.1)) + "\n\n",
        encoding="utf-8",
    )
    assert len(read_ledger(path)) == 1


def test_invalid_json_reports_line(tmp_path) -> None:
    path = tmp_path / "ledger.jsonl"
    path.write_text("{not json}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="line 1"):
        read_ledger(path)


def test_append_and_next_attempt(tmp_path) -> None:
    path = tmp_path / "nested" / "ledger.jsonl"
    append_ledger(path, entry("t", 1, "2026-01-01T00:00:00.000Z", "PASS", 0.1))
    append_ledger(path, entry("t", 2, "2026-01-02T00:00:00.000Z", "FAIL", None))
    append_ledger(path, entry("other", 1, "2026-01-03T00:00:00.000Z", "ERROR", None))

    assert next_attempt(path, "t") == 3
    assert next_attempt(path, "other") == 2
    assert next_attempt(path, "new") == 1


def test_summary_by_task_and_cost() -> None:
    entries = [
        entry("t", 1, "2026-01-01T00:00:00.000Z", "PASS", 0.1),
        entry("t", 2, "2026-01-02T00:00:00.000Z", "FAIL", None),
        entry("other", 1, "2026-01-03T00:00:00.000Z", "ERROR", 0.2),
    ]
    summaries = summarize_ledger(entries)

    assert [summary["task_id"] for summary in summaries] == ["other", "t"]
    assert summaries[0]["attempts"] == 1
    assert summaries[1]["attempts"] == 2
    assert summaries[1]["last_verdict"] == "FAIL"
    assert summaries[1]["cost_usd"] == 0.1
    assert summaries[1]["unknown_cost_entries"] == 1
    assert summaries[1]["models"] == ["deepseek-chat", "anthropic/claude-sonnet-4.5"]


def test_summary_reads_baseline(baseline: Path) -> None:
    entries = read_ledger(baseline / "ledger.jsonl")
    summaries = summarize_ledger(entries)

    assert len(entries) == 3
    assert summaries[0]["task_id"] == "other-task"
    demo = next(summary for summary in summaries if summary["task_id"] == "demo-greet")
    assert demo["attempts"] == 2
    assert demo["cost_usd"] == 0.0348
