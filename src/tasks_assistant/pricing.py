"""Verifier rates and cost estimation."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import yaml

from .verify import Usage


class Price(TypedDict):
    input_per_mtok: float
    output_per_mtok: float


def load_pricing(file: str | Path) -> dict[str, Price]:
    """Load ``models`` from pricing.yaml; if it does not exist, there are no rates."""
    path = Path(file)
    if not path.exists():
        return {}

    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        return {}
    models = parsed.get("models")
    return models if isinstance(models, dict) else {}


def estimate_cost(pricing: dict[str, Price], model: str, usage: Usage) -> float | None:
    """Return the estimated USD cost, or ``None`` if the model has no rate."""
    price = pricing.get(model) or pricing.get(model.lower())
    if not price:
        return None

    input_cost = (usage["prompt_tokens"] / 1_000_000) * price["input_per_mtok"]
    output_cost = (usage["completion_tokens"] / 1_000_000) * price["output_per_mtok"]
    return round(input_cost + output_cost, 6)
