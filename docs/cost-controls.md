# Cost controls

Goal: pay for the VPS + tokens, nothing else. With the CLI gone, spending is
controlled by model choice, provider caps, concurrency and the Human Gate.

## Where each control applies

| Control | Where it lives | Automatic? |
|---|---|---|
| Cheap model by default | `Builder` profile | Manual configuration |
| Expensive model only for Plan | `Planner` profile | Manual configuration |
| Independent review | `Verifier` profile | Manual configuration |
| Concurrency 1–2 | Kandev / executor | Manual configuration |
| Per-key spending cap | Provider panel | External |
| Context size | Task description, plan and diff in Kandev | Human |
| Attempt limit | Human Gate convention (max 2 loops) | No |
| Token usage | Kandev session stats | Yes, per session |

There is no cumulative ledger. Kandev shows tokens per session; cross-check
Plan, Build and Verify at the Human Gate.

## Profiles

| Role | Model | Why |
|---|---|---|
| `Planner` | Frontier (high-tier) | Few calls, decides the plan |
| `Builder` | Economy (DeepSeek/Kimi/Qwen/GLM) | Consumes most tokens |
| `Verifier` | Another provider/model | Independent bias, read-only |

Do not put the verifier on the same provider/model as the builder. Kandev does
not enforce this; the profile assignment is the control.

## Operating rules

1. Economy builder by default. The expensive model only plans or unblocks.
2. At most two Build loops. The third is a human decision.
3. Tests first. A verifier review over broken tests is money thrown away.
4. Give the verifier the diff, the acceptance checklist and the test output, not
   the whole repository.
5. Do not retry the same prompt expecting a different result. Change the plan or
   escalate.
6. One task = one objective. If the diff is huge, the task was split badly.
7. Set provider spending caps; the Human Gate is not a hard budget cutoff.

## Estimating a task

```text
cost ≈ (plan_tokens × planner_price)
      + (build_tokens × builder_price)
      + (verify_tokens × verifier_price)
      + retries × (build + verify)
```

With a builder at ~$0.30/M input tokens and a verifier at ~$3/M, the verifier
usually costs more per call even though it consumes fewer tokens. That is why it
runs only after Build and why the Human Gate checks token usage.

---

*— Andi · 2026-11-24*
