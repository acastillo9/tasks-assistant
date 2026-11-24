# tasks-assistant

Kandev-only gated coding: a portable workflow for a human spec, an approved plan, a cheap builder, an independent verifier and a human gate.

This repo no longer contains a CLI, per-task contracts or an evidence ledger. The task description is the spec, the approved task plan is the contract, and Kandev is the only runtime.

## Status

Simplified on 2026-11-24. The previous Python contract/verifier control plane is archived in git:

- branch `archive/python-control-plane`
- tag `pre-kandev-only`

If the Kandev-only flow proves too weak, restore it from that tag instead of rebuilding it.

## Architecture

```text
Me ── Kandev panel ── Hermes (optional, MCP)
          │
          ▼
       Kandev (SQLite + worktrees)
       ├─ Intake      human writes the task description
       ├─ Plan        Planner profile, plan mode
       ├─ Build       Builder profile, cheap model
       ├─ Verify      Verifier profile, another provider/model
       └─ Human Gate  diff + test output + Verify report
```

Kandev stores the task, the plan (with version history), the conversations and the step transitions. There is no `runs/` directory and no cost ledger; Kandev shows token usage per session.

## Quickstart

Requirements: Kandev. Docker only for the VPS or a containerized executor. The import helper uses `curl` and `python3`.

```bash
cd ~/acastillo/tasks-assistant
kandev start --headless          # panel at http://localhost:38429
```

Before importing, create the workspace, add the repository, and create three agent profiles in Kandev:

| Profile | Model | Purpose |
|---|---|---|
| `Planner` | frontier (high-tier) | Reads the task, writes the plan |
| `Builder` | economy | Implements the approved plan |
| `Verifier` | another provider/model | Runs tests and reviews the diff |

Import does **not** create profiles. It links by display name; if a step cannot find its profile, Kandev falls back to the agent assigned to the task. Open every step after import and confirm the profile and model.

Then import:

```bash
./scripts/import-workflow.sh     # imports workflows/gated-coding.yaml
```

Import **skips an existing workflow with the same name**. If `Gated Coding` already exists, delete or rename it in Kandev first, then import.

## The flow

| Step | Who | What happens |
|---|---|---|
| **Intake** | Human | Writes the task description: objective, acceptance checklist, exact test commands, out of scope, repo/branch |
| **Plan** | Planner | Produces a plan with an acceptance mapping and test plan; saves it with `create_task_plan_kandev`; stops for review |
| **Build** | Builder | Implements only the approved plan, commits, runs the tests, reports, then calls `step_complete_kandev` |
| **Verify** | Verifier | Read-only. Re-runs the exact tests, reviews the diff against every acceptance item, reports PASS/FAIL with file:line, then signals |
| **Human Gate** | Human | Reviews diff, test output, Verify report and token usage; approves to Done or sends back to Build |
| **Done** | — | Task completes on entry; archived after 7 days |

Build and Verify use `auto_advance_requires_signal: true`. They only move forward when the agent calls `step_complete_kandev`. A pending clarification or an unfinished turn stays put.

## Task description template

Paste this into the Kandev task description at Intake. The full version lives in `docs/task-template.md`.

```text
Objective:
  One or two sentences. What must be true when this is done?

Acceptance:
  - [ ] A verifiable item.
  - [ ] Another verifiable item.

Test commands:
  - `exact command`
  - `exact command`

Out of scope:
  - What must not be touched.

Repo/branch:
  Repository and base branch.

Risk notes:
  CI, auth, migrations, secrets, or anything else that needs extra review.
```

Every acceptance item must be checkable. Test commands must run non-interactively.

## Hard rules (conventions, not enforced by a CLI)

1. The human writes the task description before Plan. The agent does not edit the acceptance criteria or test commands.
2. The plan is approved by a human before Build.
3. The builder never weakens a test to make it pass.
4. Verify uses a different provider/model from Build.
5. If any acceptance item is unverified, Human Gate does not approve.
6. At most two Build loops; the third is a human decision.
7. No agent approves its own work.

## What this does not enforce

The old CLI enforced these; Kandev does not:

- immutable acceptance criteria (the task description and plan are editable),
- a hard builder≠verifier check (it is a profile assignment),
- structured `verdict.json` / `checks.json` evidence,
- a cost ledger and attempt budget.

The replacements are the approved plan, the separate Verify profile, the exact test commands, `step_complete_kandev` gating, and the Human Gate. Treat them as process, not as a security boundary.

Audit trail: the task conversation, the plan's version history, and `GET /api/v1/tasks/:id/step-transitions`.

## Repo layout

| Path | What it is |
|---|---|
| `workflows/gated-coding.yaml` | Portable Kandev workflow |
| `scripts/import-workflow.sh` | Imports the workflow into a workspace |
| `docs/task-template.md` | Copy-paste task description template |
| `docs/runbook.md` | Install, profiles, import, operate, VPS, upgrades |
| `docs/security.md` | Trust boundaries and the VPS checklist |
| `docs/cost-controls.md` | Kandev-native cost controls |
| `compose/docker-compose.yml` | Kandev for the VPS, loopback only |
| `hermes/` | Optional Telegram operator via Kandev MCP |

## VPS

The VPS needs Kandev and the imported workflow. It does **not** need the CLI, `uv`, contracts or `TASKS_ASSISTANT_HOME`.

```bash
cp .env.example .env
# pin KANDEV_VERSION to a real tag
docker compose -f compose/docker-compose.yml up -d
```

Keep the port on loopback or behind an authenticated TLS proxy. See `docs/runbook.md` for profiles, import, backups and upgrades.

## Rollback

```bash
git switch archive/python-control-plane
# or inspect the tag:
git show pre-kandev-only --stat
```

The archive contains the Python CLI, contract schema, verifier prompt, tests and demo scripts as they were before this simplification.

---

*— Andi · 2026-11-24*
