# Runbook

## 1. Requirements

- Python ≥ 3.11 and [uv](https://docs.astral.sh/uv/).
- Docker only if you will use Kandev in a container or a Docker executor.
- Git and a model provider account with an API key.
- macOS/Linux for the panel; Windows via WSL.

Node is not required for this project. Kandev is a Go binary; the official image includes Node 24 only for agents that need it and for JS repos.

The repo CLI:

```bash
cd ~/acastillo/tasks-assistant
uv sync --dev
uv tool install --editable .   # leaves `tasks-assistant` and `tasks` on PATH
```

For development, `uv run tasks-assistant ...` also works without installing the tool.

## 2. Install Kandev

Local:

```bash
brew install kdlbs/kandev/kandev
# or download the native binary from the releases
kandev start --port 38429
```

The panel is at `http://localhost:38429`. Data lives in `~/.kandev` (SQLite + worktrees). In a persistent deployment, pin a version.

System service:

```bash
kandev service install --system   # systemd/launchd
kandev service status
```

## 3. Prepare the workspace

1. Open the panel and create a workspace.
2. Add the repository (URL or local path).
3. Under **Settings > Agents**, install/verify OpenCode and authenticate the provider.
4. Create three OpenCode profiles, one per role:
   - `Planner` — frontier model, `plan` mode.
   - `Builder` — economy model, `build` mode.
   - `Verifier` — another provider/model, `plan` mode, no write permissions.
5. Under **Settings > Secrets**, store `VERIFIER_BASE_URL`, `VERIFIER_API_KEY`, `VERIFIER_MODEL`. Do not use production credentials.

Importing the workflow **does not create profiles**. It links by exact display name + model + mode; if they do not match, the step is left without a profile and Kandev uses the agent assigned to the task.

## 4. Import the workflow

```bash
cd ~/acastillo/tasks-assistant
./scripts/import-workflow.sh
# or with an explicit workspace:
./scripts/import-workflow.sh gated-coding.yaml <workspace-id>
```

Expected response: `{"created":["Gated Coding"],"skipped":[]}`. Reimporting the same name skips it; to update, delete the workflow in the UI or use another name.

Verify that the 6 steps exist:

```bash
sqlite3 ~/.kandev/data/kandev.db \
  "SELECT position,name FROM workflow_steps WHERE workflow_id=(SELECT id FROM workflows WHERE name='Gated Coding') ORDER BY position;"
```

## 5. Operate a task

1. **Intake**: create the contract.

   ```bash
   tasks-assistant init --id <task-id> --title "One sentence"
   $EDITOR contracts/tasks/<task-id>.yaml
   ```

   The `task-id` must match the task id in Kandev; the workflow interpolates `{task_id}` in paths.

2. **Plan**: move the task to `Plan`. The planner proposes and saves the plan; it does not write code. Review it and move the task to `Build`.

3. **Build**: the builder implements in its worktree and commits.

4. **Verify**: the step runs, in order:

   ```bash
   tasks-assistant check --contract contracts/tasks/<task-id>.yaml --repo .
   tasks-assistant verify --contract contracts/tasks/<task-id>.yaml --repo . --diff-base main
   ```

   If `check` fails, the verifier is not called.

5. **Human Gate**: review the diff, `verdict.json`, `checks.json` and `tasks-assistant report`. Approve, send back to `Build` or escalate.

6. **Done**: archived after 7 days.

## 6. Evidence and ledger

Per attempt:

```text
runs/<task-id>/attempt-<n>/
├── 01-tests.log
├── checks.json
├── verifier-prompt.md
└── verdict.json
```

History: `runs/ledger.jsonl`. Each line records task, attempt, builder, verifier, criteria, findings, tokens, cost and latency. `tasks-assistant report` summarizes it.

`runs/` is in `.gitignore`: evidence is operational, not a source of truth. If you want to keep it, upload it to a bucket or include it in the backup.

You can separate state from the installed code with:

```bash
export TASKS_ASSISTANT_STATE_DIR=/path/to/runs
```

## 7. VPS

```bash
cd ~/acastillo/tasks-assistant
cp .env.example .env
# edit KANDEV_VERSION with a real tag and the keys
docker compose -f compose/docker-compose.yml up -d
docker compose -f compose/docker-compose.yml logs -f kandev
```

- The port is published only on `127.0.0.1:38429`. Do not expose it to the internet.
- Remote access: Tailscale, Cloudflare Tunnel or a reverse proxy with TLS and auth. Protect `/mcp`, `/mcp/sse` and `/mcp/message` too; they need long-lived streaming.
- The image ships with `KANDEV_DOCKER_ENABLED=false`; the Docker executor is not cleanly supported with the containerized control plane. Use an SSH executor to another machine (preferred) or run Kandev on the host.
- Small VPS: Kandev on the VPS and an SSH executor to your Mac or a larger machine.
- Concurrency limits: 1–2 tasks at a time on 2 vCPU / 4 GB.

### 7.1 Install the CLI inside the container (Option 0)

The official image already includes Python 3.11, `venv` and `pipx`; `uv` can be installed without touching the system. The repo and CLI live in the persistent `/data` volume.

```bash
docker exec --user kandev -it kandev bash

mkdir -p /data/.npm-global/bin
export PIPX_HOME=/data/pipx
export PIPX_BIN_DIR=/data/.npm-global/bin
pipx install uv

cd /data
git clone <repo-url> tasks-assistant
# alternative without git: copy it from the host with docker cp

cd /data/tasks-assistant
export UV_TOOL_DIR=/data/uv-tools
export UV_TOOL_BIN_DIR=/data/.npm-global/bin
uv tool install --editable .
```

`/data/.npm-global/bin` is already on the image's `PATH`. Verify:

```bash
tasks-assistant --help
```

In the Kandev executor profile (Worktree/Local), set:

```text
TASKS_ASSISTANT_HOME=/data/tasks-assistant
VERIFIER_BASE_URL=https://openrouter.ai/api/v1
VERIFIER_MODEL=anthropic/claude-sonnet-4.5
VERIFIER_API_KEY=<Kandev secret>
```

The workflow uses `$TASKS_ASSISTANT_HOME/contracts/tasks/{task_id}.yaml`. Test it from a task:

```bash
tasks-assistant check --contract "$TASKS_ASSISTANT_HOME/contracts/tasks/<task-id>.yaml" --repo .
tasks-assistant verify --contract "$TASKS_ASSISTANT_HOME/contracts/tasks/<task-id>.yaml" \
  --repo . --diff-base main --dry-run
```

After a real verification, check persistence:

```bash
docker compose restart kandev
docker exec --user kandev -it kandev tasks-assistant report
```

If you prefer to isolate the agent, use an SSH executor to a worker and install the CLI there with `uv tool install --editable .`. Over SSH, environment variables are limited to the approved credentials and repository secrets; use an absolute path in the workflow if `TASKS_ASSISTANT_HOME` is not forwarded.

## 8. Backups

SQLite + worktrees live in the `kandev-data` volume (or `~/.kandev` locally). The repo and CLI in `/data/tasks-assistant` are also inside the volume.

```bash
# Consistent snapshot: stop Kandev or use the System backup
docker compose -f compose/docker-compose.yml stop kandev
docker run --rm -v kandev-data:/data -v "$PWD/backups:/backup" alpine \
  tar -czf /backup/kandev-$(date +%F).tar.gz -C /data .
docker compose -f compose/docker-compose.yml start kandev

restic -r b2:bucket:kandev backup backups/
restic -r b2:bucket:kandev check
```

Test a full restore at least once a month. A backup without a tested restore is not a backup.

## 9. Upgrades

1. Read the CHANGELOG and pin the new tag.
2. Snapshot the volume.
3. Start the new version on an alternate port with a disposable volume.
4. Verify that the workflow imports and that a test task runs.
5. Change `KANDEV_VERSION`, recreate the container and keep the snapshot until validation passes.

Update the CLI with:

```bash
cd /data/tasks-assistant
git pull
uv tool install --editable . --reinstall
```

Do not depend on Office mode (experimental).

## 10. Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `import` returns `skipped` | A workflow with that name already exists | Delete it in the UI or use another name |
| Step has no agent | Profile does not match name/model/mode | Assign it in the UI; inspect `agent_profile_id` in SQLite |
| `tasks-assistant: command not found` | CLI not installed or not on PATH | `uv tool install --editable .`; check `~/.local/bin` or `/data/.npm-global/bin` |
| `No module named tasks_assistant` | Dependencies not synced | `uv sync --dev` |
| `pip install` fails with PEP 668 | System-managed Python | Use `uv`/`venv`; do not install globally |
| `tasks-assistant: missing --contract` | Flag omitted | `--contract contracts/tasks/<id>.yaml` |
| `no check evidence` | You did not run `tasks-assistant check` or the attempt does not match | Run check with the same `--attempt` |
| `runs/` not writable | CLI is on a root/ephemeral path | Install it in `/data` or set `TASKS_ASSISTANT_STATE_DIR` |
| `$TASKS_ASSISTANT_HOME` empty | Variable not defined in the executor | Define it in the profile; use an absolute path over SSH |
| `diff exceeds the maximum` | Change is too large | Split the task or review only the files in scope |
| `invalid verifier` | Builder and verifier share provider/model | Change `VERIFIER_MODEL` or the contract |
| `verifier provider 401` | Wrong key or no balance | Check `VERIFIER_API_KEY` and the provider |
| `verifier provider 429` | Rate limit | Lower concurrency; retry with backoff |
| Checks hang | Interactive command or watch mode | Use CI commands (`--run`, `--watch=false`) |

## 11. Uninstall

```bash
docker compose -f compose/docker-compose.yml down       # keeps the volume
docker volume rm kandev-data                            # deletes data, irreversible
uv tool uninstall tasks-assistant
brew uninstall kandev                                   # if installed with brew
```

---

*— Andi · 2026-11-22*
