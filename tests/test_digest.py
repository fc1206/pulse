"""Tests for the digest linter — the anti-slop gate."""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

GOOD = """## 2026-06-15 — digest (test)

### 1. Acme pivoted into our lane
**Signal:** Acme now sells cross-tool context (https://acme.test/post).
**Why it matters:** Collides with pillar 2 in our exact ICP.
**Action:** Write the Acme battlecard and ship a positioning memo by Friday.
"""

def make_repo(tmp_path):
    root = tmp_path / "r"
    (root / "data").mkdir(parents=True)
    (root / "runs/2026-06-15").mkdir(parents=True)
    (root / "data/registry.csv").write_text(
        "domain,name,tier,cluster,status,stage,hq,founded,first_seen,last_checked,what,why_tier,evidence_url,notes\n"
        "acme.test,Acme,2,direct,active,seed,US,2024,2026-06-10,2026-06-10,x,y,https://acme.test/,\n",
        encoding="utf-8")
    (root / "data/DIGEST.md").write_text("# Digest\n\n<!-- entries below -->\n", encoding="utf-8")
    return root

def run(root, digest_text, dry=False):
    (root / "runs/2026-06-15/digest.md").write_text(digest_text, encoding="utf-8")
    args = [sys.executable, str(REPO / "scripts/validate_digest.py"),
            "--run-dir", str(root / "runs/2026-06-15"), "--root", str(root)]
    if dry:
        args.append("--dry-run")
    return subprocess.run(args, capture_output=True, text=True)

def test_good_digest_accepted_and_prepended(tmp_path):
    root = make_repo(tmp_path)
    r = run(root, GOOD)
    assert r.returncode == 0, r.stdout + r.stderr
    doc = (root / "data/DIGEST.md").read_text(encoding="utf-8")
    assert "Acme pivoted into our lane" in doc
    assert doc.index("<!-- entries below -->") < doc.index("Acme pivoted")

def test_slop_phrase_rejected(tmp_path):
    root = make_repo(tmp_path)
    bad = GOOD.replace("Collides with pillar 2", "The rapidly evolving landscape collides with pillar 2")
    r = run(root, bad)
    assert r.returncode == 1 and "slop" in r.stdout

def test_lazy_action_rejected(tmp_path):
    root = make_repo(tmp_path)
    bad = GOOD.replace("Write the Acme battlecard and ship a positioning memo by Friday.",
                       "Monitor Acme for further developments in the coming weeks.")
    r = run(root, bad)
    assert r.returncode == 1 and "monitor" in r.stdout

def test_missing_label_rejected(tmp_path):
    root = make_repo(tmp_path)
    bad = GOOD.replace("**Why it matters:** Collides with pillar 2 in our exact ICP.\n", "")
    r = run(root, bad)
    assert r.returncode == 1 and "Why it matters" in r.stdout

def test_uncited_item_rejected(tmp_path):
    root = make_repo(tmp_path)
    bad = GOOD.replace("(https://acme.test/post)", "").replace("acme.test", "somewhere")
    r = run(root, bad)
    assert r.returncode == 1 and "citation" in r.stdout

def test_no_signal_sentinel_accepted(tmp_path):
    root = make_repo(tmp_path)
    r = run(root, "## 2026-06-15 — digest (test)\n\nNO ACTIONABLE SIGNAL — four T3 infra finds, nothing clears the 2-8 week bar.\n")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "NO ACTIONABLE SIGNAL" in (root / "data/DIGEST.md").read_text(encoding="utf-8")
