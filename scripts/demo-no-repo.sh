#!/usr/bin/env bash
# Repo-less task demo: temporary directory, custom check and a patch without Git.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/tasks-assistant-no-repo.XXXXXX")"
STATE="$(mktemp -d "${TMPDIR:-/tmp}/tasks-assistant-no-repo-state.XXXXXX")"

cp examples/no-repo/check.py "$WORK/check.py"
cp examples/no-repo/output.md "$WORK/output.md"
diff -u /dev/null "$WORK/output.md" > "$WORK/changes.diff" || true

export TASKS_ASSISTANT_HOME="$ROOT"
export TASKS_ASSISTANT_STATE_DIR="$STATE"

cleanup() {
  if [[ -n "${MOCK_PID:-}" ]]; then
    kill "$MOCK_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

python3 scripts/mock-verifier.py &
MOCK_PID=$!
sleep 0.5

export VERIFIER_BASE_URL="http://127.0.0.1:8765/v1"
export VERIFIER_API_KEY="test"
export VERIFIER_MODEL="mock-verifier"

tasks-assistant check \
  --contract contracts/examples/demo-no-repo.yaml \
  --repo "$WORK" \
  --attempt 1

tasks-assistant verify \
  --contract contracts/examples/demo-no-repo.yaml \
  --repo "$WORK" \
  --diff "$WORK/changes.diff" \
  --attempt 1

tasks-assistant report

echo
echo "Working directory (no .git): $WORK"
echo "Evidence from this run: $STATE"
