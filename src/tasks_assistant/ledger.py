"""JSONL ledger of attempts and verdicts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, TypedDict

from .contract import ProviderRef
from .verify import Usage


class FindingsCounts(TypedDict):
    blocker: int
    major: int
    minor: int
    nit: int


CriteriaCounts = TypedDict(
    "CriteriaCounts",
    {"pass": int, "fail": int, "not_verified": int},
)


class LedgerEntry(TypedDict):
    ts: str
    task_id: str
    attempt: int
    repo: str
    checks_passed: bool
    builder: ProviderRef
    verifier: ProviderRef
    verdict: Literal["PASS", "FAIL", "ERROR"]
    model_verdict: Literal["PASS", "FAIL", "ERROR"]
    downgraded: bool
    downgrade_reasons: list[str]
    findings: FindingsCounts
    criteria: CriteriaCounts
    usage: Usage
    cost_usd: float | None
    latency_ms: int


class TaskSummary(TypedDict):
    task_id: str
    attempts: int
    last_verdict: Literal["PASS", "FAIL", "ERROR"]
    last_ts: str
    cost_usd: float
    unknown_cost_entries: int
    models: list[str]


def read_ledger(file: str | Path) -> list[LedgerEntry]:
    """Read the ledger; a missing file is equivalent to an empty ledger."""
    path = Path(file)
    if not path.exists():
        return []

    entries: list[LedgerEntry] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").split("\n"), start=1):
        if line.strip() == "":
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid ledger in {file}, line {index}") from error
    return entries


def append_ledger(file: str | Path, entry: LedgerEntry) -> None:
    """Append a JSON line to the ledger, creating the directory if needed."""
    path = Path(file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n")


def next_attempt(file: str | Path, task_id: str) -> int:
    """Next attempt number based on the task's previous entries."""
    previous = [entry for entry in read_ledger(file) if entry["task_id"] == task_id]
    return len(previous) + 1


def summarize_ledger(entries: list[LedgerEntry]) -> list[TaskSummary]:
    """Group by task, sum known costs and sort by latest activity."""
    by_task: dict[str, list[LedgerEntry]] = {}
    for entry in entries:
        by_task.setdefault(entry["task_id"], []).append(entry)

    summaries: list[TaskSummary] = []
    for task_id, task_entries in by_task.items():
        ordered = sorted(task_entries, key=lambda entry: entry["ts"])
        last = ordered[-1]
        known = [entry for entry in ordered if entry["cost_usd"] is not None]
        models: list[str] = []
        for entry in ordered:
            for model in (entry["builder"]["model"], entry["verifier"]["model"]):
                if model not in models:
                    models.append(model)

        summaries.append(
            TaskSummary(
                task_id=task_id,
                attempts=len(ordered),
                last_verdict=last["verdict"],
                last_ts=last["ts"],
                cost_usd=round(sum((entry["cost_usd"] or 0) for entry in known), 6),
                unknown_cost_entries=len(ordered) - len(known),
                models=models,
            )
        )

    summaries.sort(key=lambda summary: summary["last_ts"], reverse=True)
    return summaries
