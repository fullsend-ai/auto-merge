"""Read one native Review artifact from authenticated, pinned Actions execution."""

import hashlib
import io
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from fullsend_review_evidence import unique_object
from policy_evaluation import ROOT, InputError, load, require
from review_evidence_contract import PublicationProof, consume, validate

BASE = "repos/fullsend-ai/auto-merge/"
LOCK = ".fullsend/vendor-evidence-lock.json"


def enabled(tree):
    return any(x.get("path") == LOCK for x in (tree or {}).get("tree", []))


def decode_artifact(raw, metadata):
    require(len(raw) <= 256 * 1024, "native_artifact_oversized")
    require(
        metadata.get("digest") == "sha256:" + hashlib.sha256(raw).hexdigest(),
        "native_artifact_digest_mismatch",
    )
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            files = archive.infolist()
            require(
                len(files) == 1
                and files[0].filename == "fullsend-review-evidence.json"
                and files[0].file_size <= 128 * 1024
                and not files[0].is_dir(),
                "native_artifact_layout_invalid",
            )
            record = json.loads(archive.read(files[0]), object_pairs_hook=unique_object)
        validate(record)
        return record
    except InputError:
        raise
    except Exception as exc:
        raise InputError("native_artifact_invalid") from exc


def download(artifact_id, maximum_bytes=256 * 1024):
    require(
        type(maximum_bytes) is int and 0 < maximum_bytes <= 2 * 1024 * 1024,
        "native_download_limit_invalid",
    )
    require(
        type(artifact_id) is int and 0 < artifact_id < 10**15,
        "native_artifact_id_invalid",
    )

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args):
            return None

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "gemara-native-review-consumer",
    }
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    url = "https://api.github.com/" + BASE + f"actions/artifacts/{artifact_id}/zip"
    try:
        try:
            response = opener.open(
                urllib.request.Request(url, headers=headers), timeout=20
            )
        except urllib.error.HTTPError as exc:
            location = exc.headers.get("Location", "")
            status = exc.code
            exc.close()
            require(status == 302, "native_artifact_download_failed")
            parsed = urllib.parse.urlsplit(location)
            require(
                parsed.scheme == "https"
                and parsed.hostname is not None
                and parsed.hostname.endswith(".blob.core.windows.net")
                and parsed.port in {None, 443}
                and parsed.username is None
                and parsed.password is None,
                "native_artifact_redirect_refused",
            )
            # The installation token is NEVER forwarded to the signed blob URL.
            response = opener.open(
                urllib.request.Request(
                    location, headers={"User-Agent": "gemara-native-review-consumer"}
                ),
                timeout=20,
            )
        with response:
            raw = response.read(maximum_bytes + 1)
        require(len(raw) <= maximum_bytes, "native_artifact_oversized")
        return raw
    except InputError:
        raise
    except Exception as exc:
        raise InputError("native_artifact_download_failed") from exc


def blobs(tree):
    require(
        isinstance(tree, dict)
        and not tree.get("truncated")
        and isinstance(tree.get("tree"), list),
        "native_host_tree_incomplete",
    )
    return {x["path"]: x["sha"] for x in tree["tree"] if x.get("type") == "blob"}


def host_sources(client, current_tree, configuration):
    lock_path = ROOT.parent / LOCK
    lock = load(lock_path)
    entries = lock["host_files"]
    require(
        isinstance(entries, list)
        and all(
            isinstance(x, dict) and set(x) == {"path", "blob_sha1"} for x in entries
        ),
        "native_host_lock_invalid",
    )
    expected = {x["path"]: x["blob_sha1"] for x in entries}
    require(len(expected) == len(entries), "native_host_lock_invalid")
    require(
        lock["schema_version"]
        in {"vendored-review-host/v1", "review-post-script-host/v1"}
        and isinstance(expected, dict)
        and len(expected) >= 10,
        "native_host_lock_invalid",
    )
    raw = lock_path.read_bytes()
    expected = dict(
        expected,
        **{
            LOCK: hashlib.sha1(
                b"blob " + str(len(raw)).encode() + b"\0" + raw
            ).hexdigest()
        },
    )
    current = blobs(current_tree)
    original = blobs(client.get(BASE + f"git/trees/{configuration}?recursive=1"))
    require(
        all(
            current.get(path) == value == original.get(path)
            for path, value in expected.items()
        ),
        "native_host_source_changed",
    )
    if lock["schema_version"] == "review-post-script-host/v1":
        require(
            all(
                path not in current and path not in original
                for path in [".fullsend/bin/fullsend", "bin/fullsend"]
            ),
            "unexpected_vendored_binary",
        )
        return load(ROOT.parent / ".fullsend/review-evidence-producer.json")
    return load(ROOT.parent / ".fullsend/evidence-build.json")


def verify_record(client, current_tree, pr, run, artifact, raw, verify_context, as_of):
    require(
        run.get("status") == "completed"
        and run.get("conclusion") == "success"
        and run.get("path") == ".github/workflows/fullsend.yaml"
        and run.get("workflow_id") == 365189947
        and (run.get("repository") or {}).get("full_name") == "fullsend-ai/auto-merge"
        and (run.get("head_repository") or {}).get("full_name")
        == "fullsend-ai/auto-merge",
        "native_run_unverified",
    )
    require(
        artifact.get("name") == "fullsend-review-evidence-" + str(run["run_attempt"])
        and artifact.get("expired") is False,
        "native_artifact_attempt_mismatch",
    )
    record = decode_artifact(raw, artifact)
    s, p = record["subject"], record["producer"]
    require(
        s["pull_request"] == pr["number"]
        and s["head_sha"] == pr["head"]["sha"]
        and s["base_sha"] == pr["base"]["sha"]
        and p["run_id"] == run["id"]
        and p["run_attempt"] == run["run_attempt"],
        "native_review_subject_changed",
    )
    build = host_sources(client, current_tree, s["configuration_sha"])
    post_script = record["schema_version"] == "fullsend-review-evidence/v2"
    identity_field = "publisher_sha256" if post_script else "overlay_sha256"
    require(
        p["fullsend_commit"] == build["source_commit"]
        and p[identity_field] == build.get(identity_field)
        and (
            not post_script
            or build.get("schema_version") == "review-post-script-producer/v1"
        ),
        "native_producer_identity_mismatch",
    )
    references = run.get("referenced_workflows")
    require(
        isinstance(references, list)
        and len(references) == 1
        and references[0].get("sha") == build["source_commit"]
        and references[0].get("path")
        == (
            "fullsend-ai/fullsend/.github/workflows/reusable-dispatch.yml@"
            + build["source_commit"]
        ),
        "native_workflow_reference_unverified",
    )
    require(
        verify_context(run, s)
        and client.get(BASE + f"actions/runs/{run['id']}") == run,
        "native_run_context_changed",
    )
    proof = PublicationProof(
        s, p, record["payload_sha256"], run["status"], run["conclusion"], True
    )
    result = consume(record, s, proof, as_of)
    require(result["reason"] == "contract_verified", result["reason"])
    return dict(
        result,
        run_id=run["id"],
        run_attempt=run["run_attempt"],
        artifact_id=artifact["id"],
        subject=s,
    )


def observe(client, current_tree, pr, verify_context, as_of, fetch=download):
    unknown = {
        "values": {"AM-REVIEW": None, "AM-FINDINGS": None, "AM-RISK": None},
        "merge_authority": False,
    }
    try:
        runs = client.pages(
            BASE
            + "actions/workflows/fullsend.yaml/runs?event=pull_request_target&head_sha="
            + pr["head"]["sha"],
            "workflow_runs",
        )
        require(isinstance(runs, list), "native_runs_unavailable")
        runs = sorted(runs, key=lambda x: x.get("id", 0), reverse=True)[:3]
        for run in runs:
            require(run.get("status") == "completed", "native_review_in_progress")
            require(
                run.get("conclusion") == "success", "native_latest_run_not_successful"
            )
            artifacts = client.pages(
                BASE + f"actions/runs/{run['id']}/artifacts", "artifacts"
            )
            require(isinstance(artifacts, list), "native_artifacts_unavailable")
            selected = [
                x
                for x in artifacts
                if x.get("name")
                == "fullsend-review-evidence-" + str(run.get("run_attempt"))
            ]
            if not selected:
                continue
            require(len(selected) == 1, "native_artifact_ambiguous")
            return verify_record(
                client,
                current_tree,
                pr,
                run,
                selected[0],
                fetch(selected[0]["id"]),
                verify_context,
                as_of,
            )
        raise InputError("native_review_artifact_missing")
    except (InputError, KeyError, TypeError, ValueError, OSError) as exc:
        reason = str(exc) if isinstance(exc, InputError) else "native_review_invalid"
        require(re.fullmatch(r"[a-z_]{1,80}", reason), "native_review_invalid")
        return dict(unknown, reason=reason)
