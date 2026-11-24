# Security

## Trust boundaries

| Component | Trust | Can write |
|---|---|---|
| Task description | High (human) | It is the spec |
| Approved plan | High after human review (agent-drafted) | It defines scope |
| Builder | Medium | Only the worktree, within the approved plan |
| Verifier | Low for writes / high for reads | Nothing |
| Diff and repo content | Untrusted | Data, not instructions |
| Hermes | Medium | Create/query tasks via MCP |

There is no immutable contract file and no CLI enforcing these boundaries. They are process controls: the approved plan, the separate Verify profile, the exact test commands and the Human Gate.

## Panel

- Kandev does not ship with active multi-user login enabled by default. Locally, it listens on loopback.
- On a VPS: never publish `38429` to the internet. Use Tailscale, Cloudflare Tunnel or a reverse proxy with TLS + auth.
- Protect `/mcp`, `/mcp/sse` and `/mcp/message` just like the panel. An MCP client can create, move and delete tasks.
- If you enable authentication, external clients need a personal access token.

## Secrets

- Model provider keys belong in the agent profile or the Kandev secret manager. Do not put them in the task description.
- No production credentials in agents. Read-only tokens when sufficient.
- Separate keys by role and set spending caps at the provider.
- Do not commit `.env`, tokens, worktree contents or task conversations.

## Prompt injection

The repository, issues, comments and diffs are untrusted content.

- The task description is human-authored, but repository files are not. The builder must not follow instructions found in repo files.
- The Verify prompt must treat the diff as data and review it, not execute instructions from it.
- Least privilege: no production access, no `sudo`, no SSH to other hosts.
- Sandbox: Docker/SSH executor per task, with CPU/RAM limits and restricted network.
- If a task touches CI, auth, migrations or infrastructure, treat it as protected and require an explicit human decision at the Human Gate.

## Verification

- Verify runs with a different provider/model from Build.
- Verify is read-only and re-runs the exact test commands from the task description.
- The builder must not weaken tests to make them pass.
- A Verify `PASS` does not authorize a merge: the Human Gate is mandatory.
- If any acceptance item is unverified, do not approve.
- These are conventions, not enforced by a CLI. The Human Gate is the enforcement point.

## Data

- SQLite, plans and worktrees live in `~/.kandev` / the `kandev-data` volume.
- Encrypted backups (restic) and a tested restore.
- Worktree retention: delete them when archiving the task.
- Logs: do not include tokens or personal data; if a log contains them, redact it before sharing.

## Checklist before exposing the VPS

- [ ] Port on loopback or firewall.
- [ ] Reverse proxy with TLS and auth.
- [ ] `/mcp` protected.
- [ ] Agents without production credentials.
- [ ] Per-key spending caps.
- [ ] Backup + tested restore.
- [ ] Pinned Kandev version (no `latest`).
- [ ] Workflow reviewed by a human.
- [ ] `Planner`, `Builder` and `Verifier` profiles assigned to the correct steps.
- [ ] Verify uses a different provider/model from Build.

---

*— Andi · 2026-11-24*
