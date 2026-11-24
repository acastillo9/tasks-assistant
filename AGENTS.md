# AGENTS.md

## Commands

- Setup: `uv sync --dev` (Python 3.11+, uv; Node is not used).
- CI gates, in order: `uv run ruff check .` then `uv run pytest`.
- Single test: `uv run pytest tests/test_verify.py::test_name`.
- Optional typecheck, not wired into CI: `uv run mypy src`.
- CLI: `uv run tasks-assistant ...`. Bare `tasks-assistant` / `tasks` exist only after `uv tool install --editable .`; the demo scripts and docs assume that install.
- Token-free end-to-end: `./scripts/demo-local.sh`; repo-less variant: `./scripts/demo-no-repo.sh`. Both start a mock verifier and use a temporary state dir.

## How the control plane fits together

- Entrypoint `src/tasks_assistant/cli.py` exposes `init`, `check`, `verify`, `report`. `check` runs the contract's shell commands (layer 1). `verify` only runs after layer 1 passes; it builds a prompt from contract + check tails + diff, calls an OpenAI-compatible endpoint, applies guards, and writes evidence.
- Evidence lives under `runs/<task-id>/attempt-N/` (`checks.json`, `verdict.json`, `verifier-prompt.md`, logs), with history in `runs/ledger.jsonl`. `runs/` is gitignored: do not commit or hand-edit it.
- `TASKS_ASSISTANT_HOME` is the repo root used to find `contracts/`, `verifier/prompt.md`, and `config/pricing.yaml`; `TASKS_ASSISTANT_STATE_DIR` overrides where `runs/` is written. Set both when invoking the CLI outside this checkout.
- `contracts/tasks/<kandev-task-id>.yaml` are real human-authored contracts; `contracts/examples/` and `examples/` are test fixtures. Never change a contract, its checks, or tests to make verification pass.

## Repo-specific traps

- Contract validation is hand-coded in `src/tasks_assistant/contract.py`; `contracts/task-contract.schema.json` is documentation only. Keep both in sync manually.
- `tests/baseline/` holds historical TypeScript-era artifacts used only by `tests/test_parity.py` to lock JSON schemas and verifier-prompt headings. The active implementation is Python; do not restore Node/npm tooling, and update these fixtures only for deliberate schema/prompt changes.
- `verify --diff-base` does not include untracked file contents (only lists their names). Stage new files or pass `--diff`. Diffs over `MAX_DIFF_BYTES` (200 KB) fail instead of truncating.
- Running `check`/`verify` manually appends ledger entries and advances the attempt count, including `ERROR` entries from failed checks. Experiment with a temporary `TASKS_ASSISTANT_STATE_DIR` to avoid burning a task's `max_attempts`.
- `config/pricing.yaml` is gitignored; without it `cost_usd` is `null` and reports show `no-rate`. Copy `config/pricing.example.yaml` when cost reporting matters.
- `verify` needs `VERIFIER_BASE_URL` and `VERIFIER_API_KEY`, and builder/verifier must differ in provider+model; `--dry-run` skips the API call. Kandev, its workflow (`workflows/gated-coding.yaml`), compose, and Hermes are external integrations not covered by the Python suite.
