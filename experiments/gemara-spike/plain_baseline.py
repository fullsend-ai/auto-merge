#!/usr/bin/env python3
"""The same fixture rules without CUE execution or Gemara output serialization."""

from pathlib import Path
import argparse
import json

from engine import InputError, evaluate, resolve_policy
from run import ROOT, load


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence", type=Path, required=True)
    p.add_argument("--policy", choices=["baseline", "repository"], default="baseline")
    args = p.parse_args()
    try:
        effective = resolve_policy(
            load(ROOT / "catalog.json"),
            load(ROOT / "policies" / (args.policy + ".json")),
        )
        report = evaluate(load(args.evidence), effective)
        print(json.dumps(report, indent=2))
        return 0
    except InputError as exc:
        print(
            json.dumps(
                {"error": str(exc), "decision": "hold", "mutation_permitted": False}
            )
        )
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        print(
            json.dumps(
                {
                    "error": "invalid_input",
                    "decision": "hold",
                    "mutation_permitted": False,
                }
            )
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
