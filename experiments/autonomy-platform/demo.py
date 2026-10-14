#!/usr/bin/env python3
"""Exercise the policy boundary locally. No network, inference or SCM mutation."""

import copy
import json
from platform_lab import (
    ROOT,
    assess,
    documents,
    gate,
    load,
    new_output,
    observations_for,
    qualification,
    request,
    resolve,
    subject,
    source_digests,
)


def main():
    now = "2026-10-14T18:00:00Z"
    effective = resolve(
        load(ROOT / "policies/shared.json"), load(ROOT / "policies/repository.json")
    )
    ready, candidate = subject(), subject(candidate=True)
    ready_obs = observations_for(ready, effective["readiness"], now)
    observations = observations_for(candidate, effective["candidate"], now)
    out = new_output("demo")
    rows = []
    print("Synthetic platform experiment; no adapter can request a merge.")
    for adapter in ["gemara-sdk", "native-json-reference"]:
        receipt = qualification(effective, ready, now, ready_obs, adapter)
        for mode in ["off", "shadow", "light", "policy"]:
            result = gate(
                effective, candidate, now, observations, mode, receipt, adapter
            )
            rows.append({"case": mode, "adapter": adapter, "result": result})
            print(f"{adapter} / {mode}: {result['decision']}; actions=[]")
        for name in [
            "missing-review",
            "failed-ci",
            "changed-configuration",
            "expired-qualification",
            "outside-light",
            "protected-policy-change",
        ]:
            obs, who, as_of, mode = (
                copy.deepcopy(observations),
                copy.deepcopy(candidate),
                now,
                "shadow",
            )
            if name == "missing-review":
                del obs["AM-REVIEW"]
            elif name == "failed-ci":
                obs["AM-CI"]["value"] = False
            elif name == "changed-configuration":
                who["configuration_sha256"] = "d" * 64
            elif name == "expired-qualification":
                as_of = "2026-10-14T18:10:01Z"
            elif name == "outside-light":
                obs["AM-CLASS"]["value"] = "documentation"
                mode = "light"
            else:
                obs["AM-PROTECTED"]["value"] = False
            result = gate(effective, who, as_of, obs, mode, receipt, adapter)
            assert result["decision"] == "hold"
            rows.append({"case": name, "adapter": adapter, "result": result})
            print(f"{adapter} / {name}: hold")
    req = request(effective, "candidate", candidate, observations, now)
    sdk = assess(req, "gemara-sdk")
    package = {
        "provenance": "synthetic",
        "source_digests": source_digests(),
        "effective_policy": effective,
        "request": req,
        "gemara": documents(req, sdk),
        "cases": rows,
        "sdk_build": load(ROOT / "build-lock.json"),
        "mutation_permitted": False,
    }
    (out / "results.json").write_text(json.dumps(package, indent=2) + "\n")
    print(
        "20 mode/adversarial cases recorded; SDK output passed official schema validation."
    )
    print("Local output: " + str(out.relative_to(ROOT)))


if __name__ == "__main__":
    main()
