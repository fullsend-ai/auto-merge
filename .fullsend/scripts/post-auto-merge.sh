#!/usr/bin/env bash
# Validate model output, write a receipt, revalidate, and merge the exact head.

set -euo pipefail

: "${GH_TOKEN:?GH_TOKEN must be set}"
: "${ISSUE_URL:?ISSUE_URL must be set}"
: "${TARGET_REPO_DIR:?TARGET_REPO_DIR must be set}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -n "${FULLSEND_VALIDATED_ITERATION_DIR:-}" ]]; then
  RESULT_FILE="${FULLSEND_VALIDATED_ITERATION_DIR}/agent-result.json"
else
  RESULT_FILE=""
  best=-1
  for candidate in iteration-*/output/agent-result.json; do
    [[ -f "${candidate}" ]] || continue
    iteration="${candidate#iteration-}"
    iteration="${iteration%%/*}"
    if [[ "${iteration}" =~ ^[0-9]+$ ]] && (( iteration > best )); then
      best="${iteration}"
      RESULT_FILE="${candidate}"
    fi
  done
fi

[[ -n "${RESULT_FILE}" && -f "${RESULT_FILE}" ]] || {
  echo "post-auto-merge: no validated agent-result.json found" >&2
  exit 1
}

python3 "${SCRIPT_DIR}/auto_merge_finalize.py" \
  --issue-url "${ISSUE_URL}" \
  --evidence "${TARGET_REPO_DIR}/.fullsend-runtime/auto-merge-evidence.json" \
  --result "${RESULT_FILE}" \
  --gate-script "${SCRIPT_DIR}/auto_merge_gate.py"
