package reviewevidence

import (
	"bytes"
	"encoding/json"
	"strings"
	"testing"
)

func sample() Input {
	return Input{
		Subject:  Subject{1383516376, "fullsend-ai/auto-merge", 41, strings.Repeat("a", 40), strings.Repeat("b", 40), strings.Repeat("b", 40)},
		Producer: Producer{"fullsend-host-lab", strings.Repeat("c", 40), strings.Repeat("d", 64), ".github/workflows/fullsend.yaml", 1234, 1},
		Issued:   "2026-10-16T12:00:00Z", Completion: "completed",
		Review: Review{Action: "approve", Findings: []Finding{}, Risk: &Risk{1, "low"}},
	}
}

func TestPublishAndClosedContract(t *testing.T) {
	input := sample()
	raw, _ := json.Marshal(input)
	var out bytes.Buffer
	if err := Publish(bytes.NewReader(raw), &out); err != nil {
		t.Fatal(err)
	}
	var record map[string]any
	if json.Unmarshal(out.Bytes(), &record) != nil || record["schema_version"] != Version || record["payload_sha256"] == nil {
		t.Fatal("missing contract")
	}
	for _, raw := range []string{
		`{"subject":{},"subject":{}}`,
		string(raw) + ` {}`,
		strings.Replace(string(raw), `"review":`, `"trusted":true,"review":`, 1),
		strings.Replace(string(raw), `"findings":[]`, `"findings":[],"body":"PRIVATE_SENTINEL"`, 1),
		strings.Replace(string(raw), `"score":1`, `"score":true`, 1),
	} {
		out.Reset()
		if Publish(strings.NewReader(raw), &out) == nil || out.Len() != 0 {
			t.Fatal("invalid input was published")
		}
	}
}

func TestDoesNotTreatModelConclusionAsAuthority(t *testing.T) {
	input := sample()
	input.Review.Findings = []Finding{{"f_one", "high", "auth-bypass", "open"}}
	raw, _ := json.Marshal(input)
	var out bytes.Buffer
	if Publish(bytes.NewReader(raw), &out) != nil {
		t.Fatal("must preserve adverse evidence")
	}
	if !strings.Contains(out.String(), `"status":"open"`) || strings.Contains(out.String(), "authorized") {
		t.Fatal("lost evidence or invented authorization")
	}
	input.Review.Findings[0].Status = "dismissed_by_human"
	raw, _ = json.Marshal(input)
	if Publish(bytes.NewReader(raw), &bytes.Buffer{}) == nil {
		t.Fatal("unsupported critical dismissal")
	}
}
