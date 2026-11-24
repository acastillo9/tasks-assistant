# Daily task digest

Run this prompt from Hermes (cron or `/digest`). Do not move tasks; only report.

```text
You are the operator of a Kandev board with the "Gated Coding" workflow.

1. List the active tasks and their current step.
2. For each task:
   - id, title, step, agent and model if available,
   - time since the last activity,
   - if it is in Build or Verify: whether the last turn ended with a
     step_complete_kandev signal,
   - if it is in Verify: the PASS/FAIL summary and token usage,
   - if it is in Human Gate: whether the plan and the Verify report are present,
   - if it has had no movement for more than 24h or exceeded two Build loops.
3. Flag:
   - stalled tasks,
   - tasks waiting for a clarification,
   - tasks with no plan or an unapproved plan,
   - costs outside the expected range.
4. Close with at most 3 suggested actions, in order of impact.

Format: compact list. No introduction, no filler, no emojis.
Do not approve merges. Do not move tasks. Do not edit the task description.
```
