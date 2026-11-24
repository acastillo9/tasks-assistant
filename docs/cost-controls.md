# Cost controls

Goal: pay for the VPS + tokens, nothing else. Spending is controlled at four layers: policy, contract, runtime and provider.

## Where each control applies

| Control | Where it lives | Automatic? |
|---|---|---|
| Maximum attempts | `budget.max_attempts` + `tasks-assistant verify` | Yes: the CLI rejects attempt N+1 |
| Per-task budget | `budget.max_usd` | Partial: it stays in the contract and ledger; the cutoff is human |
| Concurrency 1–2 | Kandev / executor | Manual configuration |
| Tests before the verifier | `tasks-assistant verify` | Yes: fails if layer 1 did not pass |
| Minimal context | `MAX_DIFF_BYTES` (200 KB) | Yes: fails instead of truncating |
| Cheap model by default | `Build` step profile | Manual configuration |
| Escalate to an expensive model | `Plan` profile or retry | Human |
| Per-key spending cap | Provider panel | External |
| Prompt caching | Provider | Provider configuration |
| Cost ledger | `runs/ledger.jsonl` | Yes, per verifier |

## Contract budget

```yaml
budget:
  max_attempts: 2      # 1–5; the CLI blocks excess
  max_minutes: 30      # operational target
  max_usd: 1           # human review threshold
```

`max_minutes` and `max_usd` do not cut a run by themselves: they are the contract the Human Gate reviews. If you want a hard cutoff, configure the limit at the provider and in the executor (CPU/RAM/time).

## Ledger

Each verification appends a line:

```json
{
  "task_id": "my-task",
  "attempt": 1,
  "builder": { "provider": "deepseek", "model": "deepseek-chat" },
  "verifier": { "provider": "openrouter", "model": "anthropic/claude-sonnet-4.5" },
  "verdict": "FAIL",
  "usage": { "prompt_tokens": 4200, "completion_tokens": 380 },
  "cost_usd": 0.0183,
  "latency_ms": 12000
}
```

Cost is calculated only if the model is in `config/pricing.yaml`. If it is missing, `cost_usd` is `null` and `tasks-assistant report` marks it as `no-rate`. Keep rates up to date; the ledger is an estimate, not the invoice.

This ledger does **not** capture the builder's cost: Kandev shows tokens per session. Cross-check both at the Human Gate.

## Operating rules

1. Economy builder by default. The expensive model only plans or unblocks.
2. At most 2 attempts; the third is paid by a human with their time.
3. Checks first. An LLM verifier over broken tests is money thrown away.
4. Diff + criteria + test output, not the whole repo.
5. Do not retry the same prompt expecting a different result. Change the plan or escalate.
6. One task = one objective. If the diff does not fit in 200 KB, the task was split badly.

## Estimating a task

```
cost ≈ (plan_tokens × planner_price)
      + (build_tokens × builder_price)
      + (verify_tokens × verifier_price)
      + retries × (build + verify)
```

With a builder at ~$0.30/M input tokens and a verifier at ~$3/M, the verifier usually costs more per call even though it consumes fewer tokens. That is why it only runs after the checks.

---

*— Andi · 2026-11-22*
