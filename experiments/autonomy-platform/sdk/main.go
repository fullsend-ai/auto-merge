// Native Gemara policy evaluation. No network, forge or mutation client.
package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	gemara "github.com/gemaraproj/go-gemara"
	"io"
	"os"
	"regexp"
	"sort"
	"time"
)

type Observation struct {
	Subject   string `json:"subject_sha256"`
	Collected string `json:"collected_at"`
	Trusted   bool   `json:"trusted_source"`
	Value     any    `json:"value"`
}
type Request struct {
	Version      string                           `json:"schema_version"`
	SubjectHash  string                           `json:"subject_sha256"`
	AsOf         string                           `json:"as_of"`
	Purpose      string                           `json:"purpose"`
	Repository   string                           `json:"repository"`
	RootPolicy   string                           `json:"root_policy"`
	Catalogs     map[string]gemara.ControlCatalog `json:"catalogs"`
	Policies     map[string]gemara.Policy         `json:"policies"`
	Observations map[string]Observation           `json:"observations"`
}
type Payload struct {
	gemara.EvidenceCollector
	Request Request
	Binding binding
}
type Row struct {
	ID          string `json:"id"`
	Policy      string `json:"policy"`
	Plan        string `json:"plan"`
	Requirement string `json:"requirement"`
	State       string `json:"state"`
	Reason      string `json:"reason"`
}

func canonical(v any) []byte { b, _ := json.Marshal(v); return b }

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
	b, r := p.Binding, p.Request
	o, ok := r.Observations[b.Control.Id]
	if !ok {
		return gemara.Unknown, "missing", gemara.Undetermined
	}
	now, e := time.Parse(time.RFC3339, r.AsOf)
	observed, e2 := time.Parse(time.RFC3339, o.Collected)
	if e != nil || e2 != nil || o.Subject != r.SubjectHash || !o.Trusted {
		return gemara.Unknown, "untrusted_or_wrong_subject", gemara.Undetermined
	}
	age := now.Sub(observed).Seconds()
	if age < 0 || age > float64(b.MaximumAge) {
		return gemara.Unknown, "stale_or_future", gemara.Undetermined
	}
	passed := false
	switch b.Control.Id {
	case "AM-RISK":
		v, ok := o.Value.(float64)
		if !ok || v < 0 || v > 5 || v != float64(int(v)) {
			return gemara.Unknown, "invalid_value", gemara.Undetermined
		}
		passed = v <= float64(b.MaximumRisk)
	case "AM-CLASS":
		v, ok := o.Value.(string)
		if !ok {
			return gemara.Unknown, "invalid_value", gemara.Undetermined
		}
		for _, x := range b.Classes {
			passed = passed || v == x
		}
	default:
		v, ok := o.Value.(bool)
		if !ok {
			return gemara.Unknown, "invalid_value", gemara.Undetermined
		}
		passed = v
	}
	hash := sha256.Sum256(canonical(o))
	var ev gemara.Evidence
	_ = json.Unmarshal(canonical(map[string]any{"id": b.Control.Id, "type": "normalized-observation", "collected-at": o.Collected, "payload": o, "source": map[string]any{"reference-id": "observations", "coordinate": b.Control.Id, "digest": "sha256:" + hex.EncodeToString(hash[:])}}), &ev)
	p.AddEvidence(ev)
	if passed {
		return gemara.Passed, "satisfied", gemara.Undetermined
	}
	return gemara.Failed, "condition_failed", gemara.Undetermined
}
func evaluate(r Request) (map[string]any, error) {
	bindings, err := resolve(r)
	if err != nil {
		return nil, err
	}
	evaluations := []*gemara.ControlEvaluation{}
	byControl := map[string]*gemara.ControlEvaluation{}
	rows := []Row{}
	for _, b := range bindings {
		key := b.Catalog + "/" + b.Control.Id
		c := byControl[key]
		if c == nil {
			c = &gemara.ControlEvaluation{Name: b.Control.Title, Control: gemara.EntryMapping{ReferenceId: b.Catalog, EntryId: b.Control.Id}}
			byControl[key] = c
			evaluations = append(evaluations, c)
		}
		payload := &Payload{Request: r, Binding: b}
		a := c.AddAssessment(b.Requirement.Id, b.Requirement.Text, b.Requirement.Applicability, []gemara.AssessmentStep{gemara.NamedStep(b.Method, func(any) (gemara.Result, string, gemara.ConfidenceLevel) { return check(payload) })})
		a.Requirement.ReferenceId = b.Catalog
		a.Plan = &gemara.EntryMapping{ReferenceId: b.Policy, EntryId: b.Plan.Id}
		// Execute only this plan's assessment. Control aggregation below includes all siblings.
		a.Run(payload)
		state := "unknown"
		if a.Result == gemara.Passed {
			state = "passed"
		}
		if a.Result == gemara.Failed {
			state = "failed"
		}
		rows = append(rows, Row{b.Control.Id, b.Policy, b.Plan.Id, b.Requirement.Id, state, a.Message})
	}
	aggregate := gemara.NotRun
	for _, c := range evaluations {
		c.Result = gemara.NotRun
		for _, a := range c.AssessmentLogs {
			c.Result = gemara.UpdateAggregateResult(c.Result, a.Result)
		}
		c.Message = "Native Gemara assessments; shadow evaluation only"
		aggregate = gemara.UpdateAggregateResult(aggregate, c.Result)
	}
	sort.Slice(rows, func(i, j int) bool { return rows[i].ID+rows[i].Policy < rows[j].ID+rows[j].Policy })
	decision := "eligible"
	for _, row := range rows {
		if row.State != "passed" {
			decision = "hold"
		}
	}
	references := []map[string]any{}
	for id, catalog := range r.Catalogs {
		references = append(references, map[string]any{"id": id, "title": catalog.Title, "version": catalog.Metadata.Version})
	}
	for id, policy := range r.Policies {
		references = append(references, map[string]any{"id": id, "title": policy.Title, "version": policy.Metadata.Version})
	}
	sort.Slice(references, func(i, j int) bool { return references[i]["id"].(string) < references[j]["id"].(string) })
	requestHash := sha256.Sum256(canonical(r))
	log := map[string]any{
		"metadata": map[string]any{"id": "evaluation-" + hex.EncodeToString(requestHash[:]), "type": "EvaluationLog", "gemara-version": "1.5.0", "description": "Native policy-plan evaluation of revision-bound normalized evidence", "mapping-references": references, "author": map[string]any{"id": "autonomy-evaluator", "name": "Auto-Merge Gemara evaluator", "type": "Software"}},
		"target":   map[string]any{"id": "sha256:" + r.SubjectHash, "name": r.Repository + "/" + r.Purpose, "type": "Software"},
		"result":   aggregate, "evaluations": evaluations,
	}
	return map[string]any{"engine": "gemara", "sdk_schema_version": gemara.SchemaVersion, "decision": decision, "assessments": rows, "evaluation_log": log, "mutation_permitted": false}, nil
}
func run() error {
	raw, err := io.ReadAll(io.LimitReader(os.Stdin, 1024*1024+1))
	if err != nil || len(raw) > 1024*1024 {
		return fmt.Errorf("invalid_request")
	}
	d := json.NewDecoder(bytes.NewReader(raw))
	if keys(d, 0) != nil {
		return fmt.Errorf("invalid_request")
	}
	if _, err := d.Token(); err != io.EOF {
		return fmt.Errorf("invalid_request")
	}
	if len(os.Args) != 1 {
		return fmt.Errorf("invalid_arguments")
	}
	var r Request
	d = json.NewDecoder(bytes.NewReader(raw))
	d.DisallowUnknownFields()
	if d.Decode(&r) != nil || d.Decode(new(any)) != io.EOF || r.Version != "gemara-evaluation/v1" || !regexp.MustCompile(`^[a-f0-9]{64}$`).MatchString(r.SubjectHash) || len(r.Observations) > 40 {
		return fmt.Errorf("invalid_request")
	}
	if _, e := time.Parse(time.RFC3339, r.AsOf); e != nil {
		return fmt.Errorf("invalid_request")
	}
	if !regexp.MustCompile(`^(fullsend-ai|example)/[a-z0-9-]{1,50}$`).MatchString(r.Repository) {
		return fmt.Errorf("invalid_request")
	}
	for id, o := range r.Observations {
		if !regexp.MustCompile(`^[A-Z][A-Z0-9-]{0,31}$`).MatchString(id) || !regexp.MustCompile(`^[a-f0-9]{64}$`).MatchString(o.Subject) {
			return fmt.Errorf("invalid_observation")
		}
		if _, e := time.Parse(time.RFC3339, o.Collected); e != nil {
			return fmt.Errorf("invalid_observation")
		}
		switch v := o.Value.(type) {
		case nil, bool:
		case float64:
			if v < 0 || v > 100 || v != float64(int(v)) {
				return fmt.Errorf("invalid_observation")
			}
		case string:
			if !regexp.MustCompile(`^[A-Za-z0-9 -]{1,60}$`).MatchString(v) {
				return fmt.Errorf("invalid_observation")
			}
		default:
			return fmt.Errorf("invalid_observation")
		}
	}
	result, err := evaluate(r)
	if err != nil {
		return err
	}
	return json.NewEncoder(os.Stdout).Encode(result)
}
func main() {
	if err := run(); err != nil {
		code := err.Error()
		if !regexp.MustCompile(`^[a-z_]{1,80}$`).MatchString(code) {
			code = "invalid_policy_or_evidence"
		}
		_ = json.NewEncoder(os.Stdout).Encode(map[string]any{"error": code, "decision": "hold", "mutation_permitted": false})
		os.Exit(2)
	}
}
