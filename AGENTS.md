# AGENTS.md

## What this repo is

A Kandev-only gated-coding setup: one portable workflow plus the docs needed to run it. There is no `tasks-assistant` CLI, no per-task contract YAML, no `runs/` evidence directory and no verifier API call outside Kandev.

The task description is the spec. The approved task plan is the contract. Kandev runs the agents and stores the history.

## Commands

- Start Kandev locally: `kandev start --headless` (panel at `http://127.0.0.1:38429`).
- Import the workflow: `./scripts/import-workflow.sh` or `./scripts/import-workflow.sh workflows/gated-coding.yaml <workspace-id>`.
- VPS: `docker compose -f compose/docker-compose.yml up -d`.
- There is no Python test suite or lint gate in this repo. Validate a change by importing the workflow into a disposable workspace and walking one task through it.

## How the flow fits together

- `workflows/gated-coding.yaml` defines Intake -> Plan -> Build -> Verify -> Human Gate -> Done.
- Intake is human: objective, acceptance checklist, exact test commands, out of scope, repo/branch.
- Plan runs in Kandev plan mode with the `Planner` profile and saves the plan via `create_task_plan_kandev`. A human approves the plan before Build.
- Build uses the `Builder` profile, implements only the approved plan, commits, runs the tests and calls `step_complete_kandev`.
- Verify uses the `Verifier` profile (different provider/model), is read-only, re-runs the exact tests and reports PASS/FAIL per acceptance item.
- Build and Verify use `auto_advance_requires_signal: true`; they do not advance without `step_complete_kandev`.
- Human Gate is the only approval. No agent approves its own work.

## Repo-specific traps

- **Import skips existing workflow names.** Kandev does not update a workflow in place. Delete or rename the existing `Gated Coding` workflow first, then import. `scripts/import-workflow.sh` fails loudly when it gets a `skipped` response.
- **Import does not create agent profiles.** It links by display name/model/mode. Create `Planner`, `Builder` and `Verifier` in Settings > Agents first, and confirm every step in the UI after import. A missing profile silently falls back to the task's agent.
- **The workflow is per workspace and per Kandev instance.** Import it separately on the VPS or any other installation.
- **`step_complete_kandev` is the completion gate.** If the agent cannot find the tool, tell it to search the active tool catalog. A turn that never signals leaves the task in Build or Verify.
- **There is no immutable contract.** The task description and plan are editable. Do not treat prompt instructions or `allow_manual_move` as a security boundary; the Human Gate is the control.
- **Do not reintroduce the old CLI/contract layer** without an explicit decision. The previous implementation is archived at tag `pre-kandev-only` and branch `archive/python-control-plane`.
- **VPS needs only Kandev.** Do not install `uv`, the CLI or contract files there. `TASKS_ASSISTANT_HOME` is gone; remove it from executor profiles.
- **Workflow changes are code.** Keep `workflows/gated-coding.yaml` in git and export the Kandev workflow before large edits.

## Layout

| Path | What it is |
|---|---|
| `workflows/gated-coding.yaml` | The workflow |
| `scripts/import-workflow.sh` | Import helper |
| `docs/task-template.md` | Task description template |
| `docs/runbook.md` | Install, profiles, import, operate, VPS |
| `docs/security.md` | Trust boundaries and VPS checklist |
| `docs/cost-controls.md` | Kandev-native cost controls |
| `compose/docker-compose.yml` | Kandev for the VPS |
| `hermes/` | Optional Telegram operator via Kandev MCP |
