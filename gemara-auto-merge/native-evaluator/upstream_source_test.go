package main

import (
	"encoding/json"
	"github.com/goccy/go-yaml"
	"os"
	"reflect"
	"testing"
)

func TestSelectedUpstreamControlIsUnchanged(t *testing.T) {
	raw, err := os.ReadFile("../upstream/osps-baseline/OSPS-QA.yaml")
	if err != nil {
		t.Fatal(err)
	}
	var source struct {
		Controls []map[string]any `yaml:"controls"`
	}
	if err := yaml.Unmarshal(raw, &source); err != nil {
		t.Fatal(err)
	}
	var selected map[string]any
	for _, c := range source.Controls {
		if c["id"] == "OSPS-QA-03" {
			selected = c
		}
	}
	if selected == nil {
		t.Fatal("upstream control missing")
	}
	// Normalize the YAML decoder's slice representation before comparison.
	encoded, err := json.Marshal(selected)
	if err != nil {
		t.Fatal(err)
	}
	if err := json.Unmarshal(encoded, &selected); err != nil {
		t.Fatal(err)
	}
	projected, err := os.ReadFile("../upstream/osps-baseline/catalog.json")
	if err != nil {
		t.Fatal(err)
	}
	var catalog struct {
		Controls []map[string]any `json:"controls"`
	}
	if err := json.Unmarshal(projected, &catalog); err != nil {
		t.Fatal(err)
	}
	if len(catalog.Controls) != 1 || !reflect.DeepEqual(selected, catalog.Controls[0]) {
		t.Fatal("upstream control content changed")
	}
}
