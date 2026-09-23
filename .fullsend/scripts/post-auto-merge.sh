#!/usr/bin/env bash
# Validate model output, write a receipt, revalidate, and merge the exact head.

set -euo pipefail

: "${GH_TOKEN:?GH_TOKEN must be set}"
: "${ISSUE_URL:?ISSUE_URL must be set}"
: "${TARGET_REPO_DIR:?TARGET_REPO_DIR must be set}"
: "${AUTO_MERGE_ALLOWED_REPO:?AUTO_MERGE_ALLOWED_REPO must be set}"
: "${AUTO_MERGE_BASE_REF:?AUTO_MERGE_BASE_REF must be set}"
: "${AUTO_MERGE_POLICY_VERSION:?AUTO_MERGE_POLICY_VERSION must be set}"
: "${AUTO_MERGE_MODE:?AUTO_MERGE_MODE must be set}"
: "${AUTO_MERGE_EXECUTION_STRATEGY:?AUTO_MERGE_EXECUTION_STRATEGY must be set}"
: "${AUTO_MERGE_RISK_GATE:?AUTO_MERGE_RISK_GATE must be set}"
: "${AUTO_MERGE_ALLOWED_RISK_LEVELS:?AUTO_MERGE_ALLOWED_RISK_LEVELS must be set}"
: "${AUTO_MERGE_REQUIRED_CHECKS:?AUTO_MERGE_REQUIRED_CHECKS must be set}"
: "${AUTO_MERGE_ALLOWED_PATHS:?AUTO_MERGE_ALLOWED_PATHS must be set}"
: "${AUTO_MERGE_ALLOWED_AUTHORS:?AUTO_MERGE_ALLOWED_AUTHORS must be set}"
: "${AUTO_MERGE_ALLOWED_REVIEWERS:?AUTO_MERGE_ALLOWED_REVIEWERS must be set}"

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
  --allowed-repository "${AUTO_MERGE_ALLOWED_REPO}" \
  --base-ref "${AUTO_MERGE_BASE_REF}" \
  --policy-version "${AUTO_MERGE_POLICY_VERSION}" \
  --mode "${AUTO_MERGE_MODE}" \
  --execution-strategy "${AUTO_MERGE_EXECUTION_STRATEGY}" \
  --risk-gate "${AUTO_MERGE_RISK_GATE}" \
  --allowed-risk-levels "${AUTO_MERGE_ALLOWED_RISK_LEVELS}" \
  --required-checks "${AUTO_MERGE_REQUIRED_CHECKS}" \
  --allowed-paths "${AUTO_MERGE_ALLOWED_PATHS}" \
  --allowed-authors "${AUTO_MERGE_ALLOWED_AUTHORS}" \
  --allowed-reviewers "${AUTO_MERGE_ALLOWED_REVIEWERS}" \
  --evidence "${TARGET_REPO_DIR}/.fullsend-runtime/auto-merge-evidence.json" \
  --result "${RESULT_FILE}" \
  --gate-script "${SCRIPT_DIR}/auto_merge_gate.py"
