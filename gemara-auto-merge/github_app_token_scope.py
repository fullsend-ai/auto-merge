#!/usr/bin/env python3
"""Fixed GitHub installation-token scope check/revocation for this lab only."""

import json
import os
import sys
import urllib.request
from github_pr_evidence import NoRedirect, REPOSITORY
from policy_evaluation import require


def installation_request(path, method="GET"):
    token = os.environ.get("PILOT_ENQUEUE_TOKEN") or os.environ.get("APP_TOKEN")
    require(bool(token), "repository_app_token_required")
    require(
        path in {"/installation/repositories?per_page=100", "/installation/token"},
        "unsupported_installation_operation",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(
        "https://api.github.com" + path,
        method=method,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
        },
    )
    with opener.open(request, timeout=20) as response:
        raw = response.read(2 * 1024 * 1024 + 1)
        require(len(raw) <= 2 * 1024 * 1024, "app_scope_response_too_large")
        return response.status, json.loads(raw) if raw else None


def verify_scope():
    status, data = installation_request("/installation/repositories?per_page=100")
    require(
        status == 200
        and data.get("total_count") == 1
        and [r.get("full_name") for r in data.get("repositories", [])] == [REPOSITORY],
        "app_token_not_repository_scoped",
    )


def main():
    try:
        require(
            len(sys.argv) == 2 and sys.argv[1] in {"verify", "revoke"},
            "unsupported_installation_operation",
        )
        if sys.argv[1] == "verify":
            verify_scope()
            print("Repository-scoped lab installation token verified.")
        else:
            status, _ = installation_request("/installation/token", "DELETE")
            require(status == 204, "app_token_revocation_failed")
            print("Lab installation token revoked.")
        return 0
    except Exception:
        print("Installation token operation failed; no credential details retained.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
