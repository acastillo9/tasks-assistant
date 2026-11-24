# Task contract

A contract is the only trusted input to the flow. A human writes it, not the agent. The builder does not edit it; the verifier uses it as the source of truth.

## Rules

1. **Verifiable criteria.** Every criterion has an id and evidence: `test`, `diff`, `artifact` or `manual`. If it cannot be verified, it is not a criterion.
2. **Exact commands.** Checks are commands that run in the builder's worktree, without LLM intervention. If a command does not exist, the check fails; it is not invented.
3. **Explicit scope.** `paths_allow` and `paths_deny` use globs. Everything else is forbidden.
4. **Closed budget.** `max_attempts` between 1 and 5. Two is the healthy default; three is the ceiling.
5. **Distinct models.** `builder` and `verifier` cannot be the same provider/model pair. The CLI fails if they are.
6. **No secrets.** The contract is committed. No keys, tokens or private paths.

## Flow

```
Intake (human writes the contract)
  → Plan (planner, no code, human approval)
  → Build (cheap builder, worktree)
  → Verify (deterministic checks → verifier with another model)
  → Human Gate (diff + evidence + cost)
  → Done
```

If Verify fails, the human sends the task back to Build. The attempt counter lives in `runs/ledger.jsonl`; when `max_attempts` is exceeded, the task is escalated.

## Minimal structure

```yaml
id: my-task
title: "One sentence"
objective: "What must be achieved."
acceptance:
  - id: A1
    criterion: "The endpoint returns 200 with payload X."
    evidence: test
no_goals:
  - "Do not touch authentication."
scope:
  paths_allow: ["src/**", "tests/**"]
  paths_deny: [".github/**", "uv.lock", "pyproject.toml"]
checks:
  - name: tests
    run: "uv run --project . pytest -q"
    timeout_s: 300
models:
  builder: { provider: deepseek, model: deepseek-chat }
  verifier: { provider: openrouter, model: anthropic/claude-sonnet-4.5 }
budget:
  max_attempts: 2
```

The full schema is in `contracts/task-contract.schema.json`. To create one:

```bash
tasks-assistant init --id my-task --title "One sentence"
```
