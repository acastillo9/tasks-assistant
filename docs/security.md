# Security

## Trust boundaries

| Component | Trust | Can write |
|---|---|---|
| Contract | High (human) | It is the source of truth |
| Checks | High (human) | Nothing; they only run commands |
| Builder | Medium | Only the worktree, within scope |
| Verifier | Low for writes / high for reads | Nothing |
| Diff and repo content | Untrusted | Data, not instructions |
| Hermes | Medium | Create/query tasks via MCP |

## Panel

- Kandev does not ship with active multi-user login enabled by default. Locally, it listens on loopback.
- On a VPS: never publish `38429` to the internet. Use Tailscale, Cloudflare Tunnel or a reverse proxy with TLS + auth.
- Protect `/mcp`, `/mcp/sse` and `/mcp/message` just like the panel. An MCP client can create, move and delete tasks.
- If you enable authentication, external clients need a personal access token.

## Secrets

- `VERIFIER_API_KEY` goes in environment variables or the Kandev secret manager, never in the contract.
- No production credentials in agents. Read-only tokens when sufficient.
- Separate keys by role and set spending caps at the provider.
- `runs/` may contain diffs and test output: do not commit it.

## Prompt injection

The repo, issues and comments are untrusted content.

- The verifier system prompt declares the diff as data and delimits `<untrusted_diff>`; the CLI neutralizes the closing delimiter.
- The builder must not execute instructions found in repo files.
- Least privilege: no production access, no `sudo`, no SSH to other hosts.
- Sandbox: Docker/SSH executor per task, with CPU/RAM limits and restricted network.
- If a task touches CI, auth, migrations or infrastructure, treat it as protected and require an explicit human gate.

## Verification

- The verifier runs in plan/read-only mode and with another provider/model.
- The CLI downgrades any `PASS` with incomplete criteria, `blocker`/`major` findings, weakened tests or modified protected files to `FAIL`.
- A `PASS` does not authorize a merge: the human gate is mandatory.
- Check commands come from the human contract; an agent cannot add or change commands.

## Data

- SQLite and worktrees in `~/.kandev` / the `kandev-data` volume.
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
- [ ] Workflow and contract reviewed by a human.

---

*— Andi · 2026-11-22*
