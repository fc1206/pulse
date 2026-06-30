"""Cross-repo identity tripwire.

Four scripts are maintained byte-identical between Pulse (the template) and astell-radar
(the live fork): render_report.py, score_axes.py, plan_run.py, check_run_health.py. The
invariant has historically lived only in prose, so a one-sided edit (e.g. an XSS fix in
render_report.py) could land in one repo with both CIs green and no drift signal.

This test pins each shared file's sha256 against tests/shared_manifest.json. Editing a
shared file fails CI until you update the manifest — which is the moment to mirror the
change (and the new hash) into the OTHER repo. shared_manifest.json must be kept IDENTICAL
across both repos; a divergence between the two repos' manifests means the shared files
have drifted.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((Path(__file__).parent / "shared_manifest.json").read_text(encoding="utf-8"))


def test_shared_files_match_manifest():
    mismatched = []
    for name, expected in MANIFEST.items():
        actual = hashlib.sha256((ROOT / "scripts" / name).read_bytes()).hexdigest()
        if actual != expected:
            mismatched.append(f"{name}: manifest {expected[:12]}… != file {actual[:12]}…")
    assert not mismatched, (
        "Shared-file drift — update tests/shared_manifest.json AND mirror the change into the "
        "other repo (keep both repos' manifests identical):\n  - " + "\n  - ".join(mismatched)
    )
