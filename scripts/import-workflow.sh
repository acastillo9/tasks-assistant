#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KANDEV_URL="${KANDEV_URL:-http://127.0.0.1:38429}"
WORKFLOW_FILE="${1:-$ROOT/workflows/gated-coding.yaml}"

if [[ ! -f "$WORKFLOW_FILE" ]]; then
  echo "Workflow file does not exist: $WORKFLOW_FILE" >&2
  exit 1
fi

workspace_id="${2:-}"
if [[ -z "$workspace_id" ]]; then
  workspace_id="$(curl -fsS "$KANDEV_URL/api/v1/workspaces" | python3 -c 'import json,sys; print(json.load(sys.stdin)["workspaces"][0]["id"])')"
  echo "Workspace: $workspace_id"
fi

echo "Importing $(basename "$WORKFLOW_FILE") into $KANDEV_URL ..."
response="$(curl -fsS -X POST \
  "$KANDEV_URL/api/v1/workspaces/$workspace_id/workflows/import" \
  -H "Content-Type: application/x-yaml" \
  --data-binary "@$WORKFLOW_FILE")"

echo "$response" | python3 -m json.tool

# Kandev import only creates workflows; it skips any whose name already exists.
# Fail loudly so a stale workflow is not mistaken for a successful import.
skipped="$(printf '%s' "$response" | python3 -c 'import json, sys; print(", ".join(json.load(sys.stdin).get("skipped") or []))')"
if [[ -n "$skipped" ]]; then
  echo "Kandev skipped existing workflow(s): $skipped" >&2
  echo "Import does not update a workflow whose name already exists." >&2
  echo "Rename or delete it in Kandev, then run this script again." >&2
  exit 1
fi
