"""Deterministic tests for the radar plumbing.

Philosophy: the LLM only writes runs/<date>/*.json; these tests pin down everything
after that point, so swapping to a cheaper model can't corrupt the system of record.
The low-footprint fixture is the regression: a low-footprint, adjacent-vocabulary company
must merge cleanly once the model emits it.
"""
import csv
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"

SEED_REGISTRY = (
    "domain,name,tier,cluster,status,stage,hq,founded,first_seen,last_checked,"
    "what,why_tier,evidence_url,notes\n"
    'alpha.example,Alpha,1,direct,active,series-b,"US",2019,2026-06-10,2026-06-10,'
    '"Direct competitor","Same lane",https://alpha.example/,\n'
    'beta.example,Beta,2,data-intel,active,series-a,"US",2021,2026-06-10,2026-06-10,'
    '"Adjacent tool","One pivot away",https://beta.example/,\n'
)

SEED_LANDSCAPE = (
    "# Landscape\n\n**Last scan:** 2026-06-10 (baseline)\n\n## Changelog\n\n"
    "### 2026-06-10 — Baseline established\nSeed.\n"
)

SEED_QUERIES = (
    "# Queries\n\n## Block A: self\n- q1\n\n## Block B: data\n- q2\n\n"
    "## Block F: lookalike\n- q3\n\n## Block G: funding\n- q4\n"
)


def make_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "data").mkdir(parents=True)
    (root / "config").mkdir()
    (root / "data/registry.csv").write_text(SEED_REGISTRY, encoding="utf-8")
    (root / "data/LANDSCAPE.md").write_text(SEED_LANDSCAPE, encoding="utf-8")
    (root / "data/SCANLOG.md").write_text("# Scan Log\n", encoding="utf-8")
    (root / "data/state.json").write_text(json.dumps({
        "schema": 1, "block_cursor": 0, "status_cursor": 0,
        "status_batch": 8, "emphasis_per_run": 2,
        "last_run": "2026-06-10", "last_runner": "baseline",
    }), encoding="utf-8")
    (root / "config/queries.md").write_text(SEED_QUERIES, encoding="utf-8")
    return root


def run_script(script: str, *args, clean=False):
    """Run a script as a subprocess.

    By default authorize writes (these tests are intentional local writes) via
    RADAR_ALLOW_WRITE=1. Pass clean=True to strip both that override and
    GITHUB_ACTIONS, simulating an unauthorized non-canonical runner (the bridge).
    """
    if clean:
        env = {k: v for k, v in os.environ.items()
               if k not in ("GITHUB_ACTIONS", "RADAR_ALLOW_WRITE")}
    else:
        env = {**os.environ, "RADAR_ALLOW_WRITE": "1"}
    return subprocess.run(
        [sys.executable, str(REPO / "scripts" / script), *args],
        capture_output=True, text=True, env=env,
    )


def write_run(root: Path, candidates=None, updates=None, meta=None, day="2026-06-15"):
    run_dir = root / "runs" / day
    run_dir.mkdir(parents=True, exist_ok=True)
    if candidates is not None:
        (run_dir / "candidates.json").write_text(json.dumps(candidates), encoding="utf-8")
    if updates is not None:
        (run_dir / "status_updates.json").write_text(json.dumps(updates), encoding="utf-8")
    (run_dir / "run_meta.json").write_text(json.dumps(meta or {
        "runner": "test", "emphasized_blocks": ["A", "B"],
        "queries_run": ["q1"], "candidates_evaluated": 1,
    }), encoding="utf-8")
    return run_dir


def read_registry(root: Path):
    with (root / "data/registry.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_plan_run_emits_valid_plan(tmp_path):
    root = make_repo(tmp_path)
    r = run_script("plan_run.py", "--root", str(root))
    assert r.returncode == 0, r.stderr
    plan = json.loads(r.stdout)
    assert plan["always_block"] == "F"
    assert plan["emphasized_blocks"] == ["A", "B"]  # cursor 0, F excluded from rotation
    assert "alpha.example" in plan["known_domains"]
    assert 1 <= len(plan["status_targets"]) <= 8


def test_low_footprint_regression_merges_cleanly(tmp_path):
    """THE regression: a low-footprint candidate must enter the registry."""
    root = make_repo(tmp_path)
    cands = json.loads((FIXTURES / "low_footprint_candidate.json").read_text(encoding="utf-8"))
    run_dir = write_run(root, candidates=cands)
    r = run_script("validate_merge.py", "--run-dir", str(run_dir), "--root", str(root), "--runner", "test")
    assert r.returncode == 0, r.stdout + r.stderr
    rows = read_registry(root)
    match = [x for x in rows if x["domain"] == "lowprofile-regression.example"]  # normalized
    assert match and match[0]["tier"] == "2" and match[0]["first_seen"] == match[0]["last_checked"]
    assert "lowprofile-regression" not in (root / "runs/2026-06-15").joinpath("ESCALATION.md").read_text() \
        if (root / "runs/2026-06-15/ESCALATION.md").exists() else True  # T2 must not escalate
    assert "net-new added: 1" in (root / "data/SCANLOG.md").read_text(encoding="utf-8")


def test_new_tier1_escalates(tmp_path):
    root = make_repo(tmp_path)
    cand = json.loads((FIXTURES / "low_footprint_candidate.json").read_text(encoding="utf-8"))[0] | {
        "name": "DirectThreat", "domain": "directthreat.ai", "tier": "1", "cluster": "direct",
        "evidence_url": "https://directthreat.ai/",
    }
    run_dir = write_run(root, candidates=[cand])
    r = run_script("validate_merge.py", "--run-dir", str(run_dir), "--root", str(root), "--runner", "test")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (run_dir / "ESCALATION.md").exists()
    assert "NEW TIER 1: DirectThreat" in (run_dir / "ESCALATION.md").read_text(encoding="utf-8")
    assert "⚠ NEW TIER 1" in (root / "data/LANDSCAPE.md").read_text(encoding="utf-8")


def test_duplicate_domain_rejected_with_normalization(tmp_path):
    root = make_repo(tmp_path)
    cand = json.loads((FIXTURES / "low_footprint_candidate.json").read_text(encoding="utf-8"))[0] | {
        "domain": "https://www.ALPHA.example/about",  # already registered as alpha.example
    }
    run_dir = write_run(root, candidates=[cand])
    before = read_registry(root)
    r = run_script("validate_merge.py", "--run-dir", str(run_dir), "--root", str(root))
    assert r.returncode == 1
    assert "already in registry" in r.stdout
    assert read_registry(root) == before  # nothing written on failure


def test_refuses_non_canonical_writer(tmp_path):
    """Single-writer guard: an unauthorized non-CI run must refuse to write,
    so it can never re-create the parallel-writer divergence."""
    root = make_repo(tmp_path)
    run_dir = write_run(root, candidates=[])
    before = read_registry(root)
    r = run_script("validate_merge.py", "--run-dir", str(run_dir), "--root", str(root), clean=True)
    assert r.returncode != 0
    assert "REFUSING TO WRITE" in (r.stdout + r.stderr)
    assert read_registry(root) == before  # nothing written when not the canonical runner


def test_invalid_enums_rejected(tmp_path):
    root = make_repo(tmp_path)
    cand = json.loads((FIXTURES / "low_footprint_candidate.json").read_text(encoding="utf-8"))[0] | {
        "tier": "4", "cluster": "vibes",
    }
    run_dir = write_run(root, candidates=[cand])
    r = run_script("validate_merge.py", "--run-dir", str(run_dir), "--root", str(root))
    assert r.returncode == 1
    assert "tier" in r.stdout and "cluster" in r.stdout


def test_status_update_applies_and_logs(tmp_path):
    root = make_repo(tmp_path)
    run_dir = write_run(root, candidates=[], updates=[{
        "domain": "beta.example",
        "fields_changed": {"stage": "series-b", "notes": "raised B 2026-06"},
        "change_summary": "Raised Series B",
        "evidence_url": "https://example.com/round",
    }])
    r = run_script("validate_merge.py", "--run-dir", str(run_dir), "--root", str(root), "--runner", "test")
    assert r.returncode == 0, r.stdout + r.stderr
    z = [x for x in read_registry(root) if x["domain"] == "beta.example"][0]
    assert z["stage"] == "series-b" and z["last_checked"] == date.today().isoformat()
    assert "Raised Series B" in (root / "data/LANDSCAPE.md").read_text(encoding="utf-8")


def test_cursors_advance_only_on_success(tmp_path):
    root = make_repo(tmp_path)
    # Failed merge: cursor untouched
    bad = write_run(root, candidates=[{"name": "x"}], day="2026-06-15")
    run_script("validate_merge.py", "--run-dir", str(bad), "--root", str(root))
    assert json.loads((root / "data/state.json").read_text())["block_cursor"] == 0
    # Successful merge: cursor advances by emphasis_per_run
    good = write_run(root, candidates=[], day="2026-06-18")
    r = run_script("validate_merge.py", "--run-dir", str(good), "--root", str(root))
    assert r.returncode == 0, r.stdout + r.stderr
    st = json.loads((root / "data/state.json").read_text())
    assert st["block_cursor"] == 2 and st["status_cursor"] == 8


def test_coverage_ledger_stamps_swept_blocks(tmp_path):
    """A successful merge stamps the emphasized blocks + always-on F in state.coverage."""
    root = make_repo(tmp_path)
    run_dir = write_run(root, candidates=[], day="2026-06-15", meta={
        "runner": "test", "emphasized_blocks": ["A", "B"],
        "queries_run": ["q1"], "candidates_evaluated": 0,
    })
    r = run_script("validate_merge.py", "--run-dir", str(run_dir), "--root", str(root), "--runner", "test")
    assert r.returncode == 0, r.stdout + r.stderr
    cov = json.loads((root / "data/state.json").read_text())["coverage"]
    today = date.today().isoformat()
    assert cov["A"] == today and cov["B"] == today and cov["F"] == today


def test_plan_run_flags_stale_coverage(tmp_path):
    """plan_run flags blocks never swept (or older than the staleness window)."""
    root = make_repo(tmp_path)
    # One merge stamps A, B, F — leaving G (a real block in SEED_QUERIES) never swept.
    run_dir = write_run(root, candidates=[], day="2026-06-15", meta={
        "runner": "test", "emphasized_blocks": ["A", "B"],
        "queries_run": ["q1"], "candidates_evaluated": 0,
    })
    assert run_script("validate_merge.py", "--run-dir", str(run_dir), "--root", str(root)).returncode == 0
    p = run_script("plan_run.py", "--root", str(root))
    assert p.returncode == 0, p.stderr
    plan = json.loads(p.stdout)
    stale = {s["block"] for s in plan["stale_coverage"]}
    assert "G" in stale          # never swept → flagged
    assert "A" not in stale      # swept this run → fresh
    assert "coverage" in plan and plan["coverage"]["A"] == date.today().isoformat()
