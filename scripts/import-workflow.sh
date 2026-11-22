#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KANDEV_URL="${KANDEV_URL:-http://127.0.0.1:38429}"
WORKFLOW_FILE="${1:-$ROOT/workflows/gated-coding.yaml}"

if [[ ! -f "$WORKFLOW_FILE" ]]; then
  echo "No existe el workflow: $WORKFLOW_FILE" >&2
  exit 1
fi

workspace_id="${2:-}"
if [[ -z "$workspace_id" ]]; then
  workspace_id="$(curl -fsS "$KANDEV_URL/api/v1/workspaces" | python3 -c 'import json,sys; print(json.load(sys.stdin)["workspaces"][0]["id"])')"
  echo "Workspace: $workspace_id"
fi

echo "Importando $(basename "$WORKFLOW_FILE") en $KANDEV_URL ..."
response="$(curl -fsS -X POST \
  "$KANDEV_URL/api/v1/workspaces/$workspace_id/workflows/import" \
  -H "Content-Type: application/x-yaml" \
  --data-binary "@$WORKFLOW_FILE")"

echo "$response" | python3 -m json.tool
