#!/usr/bin/env bash
# End-to-end local demo with a mock verifier. Spends no tokens and does not write to runs/.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export TASKS_ASSISTANT_HOME="$ROOT"
STATE="$(mktemp -d "${TMPDIR:-/tmp}/tasks-assistant-demo.XXXXXX")"
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
  --contract contracts/tasks/demo-local.yaml \
  --repo examples/demo-repo \
  --attempt 1

tasks-assistant verify \
  --contract contracts/tasks/demo-local.yaml \
  --repo examples/demo-repo \
  --diff examples/demo.diff \
  --attempt 1

tasks-assistant report

echo
echo "Evidence from this run: $STATE"
