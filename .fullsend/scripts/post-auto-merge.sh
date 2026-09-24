#!/usr/bin/env bash
# Validate semantic authorization, revalidate its context, and submit to SCM.

set -euo pipefail

: "${GH_TOKEN:?GH_TOKEN must be set}"
: "${ISSUE_URL:?ISSUE_URL must be set}"
: "${TARGET_REPO_DIR:?TARGET_REPO_DIR must be set}"
: "${AUTO_MERGE_ALLOWED_REPO:?AUTO_MERGE_ALLOWED_REPO must be set}"
: "${AUTO_MERGE_BASE_REF:?AUTO_MERGE_BASE_REF must be set}"
: "${AUTO_MERGE_POLICY_VERSION:?AUTO_MERGE_POLICY_VERSION must be set}"
: "${AUTO_MERGE_MODE:?AUTO_MERGE_MODE must be set}"
: "${AUTO_MERGE_RISK_ASSESSMENT_PRODUCER:?AUTO_MERGE_RISK_ASSESSMENT_PRODUCER must be set}"

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
  --semantic-provider "${AUTO_MERGE_SEMANTIC_PROVIDER:-fullsend-review-agent}" \
  --semantic-reviewer "${AUTO_MERGE_SEMANTIC_REVIEWER:-}" \
  --review-attestation-file "${AUTO_MERGE_REVIEW_ATTESTATION_FILE:-}" \
  --risk-assessment-producer "${AUTO_MERGE_RISK_ASSESSMENT_PRODUCER}" \
  --artifact-correlation-minutes "${AUTO_MERGE_ARTIFACT_CORRELATION_MINUTES:-1}" \
  --maximum-unattended-risk "${AUTO_MERGE_MAXIMUM_UNATTENDED_RISK:-moderate}" \
  --human-signal-associations "${AUTO_MERGE_HUMAN_SIGNAL_ASSOCIATIONS:-OWNER,MEMBER,COLLABORATOR}" \
  --review-quality-mode "${AUTO_MERGE_REVIEW_QUALITY_MODE:-off}" \
  --review-quality-minimum-score "${AUTO_MERGE_REVIEW_QUALITY_MINIMUM_SCORE:-0.98}" \
  --review-quality-minimum-samples "${AUTO_MERGE_REVIEW_QUALITY_MINIMUM_SAMPLES:-50}" \
  --review-quality-file "${AUTO_MERGE_REVIEW_QUALITY_FILE:-}" \
  --custom-instructions "${AUTO_MERGE_CUSTOM_INSTRUCTIONS:-}" \
  --evidence "${TARGET_REPO_DIR}/.fullsend-runtime/auto-merge-evidence.json" \
  --result "${RESULT_FILE}" \
  --gate-script "${SCRIPT_DIR}/auto_merge_gate.py"
