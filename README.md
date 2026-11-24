# tasks-assistant

Control plane for agentic tasks: Kandev board, OpenCode builder, three-layer verification and Hermes as operator. The brief lives at `Projects/side/panel-tareas-agentes.md` in the vault.

## Status

Validated locally on 2026-11-22:

- Kandev installed and running at `http://127.0.0.1:38429`.
- `Gated Coding` workflow imported into the default workspace (6 steps).
- `tasks-assistant check` runs the contract checks and writes evidence.
- `tasks-assistant verify --dry-run` builds the prompt with contract + checks + diff.
- 70 CLI tests and 3 demo repo tests green.
- The project is Python 3.11+ with `uv`; it does not require Node.

Pending: provider keys, per-role profiles in Kandev, the VPS, Hermes MCP and the first real end-to-end task.

## Architecture

```text
Me ── Kandev panel ───┐
  └─ Hermes (Telegram) ─┤ MCP
                        ▼
                 Kandev (SQLite, worktrees)
                 ├─ Intake      human writes contract
                 ├─ Plan        planner (strong model)
                 ├─ Build       builder (cheap model)
                 ├─ Verify      checks → verifier (another provider)
                 └─ Human Gate  diff + evidence + cost
                        │
                 runs/<task>/attempt-N/
                 ├─ 01-tests.log
                 ├─ checks.json
                 ├─ verifier-prompt.md
                 └─ verdict.json
```

## Structure

| Path | What it is |
|---|---|
| `pyproject.toml` | Dependencies, entry points and pytest/ruff configuration |
| `workflows/gated-coding.yaml` | Portable Kandev workflow (plan → build → verify → gate) |
| `contracts/task-contract.md` | Task contract rules |
| `contracts/task-contract.schema.json` | JSON schema for the contract |
| `contracts/tasks/` | Real contracts, one per task (`<task-id>.yaml`) |
| `contracts/examples/demo-greet.yaml` | Example contract with a repo, used by the tests |
| `contracts/examples/demo-no-repo.yaml` | Example contract without Git |
| `examples/no-repo/` | Content task with its own check, without a repository |
| `src/tasks_assistant/cli.py` | `tasks-assistant init / check / verify / report` |
| `src/tasks_assistant/checks.py` | Layer 1: run commands, capture logs and timeouts |
| `src/tasks_assistant/verify.py` | Layer 2: prompt, verifier call, parsing and guards |
| `tests/` | `pytest` suite and parity fixtures |
| `examples/demo-repo/` | Minimal Python repo for testing the checks |
| `verifier/prompt.md` | Verifier system prompt |
| `verifier/rubric.md` | Review rubric |
| `hermes/` | Hermes MCP connection and daily digest |
| `compose/docker-compose.yml` | Kandev for the VPS, port bound to loopback only |
| `docs/runbook.md` | Installation, operation, VPS, backups |
| `docs/cost-controls.md` | Budgets, attempts, concurrency, ledger |
| `docs/security.md` | Trust boundaries and permissions |

## Local quickstart

Requirements: **Python 3.11+** and **[uv](https://docs.astral.sh/uv/)**. Node is not required.

```bash
cd ~/acastillo/tasks-assistant
uv sync --dev
uv tool install --editable .   # leaves `tasks-assistant` and the `tasks` alias on PATH

kandev start --headless        # panel at http://localhost:38429
./scripts/import-workflow.sh
```

If you prefer not to install it as a tool, use `uv run tasks-assistant ...`.

Create a task:

```bash
tasks-assistant init --id my-task --title "One sentence"
$EDITOR contracts/tasks/my-task.yaml
```

Run the deterministic layer against the worktree:

```bash
tasks-assistant check --contract contracts/tasks/my-task.yaml --repo ~/path/to/repo
```

Verify with another model (after the checks pass):

```bash
export VERIFIER_BASE_URL=https://openrouter.ai/api/v1
export VERIFIER_API_KEY=...
export VERIFIER_MODEL=anthropic/claude-sonnet-4.5
tasks-assistant verify --contract contracts/tasks/my-task.yaml \
  --repo ~/path/to/repo --diff-base main
```

Cumulative cost:

```bash
tasks-assistant report
```

Run the suite:

```bash
uv run pytest
uv run ruff check .
```

### Test without spending tokens

The quick path, without touching your real ledger:

```bash
./scripts/demo-local.sh
```

The `contracts/tasks/demo-local.yaml` contract points to the example Python repo. To do it step by step:

```bash
python3 scripts/mock-verifier.py &
export VERIFIER_BASE_URL=http://127.0.0.1:8765/v1
export VERIFIER_API_KEY=test
export VERIFIER_MODEL=mock-verifier
export TASKS_ASSISTANT_HOME="$PWD"

tasks-assistant check --contract contracts/tasks/demo-local.yaml \
  --repo examples/demo-repo --attempt 1
tasks-assistant verify --contract contracts/tasks/demo-local.yaml \
  --repo examples/demo-repo --diff examples/demo.diff --attempt 1
tasks-assistant report
```

The mock extracts the acceptance ids from the prompt and returns PASS for each one. For real verification, use another provider/model and a key with a spending cap.

### Repo-less task

You can also work without Git: `--repo` is only the working directory, and the verifier receives a patch with `--diff`.

```bash
./scripts/demo-no-repo.sh
```

The example lives in `examples/no-repo/`: a deterministic `check.py` and an `output.md`. The script generates the patch with `diff -u /dev/null output.md`, without initializing Git.

In Kandev, under **New Task**, choose Source **None** and a **Local** executor with a directory or scratch workspace. The task ID is still the UUID, so the contract is `contracts/tasks/<uuid>.yaml`. Because there is no `--diff-base`, the Verify step uses `--diff changes.diff` with a generated patch.

## Daily flow

Once Kandev is configured, day-to-day work is panel + contract. You do not run `check`/`verify` by hand: the workflow's **Verify** step runs them.

| Step | Who does it | Frequency |
|---|---|---|
| Create the task in **Intake** and copy its task ID | Human | Per task |
| `tasks-assistant init --id <task-id> --title "..."` and complete the contract | Human | Per task |
| Plan | Planner (agent) | Per task |
| Build | Builder (agent) | Per task |
| `tasks-assistant check` + `verify` | **Verify** step (agent) | Automatic |
| Review evidence, cost and approve | Human (Human Gate) | Per task |
| Configure keys, profiles, `TASKS_ASSISTANT_HOME`, pricing | Human | Once |
| Test with the mock or demo | Human | Development only |

Typical human commands per task:

```bash
TASK_ID=<kandev-uuid>
tasks-assistant init --id "$TASK_ID" --title "One sentence"
$EDITOR "contracts/tasks/$TASK_ID.yaml"
```

After that, you move the task through the panel. The agent does the rest and you review the Human Gate.

## Hard rules

1. Checks come from the contract written by a human. The agent does not edit them.
2. If layer 1 fails, the verifier is not called.
3. Builder and verifier cannot be the same provider/model; the CLI fails if they are.
4. A verifier `PASS` is downgraded to `FAIL` if a criterion is missing, there is a `blocker`/`major` finding, tests were weakened or protected files were touched.
5. At most `budget.max_attempts` (1–5; default 2). When exceeded, a human is escalated.
6. No agent approves its own work: the merge goes through the Human Gate.

## Models by role

| Role | Profile | Criterion |
|---|---|---|
| Planner | Frontier (high-tier Claude/GPT) | Few calls, decides the plan |
| Builder | Economy (DeepSeek/Kimi/Qwen/GLM) | Consumes most tokens |
| Verifier | Another provider/model, plan mode | No writes, different bias |
| Triage/digest | Local or economy | High volume, simple tasks |

The model per role is assigned in Kandev (`Settings > Agents`) on each step's profile. The contract records the expected pair; the CLI verifies that builder and verifier are distinct. Prices for the ledger go in `config/pricing.yaml` (copy of `config/pricing.example.yaml`).

## Hermes and VPS

- `hermes/README.md`: `mcp_servers` snippet and digest prompts.
- `compose/docker-compose.yml`: Kandev with a persistent volume and the port on loopback.
- `docs/runbook.md`: deployment, reverse proxy, backups, upgrades and installing the Python CLI inside `/data`.

On the VPS, the Verify step runs inside the agent environment. The canonical paths are:

```text
TASKS_ASSISTANT_HOME=/data/tasks-assistant
TASKS_ASSISTANT_STATE_DIR=/data/tasks-assistant/runs
```

The workflow uses `$TASKS_ASSISTANT_HOME/contracts/tasks/{task_id}.yaml`. Define that variable in the Kandev executor profile.

## Licenses and cost

Kandev is AGPL-3.0 self-hosted. OpenCode and Hermes are open source. This repo is our own tooling. The only variable cost is model tokens and the VPS.

---

*— Andi · 2026-11-22*
