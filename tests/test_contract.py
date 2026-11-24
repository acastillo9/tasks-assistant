from __future__ import annotations

import copy
from typing import Any

import pytest

from tasks_assistant.contract import (
    ContractError,
    contract_as_yaml,
    load_contract,
    parse_contract,
)


def base_contract() -> dict[str, Any]:
    return {
        "id": "task-1",
        "title": "T",
        "objective": "O",
        "acceptance": [{"id": "A1", "criterion": "c", "evidence": "test"}],
        "no_goals": [],
        "scope": {"paths_allow": ["src/**"], "paths_deny": []},
        "checks": [{"name": "tests", "run": "python3 -m pytest"}],
        "models": {
            "builder": {"provider": "deepseek", "model": "deepseek-chat"},
            "verifier": {"provider": "openrouter", "model": "anthropic/claude-sonnet-4.5"},
        },
        "budget": {"max_attempts": 2},
    }


def test_loads_example_contract(example_contract_path) -> None:
    contract = load_contract(example_contract_path)
    assert contract["id"] == "demo-greet"
    assert len(contract["acceptance"]) == 2
    assert contract["checks"][0]["run"] == "uv run --project . pytest -q"


def test_rejects_duplicate_acceptance_ids() -> None:
    raw = base_contract()
    raw["acceptance"].append({"id": "A1", "criterion": "d", "evidence": "test"})

    with pytest.raises(ContractError, match='duplicate "A1"'):
        parse_contract(raw)


def test_rejects_identical_builder_and_verifier() -> None:
    raw = base_contract()
    raw["models"]["verifier"] = {"provider": "deepseek", "model": "deepseek-chat"}

    with pytest.raises(ContractError, match="same provider and model"):
        parse_contract(raw)


def test_requires_test_commands() -> None:
    raw = base_contract()
    raw["checks"] = []

    with pytest.raises(ContractError, match="at least one deterministic command"):
        parse_contract(raw)


def test_rejects_bool_as_max_attempts() -> None:
    raw = base_contract()
    raw["budget"]["max_attempts"] = True

    with pytest.raises(ContractError, match="integer between 1 and 5"):
        parse_contract(raw)


def test_rejects_bool_as_timeout() -> None:
    raw = base_contract()
    raw["checks"][0]["timeout_s"] = True

    with pytest.raises(ContractError, match="timeout_s: positive number"):
        parse_contract(raw)


def test_preserves_unknown_fields() -> None:
    raw = base_contract()
    raw["custom_field"] = {"hello": "world"}
    raw["notes"] = "human note"

    contract = parse_contract(raw)
    yaml_text = contract_as_yaml(contract)
    assert "custom_field:" in yaml_text
    assert "notes: human note" in yaml_text


def test_yaml_preserves_utf8() -> None:
    raw = base_contract()
    raw["title"] = "Greeting for Andrés"
    raw["acceptance"][0]["criterion"] = "greet('Andrés') returns 'Hello, Andrés!'"

    yaml_text = contract_as_yaml(parse_contract(raw))
    assert "Andrés" in yaml_text


def test_rejects_invalid_status() -> None:
    raw = base_contract()
    raw["status"] = "invented"

    with pytest.raises(ContractError, match="status: draft"):
        parse_contract(raw)


def test_rejects_missing_scope() -> None:
    raw = base_contract()
    del raw["scope"]

    with pytest.raises(ContractError, match="scope: required"):
        parse_contract(raw)


def test_rejects_invalid_id() -> None:
    raw = base_contract()
    raw["id"] = "Task_1"

    with pytest.raises(ContractError, match="id: required"):
        parse_contract(raw)


def test_does_not_mutate_original_document() -> None:
    raw = base_contract()
    before = copy.deepcopy(raw)
    parse_contract(raw)
    assert raw == before
