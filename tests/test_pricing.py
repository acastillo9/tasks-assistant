from __future__ import annotations

from tasks_assistant.pricing import estimate_cost, load_pricing
from tasks_assistant.verify import Usage


def test_loads_rates(tmp_path) -> None:
    path = tmp_path / "pricing.yaml"
    path.write_text(
        "models:\n  deepseek-chat:\n    input_per_mtok: 0.27\n    output_per_mtok: 1.10\n",
        encoding="utf-8",
    )

    pricing = load_pricing(path)
    assert pricing["deepseek-chat"]["input_per_mtok"] == 0.27


def test_missing_file_does_not_fail(tmp_path) -> None:
    assert load_pricing(tmp_path / "does-not-exist.yaml") == {}


def test_estimates_cost() -> None:
    pricing = {"deepseek-chat": {"input_per_mtok": 0.27, "output_per_mtok": 1.10}}
    usage = Usage(prompt_tokens=1_000_000, completion_tokens=1_000_000)
    assert estimate_cost(pricing, "deepseek-chat", usage) == 1.37


def test_model_is_case_insensitive() -> None:
    pricing = {"deepseek-chat": {"input_per_mtok": 1.0, "output_per_mtok": 2.0}}
    usage = Usage(prompt_tokens=1_000_000, completion_tokens=0)
    assert estimate_cost(pricing, "DeepSeek-Chat", usage) == 1.0


def test_model_without_rate_returns_none() -> None:
    usage = Usage(prompt_tokens=10, completion_tokens=20)
    assert estimate_cost({}, "other/model", usage) is None


def test_rounds_to_six_decimals() -> None:
    pricing = {"m": {"input_per_mtok": 0.1, "output_per_mtok": 0.2}}
    usage = Usage(prompt_tokens=1, completion_tokens=1)
    assert estimate_cost(pricing, "m", usage) == 0.0
