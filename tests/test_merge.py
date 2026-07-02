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


def test_duplicate_domain_fragment_or_trailing_dot_rejected(tmp_path):
    """norm_domain must strip #fragments and trailing dots, or a duplicate of an
    already-tracked company slips in as a brand-new row (dedup-key bypass)."""
    root = make_repo(tmp_path)
    base = json.loads((FIXTURES / "low_footprint_candidate.json").read_text(encoding="utf-8"))[0]
    for dom in ("https://www.ALPHA.example/about#pricing", "alpha.example."):
        run_dir = write_run(root, candidates=[base | {"domain": dom}], day="2026-06-15")
        before = read_registry(root)
        r = run_script("validate_merge.py", "--run-dir", str(run_dir), "--root", str(root))
        assert r.returncode == 1, f"{dom!r} should normalize to a known domain"
        assert "already in registry" in r.stdout
        assert read_registry(root) == before


def test_status_update_rejects_invalid_cluster(tmp_path):
    """A status_update may change cluster, but only to a configured one — validate_updates
    must enforce the same cluster enum as validate_candidates (insert/update parity)."""
    root = make_repo(tmp_path)
    run_dir = write_run(root, candidates=[], updates=[{
        "domain": "beta.example",
        "fields_changed": {"cluster": "totally-bogus"},
        "change_summary": "reclassify",
        "evidence_url": "https://example.com/x",
    }])
    before = read_registry(root)
    r = run_script("validate_merge.py", "--run-dir", str(run_dir), "--root", str(root))
    assert r.returncode == 1
    assert "cluster" in r.stdout
    assert read_registry(root) == before


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


def test_clusters_are_config_driven(tmp_path):
    """A fork retargets its market by editing config/clusters.json — never code or tests.
    A cluster valid only in that file is accepted; a default cluster absent from it is rejected.
    This is the regression guard for the onboarding bug (clusters were hardcoded in code)."""
    root = make_repo(tmp_path)
    (root / "config/clusters.json").write_text(
        json.dumps({"clusters": ["lecture-overlay", "flashcards-quiz"]}), encoding="utf-8")
    base = json.loads((FIXTURES / "low_footprint_candidate.json").read_text(encoding="utf-8"))[0]
    # a cluster defined only in this market's config -> accepted, no code edit
    ok = base | {"cluster": "lecture-overlay"}
    rd = write_run(root, candidates=[ok], day="2026-06-15")
    r = run_script("validate_merge.py", "--run-dir", str(rd), "--root", str(root), "--runner", "test")
    assert r.returncode == 0, r.stdout + r.stderr
    # a default cluster NOT in this market's config -> rejected
    bad = base | {"domain": "other.example", "cluster": "data-intel"}
    rd2 = write_run(root, candidates=[bad], day="2026-06-18")
    r2 = run_script("validate_merge.py", "--run-dir", str(rd2), "--root", str(root))
    assert r2.returncode == 1 and "cluster" in r2.stdout


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


def test_corrections_only_does_not_advance_scan_state(tmp_path):
    """An out-of-band correction applies status_updates + writes a correction-tagged
    changelog, but must NOT advance scan cursors, stamp coverage, or move the scan
    watermark — otherwise a between-scans accuracy fix desyncs the scheduler."""
    root = make_repo(tmp_path)
    before = json.loads((root / "data/state.json").read_text())
    run_dir = write_run(root, candidates=None, updates=[{
        "domain": "beta.example",
        "fields_changed": {"founded": "2020", "hq": "Berlin, DE"},  # corrigible factual fields
        "change_summary": "accuracy fix: founded 2021 -> 2020; hq US -> Berlin, DE",
        "evidence_url": "https://example.com/about",
    }], day="2026-06-15")
    r = run_script("validate_merge.py", "--run-dir", str(run_dir), "--root", str(root),
                   "--runner", "audit", "--corrections-only")
    assert r.returncode == 0, r.stdout + r.stderr
    z = [x for x in read_registry(root) if x["domain"] == "beta.example"][0]
    assert z["founded"] == "2020" and z["hq"] == "Berlin, DE" and z["last_checked"] == date.today().isoformat()
    after = json.loads((root / "data/state.json").read_text())
    assert after["block_cursor"] == before["block_cursor"]      # cursors frozen
    assert after["status_cursor"] == before["status_cursor"]
    assert after.get("coverage", {}) == before.get("coverage", {})
    land = (root / "data/LANDSCAPE.md").read_text(encoding="utf-8")
    assert "— correction (audit)" in land and "Corrected: Beta" in land
    assert "**Last scan:** 2026-06-10 (baseline)" in land       # scan watermark untouched
    assert "Out-of-band accuracy corrections: 1 rows" in (root / "data/SCANLOG.md").read_text(encoding="utf-8")


def test_corrections_only_rejects_new_candidates(tmp_path):
    """corrections-only is for fixing existing rows, never adding companies."""
    root = make_repo(tmp_path)
    cand = json.loads((FIXTURES / "low_footprint_candidate.json").read_text(encoding="utf-8"))
    run_dir = write_run(root, candidates=cand, updates=[{
        "domain": "beta.example", "fields_changed": {"founded": "2020"},
        "change_summary": "x", "evidence_url": "https://e.com/about",
    }])
    r = run_script("validate_merge.py", "--run-dir", str(run_dir), "--root", str(root), "--corrections-only")
    assert r.returncode == 1
    assert "must not add candidates" in r.stdout


def test_score_axes_deterministic_and_sane(tmp_path):
    """Axis scoring must be reproducible (same registry → same coordinates) and rank a
    cross-tool direct competitor broader than a warehouse-bound data-intel tool."""
    root = make_repo(tmp_path)
    r1 = run_script("score_axes.py", "--root", str(root), "--all")
    r2 = run_script("score_axes.py", "--root", str(root), "--all")
    assert r1.returncode == 0, r1.stderr
    assert r1.stdout == r2.stdout                       # deterministic
    d = json.loads(r1.stdout)
    by = {c["name"]: c for c in d["companies"]}
    for c in d["companies"]:
        assert 8 <= c["axis_breadth"] <= 96 and 8 <= c["axis_action"] <= 96  # clamped
    assert by["Alpha"]["axis_breadth"] > by["Beta"]["axis_breadth"]          # breadth ordering
    assert by["Beta"]["axis_action"] < 50                                    # analyst leans retrieve


def test_status_update_rejects_nonscalar_value(tmp_path):
    """A status_update value must be a scalar — a list/dict/None must not be str()-ified
    into the registry across the trust boundary."""
    root = make_repo(tmp_path)
    run_dir = write_run(root, candidates=[], updates=[{
        "domain": "beta.example", "fields_changed": {"cluster": ["a", "b"]},
        "change_summary": "x", "evidence_url": "https://e.com/x",
    }])
    r = run_script("validate_merge.py", "--run-dir", str(run_dir), "--root", str(root))
    assert r.returncode == 1
    assert "scalar" in r.stdout            # clean failure, not a TypeError crash on the enum check
    assert "Traceback" not in (r.stdout + r.stderr)


def test_load_gate_rejects_corrupt_registry(tmp_path):
    """Domain is the join key for dedup + status updates; a blank or duplicate domain in
    the registry must fail the merge closed rather than silently corrupt the join."""
    root = make_repo(tmp_path)
    reg = root / "data/registry.csv"
    reg.write_text(reg.read_text(encoding="utf-8")
                   + ",Blank,3,direct,active,seed,US,2020,2026-06-10,2026-06-10,x,y,https://x.example/,\n"
                   + "alpha.example,Dup,3,direct,active,seed,US,2020,2026-06-10,2026-06-10,x,y,https://d.example/,\n",
                   encoding="utf-8")
    r = run_script("validate_merge.py", "--run-dir", str(write_run(root, candidates=[])), "--root", str(root))
    assert r.returncode != 0
    assert "INTEGRITY ERROR" in (r.stdout + r.stderr)


def test_load_gate_rejects_unexpected_registry_columns(tmp_path):
    """An out-of-band column add/drop in the registry must fail closed, not silently drop
    data on the next system-of-record rewrite."""
    root = make_repo(tmp_path)
    reg = root / "data/registry.csv"
    lines = reg.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0] + ",surprise"            # extra header column
    reg.write_text("\n".join(lines) + "\n", encoding="utf-8")
    r = run_script("validate_merge.py", "--run-dir", str(write_run(root, candidates=[])), "--root", str(root))
    assert r.returncode != 0
    assert "SCHEMA ERROR" in (r.stdout + r.stderr)


def test_csv_formula_injection_neutralized(tmp_path):
    """A candidate field starting with a formula char is written with a leading apostrophe
    so a spreadsheet treats it as text, not a macro."""
    root = make_repo(tmp_path)
    base = json.loads((FIXTURES / "low_footprint_candidate.json").read_text(encoding="utf-8"))[0]
    cand = base | {"domain": "formula.example", "name": "=cmd|'/c calc'!A1"}
    run_dir = write_run(root, candidates=[cand])
    r = run_script("validate_merge.py", "--run-dir", str(run_dir), "--root", str(root), "--runner", "test")
    assert r.returncode == 0, r.stdout + r.stderr
    row = [x for x in read_registry(root) if x["domain"] == "formula.example"][0]
    assert row["name"].startswith("'=")


def test_formula_leading_domain_rejected(tmp_path):
    """A domain starting with a formula char (=/-/+/@) is malformed and must be rejected at
    validation — never stored, so the join key is never an injection vector or mutated."""
    root = make_repo(tmp_path)
    base = json.loads((FIXTURES / "low_footprint_candidate.json").read_text(encoding="utf-8"))[0]
    run_dir = write_run(root, candidates=[base | {"domain": "=evil.com"}])
    r = run_script("validate_merge.py", "--run-dir", str(run_dir), "--root", str(root))
    assert r.returncode == 1
    assert "invalid domain" in r.stdout


def snapshot_sor(root: Path):
    """Byte snapshot of every system-of-record file, for zero-write assertions."""
    return {p: (root / p).read_bytes() for p in
            ("data/registry.csv", "data/LANDSCAPE.md", "data/SCANLOG.md", "data/state.json")}


def test_validate_only_valid_input_writes_nothing(tmp_path):
    """--validate-only on a valid run: exit 0 with the OK line, every system-of-record file
    byte-unchanged — and no canonical-writer env var required (validation needs no write
    authority, so clean=True must not trip the guard)."""
    root = make_repo(tmp_path)
    cands = json.loads((FIXTURES / "low_footprint_candidate.json").read_text(encoding="utf-8"))
    run_dir = write_run(root, candidates=cands)
    before = snapshot_sor(root)
    r = run_script("validate_merge.py", "--run-dir", str(run_dir), "--root", str(root),
                   "--validate-only", clean=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "VALIDATION OK (no writes performed)" in r.stdout
    assert "REFUSING TO WRITE" not in (r.stdout + r.stderr)
    assert snapshot_sor(root) == before


def test_validate_only_invalid_input_reports_errors(tmp_path):
    """--validate-only on invalid input: exit 1 with the validation error, zero writes,
    still no env var required."""
    root = make_repo(tmp_path)
    cand = json.loads((FIXTURES / "low_footprint_candidate.json").read_text(encoding="utf-8"))[0] | {
        "tier": "4",
    }
    run_dir = write_run(root, candidates=[cand])
    before = snapshot_sor(root)
    r = run_script("validate_merge.py", "--run-dir", str(run_dir), "--root", str(root),
                   "--validate-only", clean=True)
    assert r.returncode == 1
    assert "VALIDATION FAILED" in r.stdout and "tier" in r.stdout
    assert snapshot_sor(root) == before


def test_malformed_state_fails_before_any_write(tmp_path):
    """state.json is parsed up front and fail-closed: on a write-armed run, a corrupt
    scheduler state must abort BEFORE the registry is rewritten (read-everything-before-
    writing-anything), not crash after the system of record already changed."""
    root = make_repo(tmp_path)
    (root / "data/state.json").write_text("{not json", encoding="utf-8")
    cands = json.loads((FIXTURES / "low_footprint_candidate.json").read_text(encoding="utf-8"))
    run_dir = write_run(root, candidates=cands)
    before = snapshot_sor(root)
    r = run_script("validate_merge.py", "--run-dir", str(run_dir), "--root", str(root))
    assert r.returncode != 0
    assert "STATE ERROR in data/state.json" in (r.stdout + r.stderr)
    assert "Traceback" not in (r.stdout + r.stderr)
    assert snapshot_sor(root) == before


def test_missing_changelog_heading_fails_closed(tmp_path):
    """A LANDSCAPE.md without the '## Changelog' anchor must abort before any write —
    the old str.replace() silently dropped the changelog entry."""
    root = make_repo(tmp_path)
    (root / "data/LANDSCAPE.md").write_text(
        "# Landscape\n\n**Last scan:** 2026-06-10 (baseline)\n", encoding="utf-8")
    cands = json.loads((FIXTURES / "low_footprint_candidate.json").read_text(encoding="utf-8"))
    run_dir = write_run(root, candidates=cands)
    before = snapshot_sor(root)
    r = run_script("validate_merge.py", "--run-dir", str(run_dir), "--root", str(root))
    assert r.returncode != 0
    assert "## Changelog" in (r.stdout + r.stderr)
    assert snapshot_sor(root) == before


def test_missing_scan_watermark_fails_closed_on_scan_only(tmp_path):
    """A scan needs the '**Last scan:**' watermark (the old re.sub silently no-opped
    without it); a corrections-only run never stamps it, so it must not require it."""
    root = make_repo(tmp_path)
    (root / "data/LANDSCAPE.md").write_text(
        "# Landscape\n\n## Changelog\n\n### 2026-06-10 — Baseline established\nSeed.\n",
        encoding="utf-8")
    run_dir = write_run(root, candidates=[])
    before = snapshot_sor(root)
    r = run_script("validate_merge.py", "--run-dir", str(run_dir), "--root", str(root))
    assert r.returncode != 0
    assert "Last scan" in (r.stdout + r.stderr)
    assert snapshot_sor(root) == before
    # a correction is not a scan — it must succeed without the watermark
    run_dir2 = write_run(root, candidates=None, updates=[{
        "domain": "beta.example", "fields_changed": {"founded": "2020"},
        "change_summary": "accuracy fix", "evidence_url": "https://example.com/about",
    }], day="2026-06-18")
    r2 = run_script("validate_merge.py", "--run-dir", str(run_dir2), "--root", str(root),
                    "--runner", "audit", "--corrections-only")
    assert r2.returncode == 0, r2.stdout + r2.stderr


def test_null_run_meta_field_fails_in_validation_before_any_write(tmp_path):
    """run_meta.json fields are consumed after writes begin (changelog line, scanlog
    entry, coverage stamp): a null emphasized_blocks must fail in the VALIDATION phase
    — exit 1, system of record byte-unchanged, no Traceback — never TypeError after
    the registry and LANDSCAPE were already rewritten (torn system of record)."""
    root = make_repo(tmp_path)
    bad_meta = {"runner": "test", "emphasized_blocks": None,
                "queries_run": ["q1"], "candidates_evaluated": 0}
    run_dir = write_run(root, candidates=[], meta=bad_meta)
    before = snapshot_sor(root)
    r = run_script("validate_merge.py", "--run-dir", str(run_dir), "--root", str(root))
    assert r.returncode == 1
    assert "run_meta.json: emphasized_blocks must be a list of strings" in r.stdout
    assert "Traceback" not in (r.stdout + r.stderr)
    assert snapshot_sor(root) == before
    # same check must also fire under --validate-only (no write authority needed)
    r2 = run_script("validate_merge.py", "--run-dir", str(run_dir), "--root", str(root),
                    "--validate-only", clean=True)
    assert r2.returncode == 1 and "emphasized_blocks must be a list of strings" in r2.stdout
    assert snapshot_sor(root) == before
