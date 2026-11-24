from __future__ import annotations

import shutil
from pathlib import Path

from tasks_assistant.checks import run_checks
from tasks_assistant.contract import load_contract

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "examples" / "demo-no-repo.yaml"
EXAMPLE = ROOT / "examples" / "no-repo"


def prepare_workspace(tmp_path: Path) -> Path:
    work = tmp_path / "work"
    work.mkdir()
    shutil.copy(EXAMPLE / "check.py", work / "check.py")
    shutil.copy(EXAMPLE / "output.md", work / "output.md")
    return work


def test_check_without_git(tmp_path: Path) -> None:
    work = prepare_workspace(tmp_path)
    contract = load_contract(CONTRACT)

    summary = run_checks(contract, work, 1, tmp_path / "state")

    assert summary["allPassed"] is True
    assert not (work / ".git").exists()


def test_check_without_git_fails_if_content_missing(tmp_path: Path) -> None:
    work = prepare_workspace(tmp_path)
    (work / "output.md").write_text("# Publication checklist\n", encoding="utf-8")
    contract = load_contract(CONTRACT)

    summary = run_checks(contract, work, 1, tmp_path / "state")

    assert summary["allPassed"] is False
    assert summary["results"][0]["exitCode"] == 1
    assert "Missing these lines" in summary["results"][0]["tail"]
