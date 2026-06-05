#!/usr/bin/env bash
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$REPO/.venv/bin/python"

args=()
while [[ $# -gt 0 ]]; do
  if [[ "$1" == "-f" && $# -ge 2 ]]; then
    conn="$2"
    if [[ "$conn" == *'\'* || "$conn" =~ ^[A-Za-z]: ]]; then
      conn="$(wslpath "$conn")"
    fi
    args+=("-f" "$conn")
    shift 2
  else
    args+=("$1")
    shift
  fi
done

exec "$PYTHON" -m ipykernel_launcher "${args[@]}"
