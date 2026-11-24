# Runbook

## 1. Requirements

- Kandev.
- Git and a model provider account for the agent profiles.
- Docker only for the VPS or a containerized executor.
- macOS/Linux for the panel; Windows via WSL.

No Python project, `uv`, CLI, contracts or `TASKS_ASSISTANT_HOME` are required. The import helper uses `python3` only to parse the Kandev API response.

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

## 3. Prepare the workspace and profiles

1. Open the panel and create a workspace.
2. Add the repository (URL or local path) and choose the base branch.
3. Under **Settings > Agents**, install/verify OpenCode and authenticate the provider.
4. Create three profiles:
   - `Planner` — frontier model, plan mode.
   - `Builder` — economy model, build mode.
   - `Verifier` — another provider/model, plan or read-only mode.
5. Do not put verifier keys in executor environment variables; configure the provider credential in the agent profile or Kandev secrets.

Importing the workflow **does not create profiles**. It links by display name. If a step cannot find `Planner`, `Builder` or `Verifier`, it is left without a profile and Kandev uses the agent assigned to the task. Check every step after import.

## 4. Import the workflow

```bash
cd ~/acastillo/tasks-assistant
./scripts/import-workflow.sh
# or with an explicit workflow and workspace:
./scripts/import-workflow.sh workflows/gated-coding.yaml <workspace-id>
```

Expected response: `{"created":["Gated Coding"],"skipped":[]}`.

Reimporting the same name is skipped. To update: delete or rename the existing `Gated Coding` workflow in the UI, then import again. The script fails loudly when it gets a `skipped` response so a stale workflow is not mistaken for a successful import.

After import, open every step and confirm:

- `Plan` uses `Planner`.
- `Build` uses `Builder`.
- `Verify` uses `Verifier`, with a different provider/model from `Builder`.
- Build and Verify have **Wait for agent completion signal** enabled (`auto_advance_requires_signal: true`).
- Intake is the start step and has no auto-start.
- Done has **Complete task on entry** enabled.

## 5. Operate a task

1. **Intake**: create the task and write the description from `docs/task-template.md`. Every acceptance item must be verifiable and the test commands must be exact and non-interactive. Move the task to Plan when it is complete.
2. **Plan**: the Planner reads the task, proposes a plan and saves it with `create_task_plan_kandev`. Review the plan, edit it if needed, and move the task to Build. Do not let Build start from an unapproved plan.
3. **Build**: the Builder implements only the approved plan, commits, runs the test commands and reports. It calls `step_complete_kandev` when its turn is done; only then does the task move to Verify.
4. **Verify**: the Verifier re-runs the exact commands, reviews the diff against every acceptance item and reports PASS/FAIL with file:line evidence. It is read-only and uses another model. It calls `step_complete_kandev` when the report is written; only then does the task move to Human Gate.
5. **Human Gate**: review the diff, test output, Verify report and token usage. Approve to Done, send back to Build with comments (at most two loops), or escalate.
6. **Done**: completes on entry and is archived after 7 days.

If the agent asks a clarification or a turn ends without `step_complete_kandev`, the task stays in its current step. That is intentional. Answer or resume, then let it finish.

## 6. Evidence and audit

There is no `runs/` directory and no `verdict.json`. The record is:

- the task description (the spec),
- the plan and its version history (the approved contract),
- the task conversation (Build and Verify reports),
- the step transitions:

```bash
curl -fsS "http://127.0.0.1:38429/api/v1/tasks/<task-id>/step-transitions?limit=50" \
  | python3 -m json.tool
```

`trigger` shows what moved the task (`manual_move`, `mcp_move`, `engine_transition`), and `actor_kind` shows whether a human, agent or system did it.

Kandev shows token usage per session. Use it at the Human Gate; there is no cumulative cost ledger.

## 7. VPS

```bash
cd ~/acastillo/tasks-assistant
cp .env.example .env
# edit KANDEV_VERSION with a real tag
docker compose -f compose/docker-compose.yml up -d
docker compose -f compose/docker-compose.yml logs -f kandev
```

- The port is published only on `127.0.0.1:38429`. Do not expose it to the internet.
- Remote access: Tailscale, Cloudflare Tunnel or a reverse proxy with TLS and auth. Protect `/mcp`, `/mcp/sse` and `/mcp/message` too; they need long-lived streaming.
- The image ships with `KANDEV_DOCKER_ENABLED=false`; the Docker executor is not cleanly supported with the containerized control plane. Use an SSH executor to another machine (preferred) or run Kandev on the host.
- Small VPS: Kandev on the VPS and an SSH executor to your Mac or a larger machine.
- Concurrency limits: 1–2 tasks at a time on 2 vCPU / 4 GB.

On the VPS you need Kandev and the imported workflow only. Do not install `uv`, the old CLI or contract files. If you want to import from the server, copy `workflows/gated-coding.yaml` and `scripts/import-workflow.sh` or run the import from your Mac against a reachable Kandev URL:

```bash
KANDEV_URL=http://127.0.0.1:38429 ./scripts/import-workflow.sh
```

## 8. Backups

SQLite and worktrees live in the `kandev-data` volume (or `~/.kandev` locally).

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
3. Export the current workflow from Kandev before upgrading.
4. Start the new version on an alternate port with a disposable volume.
5. Verify that the workflow imports and that a test task runs.
6. Change `KANDEV_VERSION`, recreate the container and keep the snapshot until validation passes.

If the new version changes the portable workflow format, update `workflows/gated-coding.yaml` and reimport into a disposable workspace before touching the real one.

## 10. Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `import` returns `skipped` | A workflow with that name already exists | Delete or rename it in the UI, then import again |
| Step has no agent | Profile name/model/mode does not match | Assign `Planner`, `Builder` or `Verifier` to the step in the UI |
| Task stays in Build | The agent did not call `step_complete_kandev` | Resume the session and ask it to finish and signal; or move manually after review |
| Task stays in Verify | Same, or a pending clarification | Answer the question, resume, and check the tool catalog |
| Verify uses the same model as Build | Profile not assigned or copied | Set `Verifier` on the Verify step, with another provider/model |
| Task advances without a report | Completion signal was called too early | Review the diff at Human Gate; tighten the Verify prompt or keep Verify manual |
| Agent edits acceptance criteria | Task description is editable | Do not approve; send back to Intake and restore the criteria |
| `diff exceeds the maximum` | Not applicable | The CLI is gone; review large diffs in Kandev or split the task |
| `verifier provider 401/429` | Provider credential or rate limit | Check the profile credential and provider limits |
| Checks hang | Interactive command or watch mode | Use a non-interactive CI command in the task description |
| VPS cannot start | Missing `KANDEV_VERSION` or port conflict | Set a real tag in `.env`; check `docker compose logs` |

## 11. Uninstall

```bash
docker compose -f compose/docker-compose.yml down       # keeps the volume
docker compose -f compose/docker-compose.yml down -v    # deletes SQLite and worktrees
```

Local: remove `~/.kandev` after exporting the workflows you want to keep.

---

*— Andi · 2026-11-24*
