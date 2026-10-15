// A local assessment adapter. No forge, model, shell or mutation client.
package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"regexp"
	"sort"
	"time"

	gemara "github.com/gemaraproj/go-gemara"
)

type Rule struct {
	ID       string `json:"id"`
	Kind     string `json:"kind"`
	Expected any    `json:"expected"`
}
type Observation struct {
	Subject   string `json:"subject_sha256"`
	Collected string `json:"collected_at"`
	Trusted   bool   `json:"trusted_source"`
	Value     any    `json:"value"`
}
type Request struct {
	Version      string                 `json:"schema_version"`
	SubjectHash  string                 `json:"subject_sha256"`
	AsOf         string                 `json:"as_of"`
	MaximumAge   int                    `json:"maximum_age_seconds"`
	Rules        []Rule                 `json:"rules"`
	Observations map[string]Observation `json:"observations"`
}
type Payload struct {
	gemara.EvidenceCollector
	Request Request
	Rule    Rule
	Reason  string
}
type Row struct {
	ID     string `json:"id"`
	State  string `json:"state"`
	Reason string `json:"reason"`
}

func canonical(v any) []byte {
	b, _ := json.Marshal(v)
	return b
}

// Reject duplicate keys and deeply nested input before decoding typed records.
func keys(d *json.Decoder, depth int) error {
	if depth > 32 {
		return fmt.Errorf("invalid_request")
	}
	token, err := d.Token()
	if err != nil {
		return err
	}
	delimiter, ok := token.(json.Delim)
	if !ok {
		return nil
	}
	if delimiter == '{' {
		seen := map[string]bool{}
		for d.More() {
			key, err := d.Token()
			if err != nil {
				return err
			}
			name, ok := key.(string)
			if !ok || seen[name] {
				return fmt.Errorf("invalid_request")
			}
			seen[name] = true
			if err := keys(d, depth+1); err != nil {
				return err
			}
		}
	} else if delimiter == '[' {
		for d.More() {
			if err := keys(d, depth+1); err != nil {
				return err
			}
		}
	} else {
		return fmt.Errorf("invalid_request")
	}
	_, err = d.Token()
	return err
}

func check(p *Payload) (gemara.Result, string, gemara.ConfidenceLevel) {
	r := p.Request
	o, ok := r.Observations[p.Rule.ID]
	if !ok {
		return gemara.Unknown, "missing", gemara.Undetermined
	}
	now, e := time.Parse(time.RFC3339, r.AsOf)
	observed, e2 := time.Parse(time.RFC3339, o.Collected)
	if e != nil || e2 != nil || o.Subject != r.SubjectHash || !o.Trusted {
		return gemara.Unknown, "untrusted_or_wrong_subject", gemara.Undetermined
	}
	age := now.Sub(observed).Seconds()
	if age < 0 || age > float64(r.MaximumAge) {
		return gemara.Unknown, "stale_or_future", gemara.Undetermined
	}
	passed := false
	switch p.Rule.Kind {
	case "boolean":
		v, ok := o.Value.(bool)
		if !ok {
			return gemara.Unknown, "invalid_value", gemara.Undetermined
		}
		passed = v
	case "maximum":
		v, ok := o.Value.(float64)
		limit, ok2 := p.Rule.Expected.(float64)
		if !ok || !ok2 || v < 0 || v != float64(int64(v)) {
			return gemara.Unknown, "invalid_value", gemara.Undetermined
		}
		passed = v <= limit
	case "equals":
		if _, ok := o.Value.(string); !ok {
			return gemara.Unknown, "invalid_value", gemara.Undetermined
		}
		passed = bytes.Equal(canonical(o.Value), canonical(p.Rule.Expected))
	case "member":
		v, ok := o.Value.(string)
		choices, ok2 := p.Rule.Expected.([]any)
		if !ok || !ok2 {
			return gemara.Unknown, "invalid_value", gemara.Undetermined
		}
		for _, choice := range choices {
			if choice == v {
				passed = true
			}
		}
	default:
		return gemara.Unknown, "unsupported_rule", gemara.Undetermined
	}
	raw := canonical(o)
	hash := sha256.Sum256(raw)
	// The SDK captures this evidence from the assessment payload automatically.
	var ev gemara.Evidence
	_ = json.Unmarshal(canonical(map[string]any{"id": p.Rule.ID, "type": "normalized-observation", "collected-at": o.Collected, "payload": o, "source": map[string]any{"reference-id": "observations", "coordinate": p.Rule.ID, "digest": "sha256:" + hex.EncodeToString(hash[:])}}), &ev)
	p.AddEvidence(ev)
	if passed {
		return gemara.Passed, "satisfied", gemara.Undetermined
	}
	return gemara.Failed, "condition_failed", gemara.Undetermined
}

func run() error {
	raw, err := io.ReadAll(io.LimitReader(os.Stdin, 1024*1024+1))
	if err != nil || len(raw) > 1024*1024 {
		return fmt.Errorf("invalid_request")
	}
	keyDecoder := json.NewDecoder(bytes.NewReader(raw))
	if keys(keyDecoder, 0) != nil {
		return fmt.Errorf("invalid_request")
	}
	if _, err := keyDecoder.Token(); err != io.EOF {
		return fmt.Errorf("invalid_request")
	}
	if len(os.Args) != 1 {
		return fmt.Errorf("invalid_arguments")
	}
	var r Request
	d := json.NewDecoder(bytes.NewReader(raw))
	d.DisallowUnknownFields()
	if d.Decode(&r) != nil || d.Decode(new(any)) != io.EOF || r.Version != "adapter-request/v1" || len(r.Rules) == 0 || len(r.Rules) > 40 || r.MaximumAge < 1 || r.MaximumAge > 600 || len(r.Observations) > 40 {
		return fmt.Errorf("invalid_request")
	}
	if _, err := time.Parse(time.RFC3339, r.AsOf); err != nil {
		return fmt.Errorf("invalid_request")
	}
	if !regexp.MustCompile(`^[a-f0-9]{64}$`).MatchString(r.SubjectHash) {
		return fmt.Errorf("invalid_request")
	}
	// Requests are also strictly validated by the host contract before this adapter.
	rows := []Row{}
	logs := []*gemara.ControlEvaluation{}
	aggregate := gemara.NotRun
	seen := map[string]bool{}
	for _, rule := range r.Rules {
		if !regexp.MustCompile(`^[A-Z][A-Z0-9-]{0,31}$`).MatchString(rule.ID) || seen[rule.ID] {
			return fmt.Errorf("invalid_request")
		}
		seen[rule.ID] = true
		payload := &Payload{Request: r, Rule: rule}
		c := &gemara.ControlEvaluation{Name: rule.ID, Control: gemara.EntryMapping{ReferenceId: "platform-controls", EntryId: rule.ID}}
		a := c.AddAssessment(rule.ID+"-1", "Assess one normalized observation", []string{"lab"}, []gemara.AssessmentStep{gemara.NamedStep("assess-normalized-observation", func(v any) (gemara.Result, string, gemara.ConfidenceLevel) { return check(v.(*Payload)) })})
		a.Requirement.ReferenceId = "platform-controls"
		a.Plan = &gemara.EntryMapping{ReferenceId: "platform-policy", EntryId: rule.ID + "-plan"}
		c.Evaluate(payload, []string{"lab"})
		state := "unknown"
		if c.Result == gemara.Passed {
			state = "passed"
		}
		if c.Result == gemara.Failed {
			state = "failed"
		}
		rows = append(rows, Row{rule.ID, state, a.Message})
		logs = append(logs, c)
		aggregate = gemara.UpdateAggregateResult(aggregate, c.Result)
	}
	sort.Slice(rows, func(i, j int) bool { return rows[i].ID < rows[j].ID })
	decision := "hold"
	all := true
	for _, row := range rows {
		all = all && row.State == "passed"
	}
	if all {
		decision = "eligible"
	}
	return json.NewEncoder(os.Stdout).Encode(map[string]any{"adapter": "gemara-sdk", "sdk_schema_version": gemara.SchemaVersion, "decision": decision, "assessments": rows, "sdk_evaluations": logs, "sdk_aggregate": aggregate, "mutation_permitted": false})
}
func main() {
	if err := run(); err != nil {
		fmt.Println(`{"error":"invalid_request","decision":"hold","mutation_permitted":false}`)
		os.Exit(2)
	}
}
