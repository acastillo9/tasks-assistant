from __future__ import annotations

from pathlib import Path

import pytest

from tasks_assistant.contract import TaskContract, load_contract

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_CONTRACT = ROOT / "contracts" / "examples" / "demo-greet.yaml"
DEMO_REPO = ROOT / "examples" / "demo-repo"
BASELINE = ROOT / "tests" / "baseline"


@pytest.fixture
def root() -> Path:
    return ROOT


@pytest.fixture
def example_contract_path() -> Path:
    return EXAMPLE_CONTRACT


@pytest.fixture
def demo_repo() -> Path:
    return DEMO_REPO


@pytest.fixture
def contract() -> TaskContract:
    return load_contract(EXAMPLE_CONTRACT)


@pytest.fixture
def baseline() -> Path:
    return BASELINE
