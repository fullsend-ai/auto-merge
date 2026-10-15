package main

import (
	"bytes"
	"encoding/json"
	gemara "github.com/gemaraproj/go-gemara"
	"testing"
)

func TestDuplicateAndDeepJSONRejected(t *testing.T) {
	for _, raw := range []string{`{"rules":[],"rules":[]}`, `{"nested":{"key":true,"key":false}}`, string(bytes.Repeat([]byte("["), 34)) + "0" + string(bytes.Repeat([]byte("]"), 34))} {
		if keys(json.NewDecoder(bytes.NewBufferString(raw)), 0) == nil {
			t.Fatal("unsafe JSON shape accepted")
		}
	}
}

func TestSDKDoesNotEraseFailedSibling(t *testing.T) {
	c := &gemara.ControlEvaluation{}
	for _, r := range []gemara.Result{gemara.Failed, gemara.Passed} {
		result := r
		c.AddAssessment("requirement", "Assess fixture", []string{"lab"}, []gemara.AssessmentStep{func(any) (gemara.Result, string, gemara.ConfidenceLevel) {
			return result, "fixture", gemara.Undetermined
		}})
	}
	c.Evaluate(nil, []string{"lab"})
	if c.Result != gemara.Failed || len(c.AssessmentLogs) != 2 || c.AssessmentLogs[1].Result != gemara.Passed {
		t.Fatal("failed sibling must survive without skipping later assessments")
	}
}
func TestDecodedSDKLogCannotPretendToReexecute(t *testing.T) {
	a, err := gemara.NewAssessment("requirement", "Assess fixture", []string{"lab"}, []gemara.AssessmentStep{gemara.NamedStep("fixture-check", func(any) (gemara.Result, string, gemara.ConfidenceLevel) {
		return gemara.Passed, "fixture", gemara.Undetermined
	})})
	if err != nil {
		t.Fatal(err)
	}
	a.Run(nil)
	data, err := json.Marshal(a)
	if err != nil {
		t.Fatal(err)
	}
	var decoded gemara.AssessmentLog
	if json.Unmarshal(data, &decoded) != nil || decoded.Run(nil) != gemara.Unknown {
		t.Fatal("recorded names are not executable checks")
	}
}
func TestSDKEmptyAssessmentDoesNotPass(t *testing.T) {
	c := &gemara.ControlEvaluation{}
	c.Evaluate(nil, []string{"lab"})
	if c.Result != gemara.NeedsReview {
		t.Fatal("no assessments must require review")
	}
}
