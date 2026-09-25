#!/usr/bin/env bash
# Collect secret-free semantic evidence on the trusted runner.

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
  --mode "${AUTO_MERGE_MODE:-observe}" \
  --semantic-provider "${AUTO_MERGE_SEMANTIC_PROVIDER:-fullsend-review-agent}" \
  --semantic-reviewer "${AUTO_MERGE_SEMANTIC_REVIEWER:-}" \
  --review-attestation-file "${AUTO_MERGE_REVIEW_ATTESTATION_FILE:-}" \
  --risk-assessment-producer "${AUTO_MERGE_RISK_ASSESSMENT_PRODUCER:-}" \
  --artifact-correlation-minutes "${AUTO_MERGE_ARTIFACT_CORRELATION_MINUTES:-1}" \
  --maximum-unattended-risk "${AUTO_MERGE_MAXIMUM_UNATTENDED_RISK:-moderate}" \
  --human-signal-associations "${AUTO_MERGE_HUMAN_SIGNAL_ASSOCIATIONS:-OWNER,MEMBER,COLLABORATOR}" \
  --review-quality-mode "${AUTO_MERGE_REVIEW_QUALITY_MODE:-off}" \
  --review-quality-minimum-score "${AUTO_MERGE_REVIEW_QUALITY_MINIMUM_SCORE:-0.98}" \
  --review-quality-minimum-samples "${AUTO_MERGE_REVIEW_QUALITY_MINIMUM_SAMPLES:-50}" \
  --review-quality-file "${AUTO_MERGE_REVIEW_QUALITY_FILE:-}" \
  --custom-instructions "${AUTO_MERGE_CUSTOM_INSTRUCTIONS:-}" \
  --output "${EVIDENCE_FILE}"

if ! jq -e '.prerequisites.ready_for_semantic_evaluation == true' "${EVIDENCE_FILE}" >/dev/null; then
  # Keep this a single line: FULLSEND_PRESCRIPT_OUTPUT is a line-oriented
  # key=value protocol. The evidence file retains the full structured checks;
  # this compact rendering keeps only the actionable blockers visible.
  failed=$(jq -r '[.prerequisites.checks[] | select(.status == "fail") | "• ❌ " + .label] | join(" ")' "${EVIDENCE_FILE}")
  # The Fullsend status comment renders `reason=` as one sanitized line, not a
  # Markdown block. Show only actionable blockers here; the complete ordered
  # pass/N-A/fail array remains available in auto_merge_checks for the agent
  # and full receipt.
  reason="${failed:-• ❌ Semantic prerequisites are not ready}"
  reason="${reason:0:1000}"
  checks_json=$(jq -c '.prerequisites.checks' "${EVIDENCE_FILE}")
  if [[ -n "${FULLSEND_PRESCRIPT_OUTPUT:-}" ]]; then
    {
      printf 'skipped=true\n'
      printf 'reason=%s\n' "${reason:0:1000}"
      printf 'auto_merge_checks=%s\n' "${checks_json:0:100000}"
    } >> "${FULLSEND_PRESCRIPT_OUTPUT}"
  fi
  printf 'auto-merge semantic prerequisites not ready: %s\n' "${reason}" >&2
fi
