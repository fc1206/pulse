"""Tests for scripts/check_run_health.py — the silent-degradation tripwire.

A scan can exit 0 having done nothing. These tests pin the cases the workflow's
`if: failure()` cannot see: a FAILED.md run, an empty discovery sweep, and a
merge that never advanced state. A genuinely zero-find run must still pass.
"""
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TODAY = date.today().isoformat()


def make_repo(tmp_path: Path, last_run=TODAY) -> Path:
    root = tmp_path / "repo"
    (root / "data").mkdir(parents=True)
    (root / "data/registry.csv").write_text(
        "domain,name,tier,cluster,status,stage,hq,founded,first_seen,last_checked,"
        "what,why_tier,evidence_url,notes\n"
        "alpha.example,Alpha,1,direct,active,series-f,US,2019,2026-06-10,2026-06-10,"
        "x,y,https://alpha.example/,\n",
        encoding="utf-8",
    )
    (root / "data/state.json").write_text(json.dumps({"last_run": last_run, "last_runner": "test"}),
                                          encoding="utf-8")
    return root


def write_run(root: Path, meta=None, day=TODAY, extra_files=None):
    run_dir = root / "runs" / day
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_meta.json").write_text(json.dumps(meta if meta is not None else {
        "runner": "test", "emphasized_blocks": ["A", "B"],
        "queries_run": ["q1", "q2"], "candidates_evaluated": 3,
    }), encoding="utf-8")
    for name, body in (extra_files or {}).items():
        (run_dir / name).write_text(body, encoding="utf-8")
    return run_dir


def run_check(root: Path, run_dir: Path):
    return subprocess.run(
        [sys.executable, str(REPO / "scripts" / "check_run_health.py"),
         "--run-dir", str(run_dir), "--root", str(root), "--expect-date", TODAY],
        capture_output=True, text=True,
    )


def test_healthy_run_passes(tmp_path):
    root = make_repo(tmp_path)
    run_dir = write_run(root)
    r = run_check(root, run_dir)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "RUN HEALTHY" in r.stdout


def test_zero_find_run_is_healthy(tmp_path):
    """Verified zero: queries ran, state advanced, no candidates. Must NOT be flagged."""
    root = make_repo(tmp_path)
    run_dir = write_run(root, meta={
        "runner": "test", "emphasized_blocks": ["A"], "queries_run": ["q1"], "candidates_evaluated": 0,
    })
    r = run_check(root, run_dir)
    assert r.returncode == 0, r.stdout + r.stderr


def test_failed_md_is_degraded(tmp_path):
    root = make_repo(tmp_path)
    run_dir = write_run(root, extra_files={"FAILED.md": "merge rejected"})
    r = run_check(root, run_dir)
    assert r.returncode == 1
    assert "FAILED.md present" in r.stdout


def test_empty_queries_is_degraded(tmp_path):
    """Crash-before-search exit-0: no queries were run."""
    root = make_repo(tmp_path)
    run_dir = write_run(root, meta={"runner": "test", "queries_run": [], "candidates_evaluated": 0})
    r = run_check(root, run_dir)
    assert r.returncode == 1
    assert "queries_run is empty" in r.stdout


def test_stale_state_is_degraded(tmp_path):
    """Merge never ran: state.last_run is from a previous day."""
    root = make_repo(tmp_path, last_run="2026-01-01")
    run_dir = write_run(root)
    r = run_check(root, run_dir)
    assert r.returncode == 1
    assert "state.last_run" in r.stdout


def test_missing_run_dir_is_degraded(tmp_path):
    root = make_repo(tmp_path)
    r = run_check(root, root / "runs" / TODAY)  # never created
    assert r.returncode == 1
    assert "does not exist" in r.stdout


def test_digest_failed_is_warn_not_fail(tmp_path):
    """A rejected digest is non-fatal (scan.md step 7) — warn, but run stays healthy."""
    root = make_repo(tmp_path)
    run_dir = write_run(root, extra_files={"digest-FAILED.md": "slop"})
    r = run_check(root, run_dir)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "WARN" in r.stdout and "digest-FAILED.md" in r.stdout
