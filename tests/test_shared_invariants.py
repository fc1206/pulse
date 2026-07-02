"""Cross-repo identity tripwire.

Nine scripts are maintained functionally identical between Pulse (the template) and
the live internal fork, in two tiers:

- "files" (byte-pinned): render_report.py, score_axes.py, plan_run.py,
  check_run_health.py, validate_digest.py, notify_slack.py, send_report.py,
  heartbeat.py must be byte-for-byte identical in both repos.
- "normalized" (comment-tolerant): validate_merge.py may differ in comments and
  docstrings only (the live internal fork keeps its incident-memory comments); its
  functional code — source parsed with ast, docstrings stripped, re-unparsed — is
  pinned by hash.

The invariant historically lived only in prose, so a one-sided edit (e.g. an XSS fix
in render_report.py) could land in one repo with both CIs green and no drift signal.
This test pins each shared file against tests/shared_manifest.json. Editing a shared
file fails CI until you update the manifest — which is the moment to mirror the change
(and the new hash) into the OTHER repo. shared_manifest.json must be kept IDENTICAL
across both repos; a divergence between the two repos' manifests means the shared
files have drifted.
"""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((Path(__file__).parent / "shared_manifest.json").read_text(encoding="utf-8"))


def normalized_sha256(path: Path) -> str:
    """Hash of the functional source only: comments are dropped by the parser,
    docstrings are stripped from every module/class/function body, and the AST is
    re-unparsed so formatting differences also wash out."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                node.body = body[1:] or [ast.Pass()]
    return hashlib.sha256(ast.unparse(tree).encode("utf-8")).hexdigest()


def test_shared_files_match_manifest():
    mismatched = []
    for name, expected in MANIFEST["files"].items():
        actual = hashlib.sha256((ROOT / "scripts" / name).read_bytes()).hexdigest()
        if actual != expected:
            mismatched.append(f"{name}: manifest {expected[:12]}… != file {actual[:12]}…")
    assert not mismatched, (
        "Shared-file drift — update tests/shared_manifest.json AND mirror the change into the "
        "other repo (keep both repos' manifests identical):\n  - " + "\n  - ".join(mismatched)
    )


def test_normalized_shared_files_match_manifest():
    mismatched = []
    for name, expected in MANIFEST["normalized"].items():
        actual = normalized_sha256(ROOT / "scripts" / name)
        if actual != expected:
            mismatched.append(f"{name}: manifest {expected[:12]}… != normalized {actual[:12]}…")
    assert not mismatched, (
        "Functional drift in a comment-tolerant shared file — only comments/docstrings may "
        "differ between the repos. Update tests/shared_manifest.json AND mirror the functional "
        "change into the other repo:\n  - " + "\n  - ".join(mismatched)
    )
