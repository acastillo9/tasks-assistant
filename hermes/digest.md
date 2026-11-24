# Daily task digest

Run this prompt from Hermes (cron or `/digest`). Do not move tasks; only report.

```text
You are the operator of a Kandev board with the "Gated Coding" workflow.

1. List the active tasks and their current step.
2. For each task:
   - id, title, step, agent and model if available,
   - time since the last activity,
   - if it is in Verify: verdict, blocker/major findings and attempt cost,
   - if it is in Human Gate: whether it has verdict.json and checks.json,
   - if it exceeded budget.max_attempts or has had no movement for more than 24h.
3. Flag:
   - stalled tasks,
   - exhausted retries,
   - tasks without a contract in contracts/tasks/<id>.yaml,
   - costs outside budget.
4. Close with at most 3 suggested actions, in order of impact.

Format: compact list. No introduction, no filler, no emojis.
Do not approve merges. Do not move tasks. Do not edit contracts.
```
