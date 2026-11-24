"""Layer 1: run deterministic checks with timeout and evidence."""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO, TypedDict

from .contract import CheckSpec, TaskContract

MAX_CAPTURE_CHARS = 512_000
TAIL_CHARS = 6_000


class CheckResult(TypedDict):
    name: str
    run: str
    required: bool
    passed: bool
    exitCode: int | None
    signal: str | None
    durationMs: int
    timedOut: bool
    logPath: str
    tail: str


class ChecksSummary(TypedDict):
    taskId: str
    attempt: int
    startedAt: str
    finishedAt: str
    repo: str
    allPassed: bool
    results: list[CheckResult]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:60]


def _append_capped(current: str, chunk: str) -> tuple[str, bool]:
    next_text = current + chunk
    if len(next_text) <= MAX_CAPTURE_CHARS:
        return next_text, False
    return next_text[-MAX_CAPTURE_CHARS:], True


def _read_stream(stream: TextIO, sink: dict[str, str], key: str, truncated: list[bool]) -> None:
    text = ""
    while True:
        chunk = stream.read(8192)
        if not chunk:
            break
        text, was_truncated = _append_capped(text, chunk)
        if was_truncated:
            truncated[0] = True
    sink[key] = text


def _kill_group(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except (ProcessLookupError, OSError):
        try:
            process.kill()
        except (ProcessLookupError, OSError):
            pass


def run_check(spec: CheckSpec, repo: str, log_path: str) -> CheckResult:
    """Run a check and return its result with evidence on disk."""
    timeout_s = spec.get("timeout_s", 600)
    required = spec.get("required") is not False
    started = time.monotonic()

    env = {
        **os.environ,
        "CI": "1",
        "NO_COLOR": "1",
        "FORCE_COLOR": "0",
        "TERM": "dumb",
    }

    log_file = Path(log_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        process = subprocess.Popen(
            spec["run"],
            cwd=repo,
            shell=True,
            start_new_session=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
    except OSError as error:
        message = f"[spawn error] {error}"
        duration_ms = round((time.monotonic() - started) * 1000)
        log_file.write_text(f"$ {spec['run']}\n{message}\n", encoding="utf-8")
        return CheckResult(
            name=spec["name"],
            run=spec["run"],
            required=required,
            passed=False,
            exitCode=None,
            signal=None,
            durationMs=duration_ms,
            timedOut=False,
            logPath=log_path,
            tail=message,
        )

    sink = {"stdout": "", "stderr": ""}
    truncated = [False]
    stdout_thread = threading.Thread(
        target=_read_stream,
        args=(process.stdout, sink, "stdout", truncated),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_read_stream,
        args=(process.stderr, sink, "stderr", truncated),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()

    timed_out = False
    try:
        exit_code = process.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_group(process)
        exit_code = process.wait()

    stdout_thread.join(timeout=5)
    stderr_thread.join(timeout=5)

    duration_ms = round((time.monotonic() - started) * 1000)
    stdout = sink["stdout"]
    stderr = sink["stderr"]

    signal_name = signal.Signals(-exit_code).name if exit_code < 0 else None
    exit_code_value = None if exit_code < 0 else exit_code
    passed = exit_code == 0

    exit_label = str(exit_code_value) if exit_code_value is not None else "signal"
    signal_suffix = f" ({signal_name})" if signal_name else ""
    header = "\n".join(
        [
            f"$ {spec['run']}",
            f"cwd: {repo}",
            f"exit: {exit_label}{signal_suffix}",
            f"duration_ms: {duration_ms}",
            "capture: truncated (tail kept)" if truncated[0] else "capture: complete",
            "",
        ]
    )
    body = f"{header}\n--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}\n"
    log_file.write_text(body, encoding="utf-8")

    combined_tail = f"{stdout}\n{stderr}".strip()
    tail = combined_tail[-TAIL_CHARS:] if len(combined_tail) > TAIL_CHARS else combined_tail

    return CheckResult(
        name=spec["name"],
        run=spec["run"],
        required=required,
        passed=passed,
        exitCode=exit_code_value,
        signal=signal_name,
        durationMs=duration_ms,
        timedOut=timed_out,
        logPath=log_path,
        tail=tail,
    )


def run_checks(
    contract: TaskContract,
    repo: str | Path,
    attempt: int,
    out_dir: str | Path,
) -> ChecksSummary:
    """Run all contract checks in order and write checks.json."""
    repo_path = Path(repo).resolve()
    out_path = Path(out_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    started_at = _utc_now()
    results: list[CheckResult] = []

    for index, spec in enumerate(contract["checks"], start=1):
        log_path = out_path / f"{index:02d}-{_slugify(spec['name'])}.log"
        results.append(run_check(spec, str(repo_path), str(log_path)))

    summary = ChecksSummary(
        taskId=contract["id"],
        attempt=attempt,
        startedAt=started_at,
        finishedAt=_utc_now(),
        repo=str(repo_path),
        allPassed=all(not result["required"] or result["passed"] for result in results),
        results=results,
    )

    (out_path / "checks.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary
