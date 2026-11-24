"""Load and validate the task contract."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict, cast

import yaml

Evidence = Literal["test", "diff", "artifact", "manual"]
Status = Literal["draft", "ready", "running", "blocked", "done"]


class ProviderRef(TypedDict):
    provider: str
    model: str


class AcceptanceCriterion(TypedDict):
    id: str
    criterion: str
    evidence: Evidence


class Scope(TypedDict):
    repos: NotRequired[list[str]]
    paths_allow: list[str]
    paths_deny: list[str]


class CheckSpec(TypedDict):
    name: str
    run: str
    timeout_s: NotRequired[float]
    required: NotRequired[bool]


class Models(TypedDict):
    planner: NotRequired[ProviderRef]
    builder: ProviderRef
    verifier: ProviderRef


class Budget(TypedDict):
    max_attempts: int
    max_minutes: NotRequired[float]
    max_usd: NotRequired[float]


class TaskContract(TypedDict):
    id: str
    title: str
    objective: str
    status: NotRequired[Status]
    acceptance: list[AcceptanceCriterion]
    no_goals: list[str]
    scope: Scope
    checks: list[CheckSpec]
    models: Models
    budget: Budget
    evidence_required: NotRequired[list[str]]
    protected_paths: NotRequired[list[str]]
    notes: NotRequired[str]


class ContractError(Exception):
    """Invalid contract with the full list of issues found."""

    def __init__(self, issues: list[str]) -> None:
        self.issues = issues
        super().__init__("Invalid contract:\n- " + "\n- ".join(issues))


ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
EVIDENCE = {"test", "diff", "artifact", "manual"}
STATUSES = {"draft", "ready", "running", "blocked", "done"}


def _is_record(value: Any) -> bool:
    return isinstance(value, dict)


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _is_string_array(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def parse_contract(raw: Any) -> TaskContract:
    """Validate an already-parsed YAML document and return the contract."""
    issues: list[str] = []

    if not _is_record(raw):
        raise ContractError(["the document must be a YAML object"])

    if not _is_non_empty_string(raw.get("id")) or not ID_RE.fullmatch(raw["id"]):
        issues.append("id: required, lowercase letters, numbers and hyphens (2-64 characters)")
    if not _is_non_empty_string(raw.get("title")):
        issues.append("title: required")
    if not _is_non_empty_string(raw.get("objective")):
        issues.append("objective: required")

    acceptance = raw.get("acceptance")
    if not isinstance(acceptance, list) or len(acceptance) == 0:
        issues.append("acceptance: at least one verifiable criterion")
    else:
        seen: set[str] = set()
        for index, item in enumerate(acceptance):
            if not _is_record(item):
                issues.append(f"acceptance[{index}]: must be an object")
                continue
            item_id = item.get("id")
            if not _is_non_empty_string(item_id):
                issues.append(f"acceptance[{index}].id: required")
            elif item_id in seen:
                issues.append(f'acceptance[{index}].id: duplicate "{item_id}"')
            else:
                seen.add(item_id)
            if not _is_non_empty_string(item.get("criterion")):
                issues.append(f"acceptance[{index}].criterion: required")
            evidence = item.get("evidence")
            if not _is_non_empty_string(evidence) or evidence not in EVIDENCE:
                issues.append(f"acceptance[{index}].evidence: test | diff | artifact | manual")

    if not _is_string_array(raw.get("no_goals")):
        issues.append("no_goals: list of strings (may be empty)")

    scope = raw.get("scope")
    if not _is_record(scope):
        issues.append("scope: required")
    else:
        if "repos" in scope and not _is_string_array(scope["repos"]):
            issues.append("scope.repos: list of strings")
        paths_allow = scope.get("paths_allow")
        if not _is_string_array(paths_allow) or len(paths_allow) == 0:
            issues.append("scope.paths_allow: non-empty list of allowed patterns")
        if not _is_string_array(scope.get("paths_deny")):
            issues.append("scope.paths_deny: list of strings (may be empty)")

    checks = raw.get("checks")
    if not isinstance(checks, list) or len(checks) == 0:
        issues.append("checks: at least one deterministic command")
    else:
        for index, item in enumerate(checks):
            if not _is_record(item):
                issues.append(f"checks[{index}]: must be an object")
                continue
            if not _is_non_empty_string(item.get("name")):
                issues.append(f"checks[{index}].name: required")
            if not _is_non_empty_string(item.get("run")):
                issues.append(f"checks[{index}].run: required")
            if "timeout_s" in item:
                timeout_s = item["timeout_s"]
                if not _is_number(timeout_s) or timeout_s <= 0:
                    issues.append(f"checks[{index}].timeout_s: positive number")
            if "required" in item and not isinstance(item["required"], bool):
                issues.append(f"checks[{index}].required: boolean")

    models = raw.get("models")
    if not _is_record(models):
        issues.append("models: required (planner, builder, verifier)")
    else:
        for role in ("builder", "verifier"):
            ref = models.get(role)
            if not _is_record(ref):
                issues.append(f"models.{role}: required")
                continue
            if not _is_non_empty_string(ref.get("provider")):
                issues.append(f"models.{role}.provider: required")
            if not _is_non_empty_string(ref.get("model")):
                issues.append(f"models.{role}.model: required")
        if "planner" in models:
            planner = models["planner"]
            if (
                not _is_record(planner)
                or not _is_non_empty_string(planner.get("provider"))
                or not _is_non_empty_string(planner.get("model"))
            ):
                issues.append("models.planner: provider and model are required")

    budget = raw.get("budget")
    if not _is_record(budget):
        issues.append("budget: required")
    else:
        max_attempts = budget.get("max_attempts")
        if not _is_integer(max_attempts) or max_attempts < 1 or max_attempts > 5:
            issues.append("budget.max_attempts: integer between 1 and 5")
        if "max_minutes" in budget:
            max_minutes = budget["max_minutes"]
            if not _is_number(max_minutes) or max_minutes <= 0:
                issues.append("budget.max_minutes: positive number")
        if "max_usd" in budget:
            max_usd = budget["max_usd"]
            if not _is_number(max_usd) or max_usd <= 0:
                issues.append("budget.max_usd: positive number")

    if "evidence_required" in raw and not _is_string_array(raw["evidence_required"]):
        issues.append("evidence_required: list of strings")
    if "protected_paths" in raw and not _is_string_array(raw["protected_paths"]):
        issues.append("protected_paths: list of strings")
    if "status" in raw:
        status = raw["status"]
        if not _is_non_empty_string(status) or status not in STATUSES:
            issues.append("status: draft | ready | running | blocked | done")

    if issues:
        raise ContractError(issues)

    contract = cast(TaskContract, raw)
    builder = contract["models"]["builder"]
    verifier = contract["models"]["verifier"]
    if builder["provider"] == verifier["provider"] and builder["model"] == verifier["model"]:
        raise ContractError(
            [
                "models.builder and models.verifier use the same provider and model; "
                "the verifier must be different",
            ]
        )

    return contract


def load_contract(file: str | Path) -> TaskContract:
    """Read a contract from a YAML file."""
    path = Path(file)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ContractError([f"could not read {file}: {error}"]) from error

    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ContractError([f"invalid YAML: {error}"]) from error

    return parse_contract(parsed)


def contract_as_yaml(contract: TaskContract) -> str:
    """Serialize the contract for the verifier prompt."""
    return yaml.safe_dump(
        contract,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=10**9,
    )
