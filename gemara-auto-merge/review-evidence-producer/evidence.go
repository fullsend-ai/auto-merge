// Package reviewevidence is a lab-only Fullsend host publication prototype.
// It has no forge client, credentials, signing key or merge authority.
package reviewevidence

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"regexp"
	"strings"
	"time"
)

const Version = "fullsend-review-evidence/v1"

type Subject struct {
	RepositoryID  int64  `json:"repository_id"`
	Repository    string `json:"repository"`
	PR            int    `json:"pull_request"`
	Head          string `json:"head_sha"`
	Base          string `json:"base_sha"`
	Configuration string `json:"configuration_sha"`
}

type Producer struct {
	Kind     string `json:"kind"`
	Source   string `json:"fullsend_commit"`
	Overlay  string `json:"overlay_sha256"`
	Workflow string `json:"workflow_path"`
	Run      int64  `json:"run_id"`
	Attempt  int    `json:"run_attempt"`
}

type Finding struct {
	ID       string `json:"id"`
	Severity string `json:"severity"`
	Category string `json:"category"`
	Status   string `json:"status"`
}

type Risk struct {
	Score int    `json:"score"`
	Level string `json:"level"`
}

type Review struct {
	Action   string    `json:"action"`
	Findings []Finding `json:"findings"`
	Risk     *Risk     `json:"risk"`
}

type Input struct {
	Subject    Subject  `json:"subject"`
	Producer   Producer `json:"producer"`
	Issued     string   `json:"issued_at"`
	Completion string   `json:"completion"`
	Review     Review   `json:"review"`
}

var sha = regexp.MustCompile(`^[0-9a-f]{40}$`)
var hash = regexp.MustCompile(`^[0-9a-f]{64}$`)
var findingID = regexp.MustCompile(`^f_[A-Za-z0-9]{1,128}$`)
var categories = strings.Fields("api-contract api-shape architectural-conflict assertion-weakened auth-bypass backward-incompatible bidi-override breaking-api breaking-cli breaking-config breaking-schema code-organization complexity-ratio coverage-reduced data-exposure design-direction design-smell doc-style edge-case error-handling-idiom fail-open homoglyph-attack incomplete-doc incorrect-doc injection-vuln insecure-deserialization instruction-smuggling logic-error misleading-label misplaced-abstraction missing-authorization missing-deprecation missing-doc missing-test missing-version-bump mock-loosened naming-convention nil-deref off-by-one over-engineering pattern-inconsistency pattern-violation permission-expansion permission-reduction privilege-escalation prompt-injection rbac-violation role-escalation sandbox-escape scope-bundling scope-creep scope-exceeded secret-exposure split-payload ssrf stale-doc stale-reference test-inadequate test-poisoning test-removed test-weakened tier-mismatch unauthorized-change under-engineering unicode-steganography workflow-permission xss")

func knownCategory(value string) bool {
	for _, allowed := range categories {
		if value == allowed {
			return true
		}
	}
	return false
}

func oneOf(v string, values ...string) bool {
	for _, x := range values {
		if v == x {
			return true
		}
	}
	return false
}

// jsonKeys rejects duplicate keys, deep nesting and trailing JSON before decoding.
func jsonKeys(d *json.Decoder, depth int) error {
	if depth > 16 {
		return errors.New("invalid_input")
	}
	t, e := d.Token()
	if e != nil {
		return e
	}
	if v, ok := t.(json.Delim); ok {
		switch v {
		case '{':
			seen := map[string]bool{}
			for d.More() {
				k, e := d.Token()
				if e != nil {
					return e
				}
				key, ok := k.(string)
				if !ok || seen[key] {
					return errors.New("invalid_input")
				}
				seen[key] = true
				if e := jsonKeys(d, depth+1); e != nil {
					return e
				}
			}
		case '[':
			for d.More() {
				if e := jsonKeys(d, depth+1); e != nil {
					return e
				}
			}
		default:
			return errors.New("invalid_input")
		}
		_, e = d.Token()
		return e
	}
	return nil
}

// Publish projects an already validated host review into a bounded public record.
// Host metadata must come from the trusted runner, not the model or PR content.
// This record is unsigned; consumers must authenticate publication separately.
func Publish(reader io.Reader, writer io.Writer) error {
	raw, e := io.ReadAll(io.LimitReader(reader, 128*1024+1))
	if e != nil || len(raw) > 128*1024 {
		return errors.New("invalid_input")
	}
	check := json.NewDecoder(bytes.NewReader(raw))
	if jsonKeys(check, 0) != nil {
		return errors.New("invalid_input")
	}
	if _, e := check.Token(); e != io.EOF {
		return errors.New("invalid_input")
	}
	d := json.NewDecoder(bytes.NewReader(raw))
	d.DisallowUnknownFields()
	var in Input
	if d.Decode(&in) != nil {
		return errors.New("invalid_input")
	}
	s, p := in.Subject, in.Producer
	if s.Repository != "fullsend-ai/auto-merge" || s.RepositoryID != 1383516376 || s.PR < 1 || s.PR >= 1000000 || !sha.MatchString(s.Head) || !sha.MatchString(s.Base) || !sha.MatchString(s.Configuration) {
		return errors.New("invalid_subject")
	}
	if p.Kind != "fullsend-host-lab" || !sha.MatchString(p.Source) || !hash.MatchString(p.Overlay) || p.Workflow != ".github/workflows/fullsend.yaml" || p.Run < 1 || p.Run >= 1000000000000000 || p.Attempt < 1 || p.Attempt > 999999 {
		return errors.New("invalid_producer")
	}
	t, e := time.Parse("2006-01-02T15:04:05Z", in.Issued)
	if e != nil || t.Format("2006-01-02T15:04:05Z") != in.Issued || !oneOf(in.Completion, "completed", "failed", "cancelled") {
		return errors.New("invalid_completion")
	}
	if !oneOf(in.Review.Action, "approve", "request-changes", "comment", "reject") || in.Review.Findings == nil || len(in.Review.Findings) > 500 {
		return errors.New("invalid_review")
	}
	seen := map[string]bool{}
	for _, f := range in.Review.Findings {
		if !findingID.MatchString(f.ID) || seen[f.ID] || !knownCategory(f.Category) || !oneOf(f.Severity, "info", "low", "medium", "high", "critical") || !oneOf(f.Status, "open", "reclassified", "resolved_by_change", "dismissed_by_human") || f.Status == "dismissed_by_human" && oneOf(f.Severity, "high", "critical") {
			return errors.New("invalid_findings")
		}
		seen[f.ID] = true
	}
	if r := in.Review.Risk; r != nil {
		levels := []string{"low", "moderate", "elevated", "high", "critical"}
		if r.Score < 1 || r.Score > 5 || r.Level != levels[r.Score-1] {
			return errors.New("invalid_risk")
		}
	}
	// Round-trip into maps so keys sort recursively and match the consumer's
	// canonical ASCII JSON. Contract strings are all restricted to ASCII above.
	encoded, _ := json.Marshal(in)
	payload := map[string]any{}
	_ = json.Unmarshal(encoded, &payload)
	payload["schema_version"] = Version
	canonical, _ := json.Marshal(payload)
	sum := sha256.Sum256(canonical)
	payload["payload_sha256"] = hex.EncodeToString(sum[:])
	return json.NewEncoder(writer).Encode(payload)
}
