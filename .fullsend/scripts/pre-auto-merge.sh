#!/usr/bin/env bash
# Collect deterministic, secret-free merge evidence on the trusted runner.

set -euo pipefail

: "${GH_TOKEN:?GH_TOKEN must be set}"
: "${ISSUE_URL:?ISSUE_URL must be set}"
: "${TARGET_REPO_DIR:?TARGET_REPO_DIR must be set}"
: "${AUTO_MERGE_ALLOWED_REPO:?AUTO_MERGE_ALLOWED_REPO must be set}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EVIDENCE_DIR="${TARGET_REPO_DIR}/.fullsend-runtime"
EVIDENCE_FILE="${EVIDENCE_DIR}/auto-merge-evidence.json"
mkdir -p "${EVIDENCE_DIR}"

python3 "${SCRIPT_DIR}/auto_merge_gate.py" collect \
  --issue-url "${ISSUE_URL}" \
  --repository "${AUTO_MERGE_ALLOWED_REPO}" \
  --base-ref "${AUTO_MERGE_BASE_REF:-main}" \
  --policy-version "${AUTO_MERGE_POLICY_VERSION:-lab-v1}" \
  --required-checks "${AUTO_MERGE_REQUIRED_CHECKS:-}" \
  --allowed-paths "${AUTO_MERGE_ALLOWED_PATHS:-}" \
  --allowed-authors "${AUTO_MERGE_ALLOWED_AUTHORS:-}" \
  --output "${EVIDENCE_FILE}"

if ! jq -e '.deterministic.eligible == true' "${EVIDENCE_FILE}" >/dev/null; then
  reason=$(jq -r '.deterministic.failures | join("; ")' "${EVIDENCE_FILE}")
  if [[ -n "${FULLSEND_PRESCRIPT_OUTPUT:-}" ]]; then
    {
      printf 'skipped=true\n'
      printf 'reason=%s\n' "${reason:0:1000}"
    } >> "${FULLSEND_PRESCRIPT_OUTPUT}"
  fi
  printf 'auto-merge preflight ineligible: %s\n' "${reason}" >&2
fi
