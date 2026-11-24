# Hermes ↔ Kandev

Hermes is the operator: it receives messages, creates tasks, queries status and sends digests. It does not replace the human gate.

## MCP

Kandev exposes Streamable HTTP at `http://127.0.0.1:38429/mcp` (`/mcp/sse` for legacy clients). In `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  kandev:
    url: "http://127.0.0.1:38429/mcp"
    # If you enable auth in Kandev, add the PAT:
    # headers:
    #   Authorization: "Bearer ${KANDEV_MCP_TOKEN}"
    timeout: 30
```

If Hermes runs in another container/host, use the private IP or a tunnel; never expose `/mcp` to the internet.

## Useful tools

- `create_task_kandev` — creates the task; title ≤ 60 characters, context in `description`, explicit repo.
- `list_tasks_kandev` / `get_task_kandev` — status and conversation.
- `move_task_kandev` — move between steps (for example, approve the plan).
- `update_task_kandev` — priority and fields without changing state.
- `list_workflows_kandev` / `list_workflow_steps_kandev` — discover the `Gated Coding` workflow.

A task created by Hermes enters `Intake`. A human writes the contract; Hermes may draft one in `description`, but not the contract itself.

## Telegram flows

| Message | Action |
|---|---|
| `new task <project>: <objective>` | `create_task_kandev` in Intake, medium priority |
| `status` | List active tasks, step, agent and last update |
| `approve plan <task>` | Move to Build only if the plan has been reviewed |
| `reject <task> <reason>` | Comment and send back to Build |
| `digest` | Run the prompt in `hermes/digest.md` |
| `cost` | Read `tasks-assistant report` or the Kandev stats |

## Daily digest

Hermes cron, once a day:

```text
Read the active Kandev tasks. For each one report:
- id, title and current step,
- hours since the last activity,
- if it is in Verify, the verdict and attempt cost,
- if it exceeded budget.max_attempts or has been stuck for > 24h.

Format: short list, no filler. At the end, at most 3 suggested actions.
Do not move tasks or approve anything; only report.
```

## Security

- Hermes with least privilege: create/read/move tasks, do not delete workspaces or change secrets.
- No production credentials in the Hermes container.
- If Kandev is on the same VPS, use `127.0.0.1`; otherwise, a private network.
- Review the tool report Hermes loads; a misconfigured MCP can expose more than necessary.

---

*— Andi · 2026-11-22*
