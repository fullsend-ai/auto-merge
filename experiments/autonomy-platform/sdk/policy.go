package main

import (
	"fmt"
	gemara "github.com/gemaraproj/go-gemara"
	"reflect"
	"regexp"
	"strconv"
)

type binding struct {
	Catalog     string
	Policy      string
	Control     gemara.Control
	Requirement gemara.AssessmentRequirement
	Plan        gemara.AssessmentPlan
	Method      string
	MaximumAge  int
	MaximumRisk int
	Classes     []string
}

// Method names are executable capabilities, not commands or interpreted policy prose.
var methods = map[string]string{
	"AR-RULES": "branch-rules-visible", "AR-CHECKS": "check-metadata-accessible",
	"AR-REVIEWS": "review-metadata-accessible", "AR-STATUS": "trusted-status-publisher",
	"AR-TESTS": "meaningful-testing", "AR-ISOLATION": "runtime-isolation",
	"AR-QUEUE": "verified-merge-route", "AR-HISTORY": "shadow-track-record",
	"AM-CI": "github-ci", "AM-REVIEW": "fullsend-approval", "AM-FINDINGS": "blocking-findings",
	"AM-RISK": "risk-limit", "AM-CLASS": "change-class", "AM-PROTECTED": "governed-paths",
}

func invalid(code string) error { return fmt.Errorf("%s", code) }
func has(values []string, value string) bool {
	for _, v := range values {
		if v == value {
			return true
		}
	}
	return false
}
func dimensions(d gemara.Dimensions, r Request) (bool, bool) {
	// Values within a dimension are OR; specified dimensions are AND. Missing context fails closed.
	if len(d.Users)+len(d.Geopolitical)+len(d.Sensitivity) > 0 {
		return false, false
	}
	empty := len(d.Technologies)+len(d.Groups) == 0
	return (len(d.Technologies) == 0 || has(d.Technologies, "github")) && (len(d.Groups) == 0 || has(d.Groups, r.Repository)), empty
}
func inScope(s gemara.Scope, r Request) bool {
	include, _ := dimensions(s.In, r)
	exclude, empty := dimensions(s.Out, r)
	// Unsupported out dimensions must not be interpreted as an absent exclusion.
	if len(s.Out.Users)+len(s.Out.Geopolitical)+len(s.Out.Sensitivity) > 0 {
		return false
	}
	return include && (empty || !exclude)
}
func reference(p gemara.Policy, id, version string) bool {
	count := 0
	for _, ref := range p.Metadata.MappingReferences {
		if ref.Id == id && ref.Version == version {
			count++
		}
	}
	return count == 1
}
func resolve(r Request) ([]binding, error) {
	if r.Purpose != "readiness" && r.Purpose != "candidate" {
		return nil, invalid("invalid_purpose")
	}
	if len(r.Policies) < 1 || len(r.Policies) > 8 || len(r.Catalogs) < 1 || len(r.Catalogs) > 8 {
		return nil, invalid("invalid_bundle")
	}
	safeID := regexp.MustCompile(`^[a-z0-9-]{1,64}$`)
	requirements := map[string]binding{}
	for id, cat := range r.Catalogs {
		if !safeID.MatchString(id) || cat.Metadata.Id != id || cat.Metadata.Type.String() != "ControlCatalog" || cat.Metadata.GemaraVersion != "1.5.0" || len(cat.Extends)+len(cat.Imports) > 0 {
			return nil, invalid("unsupported_catalog")
		}
		if len(cat.Controls) == 0 {
			return nil, invalid("empty_catalog")
		}
		controls := map[string]bool{}
		for _, c := range cat.Controls {
			if controls[c.Id] || methods[c.Id] == "" || len(c.AssessmentRequirements) == 0 {
				return nil, invalid("unsupported_control")
			}
			controls[c.Id] = true
			if c.State.String() != "Active" && c.State.String() != "Invalid" {
				return nil, invalid("unsupported_lifecycle")
			}
			for _, a := range c.AssessmentRequirements {
				if a.State.String() != "Active" && a.State.String() != "Invalid" {
					return nil, invalid("unsupported_lifecycle")
				}
				if _, exists := requirements[a.Id]; exists || a.Id != c.Id+"-1" {
					return nil, invalid("ambiguous_requirement")
				}
				requirements[a.Id] = binding{Catalog: id, Control: c, Requirement: a}
			}
		}
	}
	for key := range r.Observations {
		found := false
		for _, b := range requirements {
			if b.Control.Id == key && has(b.Requirement.Applicability, r.Purpose) {
				found = true
			}
		}
		if !found {
			return nil, invalid("unexpected_observation")
		}
	}
	visiting, visited := map[string]bool{}, map[string]bool{}
	order := []string{}
	var visit func(string) error
	visit = func(id string) error {
		if visiting[id] {
			return invalid("policy_import_cycle")
		}
		if visited[id] {
			return nil
		}
		p, ok := r.Policies[id]
		if !ok || !safeID.MatchString(id) || p.Metadata.Id != id || p.Metadata.Type.String() != "Policy" || p.Metadata.GemaraVersion != "1.5.0" {
			return invalid("unresolved_policy")
		}
		if !inScope(p.Scope, r) {
			return invalid("policy_scope_mismatch")
		}
		if !reflect.DeepEqual(p.ImplementationPlan, gemara.ImplementationPlan{}) || !reflect.DeepEqual(p.Risks, gemara.Risks{}) || len(p.Imports.Guidance) > 0 || len(p.Adherence.EnforcementMethods) > 0 {
			return invalid("unsupported_policy_semantics")
		}
		visiting[id] = true
		imports := map[string]bool{}
		for _, imp := range p.Imports.Policies {
			parent, ok := r.Policies[imp.ReferenceId]
			if !ok || imports[imp.ReferenceId] || !reference(p, imp.ReferenceId, parent.Metadata.Version) {
				return invalid("unresolved_policy_import")
			}
			imports[imp.ReferenceId] = true
			if err := visit(imp.ReferenceId); err != nil {
				return err
			}
		}
		for _, imp := range p.Imports.Catalogs {
			cat, ok := r.Catalogs[imp.ReferenceId]
			if !ok || imports[imp.ReferenceId] || !reference(p, imp.ReferenceId, cat.Metadata.Version) {
				return invalid("unresolved_catalog_import")
			}
			imports[imp.ReferenceId] = true
			if len(imp.Constraints)+len(imp.AssessmentRequirementModifications) > 0 {
				return invalid("unsupported_catalog_modification")
			}
			seen := map[string]bool{}
			for _, ex := range imp.Exclusions {
				if seen[ex] {
					return invalid("duplicate_exclusion")
				}
				seen[ex] = true
				found := false
				for _, c := range cat.Controls {
					found = found || c.Id == ex
				}
				if !found {
					return invalid("unknown_exclusion")
				}
			}
		}
		visiting[id] = false
		visited[id] = true
		order = append(order, id)
		return nil
	}
	if err := visit(r.RootPolicy); err != nil {
		return nil, err
	}
	if len(visited) != len(r.Policies) {
		return nil, invalid("unused_policy")
	}
	expected := map[string]bool{}
	catalogs := map[string]bool{}
	covered := map[string]bool{}
	result := []binding{}
	for _, id := range order {
		p := r.Policies[id]
		for _, imp := range p.Imports.Catalogs {
			catalogs[imp.ReferenceId] = true
			for req, b := range requirements {
				if b.Catalog == imp.ReferenceId && !has(imp.Exclusions, b.Control.Id) && has(b.Requirement.Applicability, r.Purpose) {
					expected[req] = true
				}
			}
		}
	}
	if len(catalogs) != len(r.Catalogs) {
		return nil, invalid("unused_catalog")
	}
	for _, id := range order {
		p := r.Policies[id]
		plans := map[string]bool{}
		if len(p.Adherence.EvaluationMethods) > 0 {
			return nil, invalid("unbound_policy_method")
		}
		for _, plan := range p.Adherence.AssessmentPlans {
			if plans[plan.Id] || !regexp.MustCompile(`^[a-zA-Z0-9-]{1,80}$`).MatchString(plan.Id) {
				return nil, invalid("duplicate_or_invalid_plan")
			}
			plans[plan.Id] = true
			b, ok := requirements[plan.RequirementId]
			if !ok || !reference(p, b.Catalog, r.Catalogs[b.Catalog].Metadata.Version) {
				return nil, invalid("unresolved_requirement")
			}
			if len(plan.EvaluationMethods) != 1 || plan.Frequency != "every evaluation" {
				return nil, invalid("unsupported_plan")
			}
			method := plan.EvaluationMethods[0]
			if method.Id != methods[b.Control.Id] || method.Mode.String() != "Automated" || method.Type.String() != "Intent" || !method.Required || !reflect.DeepEqual(method.Executor, gemara.Actor{}) {
				return nil, invalid("unsupported_evaluation_method")
			}
			b.Policy = id
			b.Plan = plan
			b.Method = method.Id
			b.MaximumAge = 600
			b.MaximumRisk = -1
			params := map[string]bool{}
			for _, param := range plan.Parameters {
				if params[param.Id] || len(param.AcceptedValues) == 0 {
					return nil, invalid("invalid_parameter")
				}
				params[param.Id] = true
				switch param.Id {
				case "maximum-age-seconds":
					if len(param.AcceptedValues) != 1 {
						return nil, invalid("invalid_freshness")
					}
					n, e := strconv.Atoi(param.AcceptedValues[0])
					if e != nil || n < 1 || n > 600 {
						return nil, invalid("invalid_freshness")
					}
					b.MaximumAge = n
				case "maximum-risk":
					if b.Control.Id != "AM-RISK" || len(param.AcceptedValues) != 1 {
						return nil, invalid("invalid_risk_parameter")
					}
					n, e := strconv.Atoi(param.AcceptedValues[0])
					if e != nil || n < 0 || n > 5 {
						return nil, invalid("invalid_risk_parameter")
					}
					b.MaximumRisk = n
				case "allowed-change-classes":
					if b.Control.Id != "AM-CLASS" {
						return nil, invalid("invalid_class_parameter")
					}
					seen := map[string]bool{}
					for _, v := range param.AcceptedValues {
						if seen[v] || !regexp.MustCompile(`^[a-z-]{1,30}$`).MatchString(v) {
							return nil, invalid("invalid_class_parameter")
						}
						seen[v] = true
					}
					b.Classes = param.AcceptedValues
				default:
					return nil, invalid("unsupported_parameter")
				}
			}
			if b.Control.Id == "AM-RISK" && b.MaximumRisk < 0 || b.Control.Id == "AM-CLASS" && len(b.Classes) == 0 {
				return nil, invalid("missing_parameter")
			}
			if has(b.Requirement.Applicability, r.Purpose) {
				if !expected[plan.RequirementId] {
					return nil, invalid("plan_outside_imports")
				}
				covered[plan.RequirementId] = true
				result = append(result, b)
			}
		}
	}
	if len(expected) == 0 || len(result) == 0 || len(result) > 40 {
		return nil, invalid("empty_or_large_evaluation")
	}
	for id := range expected {
		if !covered[id] {
			return nil, invalid("missing_assessment_plan")
		}
	}
	return result, nil
}
