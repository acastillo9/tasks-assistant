from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import yaml

from tasks_assistant.cli import main, read_diff
from tasks_assistant.ledger import read_ledger


def test_init_creates_contract(root: Path, tmp_path: Path, capsys) -> None:
    code = main(
        [
            "init",
            "--id",
            "my-task",
            "--title",
            "One sentence",
            "--out",
            str(tmp_path),
        ]
    )

    created = tmp_path / "my-task.yaml"
    assert code == 0
    assert created.exists()
    assert "uv run --project . pytest -q" in created.read_text(encoding="utf-8")
    assert "Contract created" in capsys.readouterr().out


def test_init_does_not_overwrite(tmp_path: Path, capsys) -> None:
    args = ["init", "--id", "my-task", "--title", "One sentence", "--out", str(tmp_path)]
    assert main(args) == 0
    capsys.readouterr()

    assert main(args) == 2
    assert "already exists" in capsys.readouterr().err


def test_init_rejects_invalid_id(tmp_path: Path, capsys) -> None:
    code = main(["init", "--id", "Task_1", "--title", "One sentence", "--out", str(tmp_path)])

    assert code == 2
    assert "--id must use" in capsys.readouterr().err


def test_help_without_command(capsys) -> None:
    assert main(["--help"]) == 0
    assert "usage:" in capsys.readouterr().out

    assert main([]) == 0
    assert "usage:" in capsys.readouterr().out

    assert main(["help"]) == 0
    assert "usage:" in capsys.readouterr().out


def test_python_module_works() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tasks_assistant", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "usage:" in result.stdout


def test_check_end_to_end(
    root: Path,
    example_contract_path: Path,
    demo_repo: Path,
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    state = tmp_path / "state"
    monkeypatch.setenv("TASKS_ASSISTANT_HOME", str(root))
    monkeypatch.setenv("TASKS_ASSISTANT_STATE_DIR", str(state))

    code = main(
        [
            "check",
            "--contract",
            str(example_contract_path),
            "--repo",
            str(demo_repo),
            "--attempt",
            "1",
        ]
    )

    assert code == 0
    assert (state / "demo-greet" / "attempt-1" / "checks.json").exists()
    assert "Result: PASS" in capsys.readouterr().out


def test_failed_check_writes_error_ledger(
    root: Path,
    example_contract_path: Path,
    demo_repo: Path,
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    state = tmp_path / "state"
    monkeypatch.setenv("TASKS_ASSISTANT_HOME", str(root))
    monkeypatch.setenv("TASKS_ASSISTANT_STATE_DIR", str(state))

    contract = yaml.safe_load(example_contract_path.read_text(encoding="utf-8"))
    contract["checks"] = [{"name": "fails", "run": "sh -c 'exit 3'", "timeout_s": 10}]
    failing_path = tmp_path / "failing.yaml"
    failing_path.write_text(
        yaml.safe_dump(contract, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    code = main(
        [
            "check",
            "--contract",
            str(failing_path),
            "--repo",
            str(demo_repo),
            "--attempt",
            "1",
        ]
    )

    assert code == 1
    entries = read_ledger(state / "ledger.jsonl")
    assert len(entries) == 1
    assert entries[0]["verdict"] == "ERROR"
    assert entries[0]["checks_passed"] is False
    assert "Result: FAIL" in capsys.readouterr().out


def test_verify_without_checks_fails(
    root: Path,
    example_contract_path: Path,
    demo_repo: Path,
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("TASKS_ASSISTANT_HOME", str(root))
    monkeypatch.setenv("TASKS_ASSISTANT_STATE_DIR", str(tmp_path / "state"))

    code = main(
        [
            "verify",
            "--contract",
            str(example_contract_path),
            "--repo",
            str(demo_repo),
            "--diff",
            str(root / "examples" / "demo.diff"),
            "--attempt",
            "1",
        ]
    )

    assert code == 2
    assert "no check evidence" in capsys.readouterr().err


def test_verify_does_not_invoke_verifier_if_layer_1_failed(
    root: Path,
    example_contract_path: Path,
    demo_repo: Path,
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    state = tmp_path / "state"
    checks_dir = state / "demo-greet" / "attempt-1"
    checks_dir.mkdir(parents=True)
    (checks_dir / "checks.json").write_text(
        json.dumps(
            {
                "taskId": "demo-greet",
                "attempt": 1,
                "startedAt": "",
                "finishedAt": "",
                "repo": str(demo_repo),
                "allPassed": False,
                "results": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TASKS_ASSISTANT_HOME", str(root))
    monkeypatch.setenv("TASKS_ASSISTANT_STATE_DIR", str(state))

    code = main(
        [
            "verify",
            "--contract",
            str(example_contract_path),
            "--repo",
            str(demo_repo),
            "--diff",
            str(root / "examples" / "demo.diff"),
            "--attempt",
            "1",
        ]
    )

    assert code == 1
    assert "layer 1 failed" in capsys.readouterr().err


def test_verify_dry_run_and_save_prompt(
    root: Path,
    example_contract_path: Path,
    demo_repo: Path,
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    state = tmp_path / "state"
    monkeypatch.setenv("TASKS_ASSISTANT_HOME", str(root))
    monkeypatch.setenv("TASKS_ASSISTANT_STATE_DIR", str(state))

    assert (
        main(
            [
                "check",
                "--contract",
                str(example_contract_path),
                "--repo",
                str(demo_repo),
                "--attempt",
                "1",
            ]
        )
        == 0
    )
    capsys.readouterr()

    code = main(
        [
            "verify",
            "--contract",
            str(example_contract_path),
            "--repo",
            str(demo_repo),
            "--diff",
            str(root / "examples" / "demo.diff"),
            "--attempt",
            "1",
            "--dry-run",
            "--save-prompt",
        ]
    )

    assert code == 0
    output = capsys.readouterr().out
    assert "Dry run" in output
    assert "Builder: deepseek/deepseek-chat" in output
    assert (state / "demo-greet" / "attempt-1" / "verifier-prompt.md").exists()


def test_verify_diff_from_stdin(
    root: Path,
    example_contract_path: Path,
    demo_repo: Path,
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    state = tmp_path / "state"
    monkeypatch.setenv("TASKS_ASSISTANT_HOME", str(root))
    monkeypatch.setenv("TASKS_ASSISTANT_STATE_DIR", str(state))

    assert (
        main(
            [
                "check",
                "--contract",
                str(example_contract_path),
                "--repo",
                str(demo_repo),
                "--attempt",
                "1",
            ]
        )
        == 0
    )
    capsys.readouterr()
    monkeypatch.setattr(sys, "stdin", io.StringIO("+ diff from stdin\n"))

    code = main(
        [
            "verify",
            "--contract",
            str(example_contract_path),
            "--repo",
            str(demo_repo),
            "--diff",
            "-",
            "--attempt",
            "1",
            "--dry-run",
        ]
    )

    assert code == 0
    assert "Dry run" in capsys.readouterr().out


def test_verify_real_with_mocked_verifier(
    root: Path,
    example_contract_path: Path,
    demo_repo: Path,
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    state = tmp_path / "state"
    monkeypatch.setenv("TASKS_ASSISTANT_HOME", str(root))
    monkeypatch.setenv("TASKS_ASSISTANT_STATE_DIR", str(state))
    monkeypatch.setenv("VERIFIER_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("VERIFIER_API_KEY", "test-key")

    assert (
        main(
            [
                "check",
                "--contract",
                str(example_contract_path),
                "--repo",
                str(demo_repo),
                "--attempt",
                "1",
            ]
        )
        == 0
    )
    capsys.readouterr()

    def fake_call_verifier(**kwargs):
        return {
            "verdict": {
                "verdict": "PASS",
                "summary": "Meets the contract.",
                "criteria": [
                    {"id": "A1", "status": "PASS", "evidence": "tests/test_greet.py:6"},
                    {"id": "A2", "status": "PASS", "evidence": "tests/test_greet.py:11"},
                ],
                "findings": [],
                "protected_files_changed": False,
                "tests_weakened": False,
            },
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "rawContent": "{}",
            "latencyMs": 5,
        }

    monkeypatch.setattr("tasks_assistant.cli.call_verifier", fake_call_verifier)

    code = main(
        [
            "verify",
            "--contract",
            str(example_contract_path),
            "--repo",
            str(demo_repo),
            "--diff",
            str(root / "examples" / "demo.diff"),
            "--attempt",
            "1",
        ]
    )

    assert code == 0
    output = capsys.readouterr().out
    assert "VERDICT: PASS" in output
    assert (state / "demo-greet" / "attempt-1" / "verdict.json").exists()
    entries = read_ledger(state / "ledger.jsonl")
    assert len(entries) == 1
    assert entries[0]["verdict"] == "PASS"
    assert entries[0]["checks_passed"] is True


def test_verify_without_credentials(
    root: Path,
    example_contract_path: Path,
    demo_repo: Path,
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    state = tmp_path / "state"
    monkeypatch.setenv("TASKS_ASSISTANT_HOME", str(root))
    monkeypatch.setenv("TASKS_ASSISTANT_STATE_DIR", str(state))
    monkeypatch.delenv("VERIFIER_BASE_URL", raising=False)
    monkeypatch.delenv("VERIFIER_API_KEY", raising=False)

    assert (
        main(
            [
                "check",
                "--contract",
                str(example_contract_path),
                "--repo",
                str(demo_repo),
                "--attempt",
                "1",
            ]
        )
        == 0
    )
    capsys.readouterr()

    code = main(
        [
            "verify",
            "--contract",
            str(example_contract_path),
            "--repo",
            str(demo_repo),
            "--diff",
            str(root / "examples" / "demo.diff"),
            "--attempt",
            "1",
        ]
    )

    assert code == 2
    assert "missing VERIFIER_BASE_URL" in capsys.readouterr().err


def test_attempt_exceeds_budget(
    root: Path,
    example_contract_path: Path,
    demo_repo: Path,
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("TASKS_ASSISTANT_HOME", str(root))
    monkeypatch.setenv("TASKS_ASSISTANT_STATE_DIR", str(tmp_path / "state"))

    code = main(
        [
            "check",
            "--contract",
            str(example_contract_path),
            "--repo",
            str(demo_repo),
            "--attempt",
            "3",
        ]
    )

    assert code == 2
    assert "exceeds budget.max_attempts" in capsys.readouterr().err


def test_attempt_invalid(capsys) -> None:
    code = main(
        [
            "check",
            "--contract",
            "any.yaml",
            "--attempt",
            "0",
        ]
    )
    assert code == 2
    assert "positive integer" in capsys.readouterr().err


def test_read_diff_base_includes_tracked_and_warns_untracked(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "a.txt").write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)

    (repo / "a.txt").write_text("two\n", encoding="utf-8")
    (repo / "new.txt").write_text("new\n", encoding="utf-8")

    diff = read_diff(None, "HEAD", repo)

    assert "+two" in diff
    assert "Untracked files" in diff
    assert "new.txt" in diff


def test_report_json(baseline: Path, capsys) -> None:
    code = main(["report", "--ledger", str(baseline / "ledger.jsonl"), "--json"])

    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data["entries"]) == 3
    assert {summary["task_id"] for summary in data["summary"]} == {"demo-greet", "other-task"}


def test_report_table(baseline: Path, capsys) -> None:
    code = main(["report", "--ledger", str(baseline / "ledger.jsonl")])

    assert code == 0
    output = capsys.readouterr().out
    assert "TASK" in output
    assert "demo-greet" in output
    assert "no-rate" in output


def test_report_without_records(tmp_path: Path, capsys) -> None:
    code = main(["report", "--ledger", str(tmp_path / "does-not-exist.jsonl")])

    assert code == 0
    assert "No records" in capsys.readouterr().out
