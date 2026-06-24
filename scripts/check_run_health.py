#!/usr/bin/env python3
"""Assert a scan run was healthy — not silently degraded. Deterministic, stdlib-only.

The gap this closes: a scan can exit 0 having done nothing useful — the model
crashed mid-run but the CLI returned success, or it wrote runs/<date>/FAILED.md
per CLAUDE.md rule 6, or the publish step swallowed an empty diff. All of those
look identical to a legitimately quiet "verified zero" run. `if: failure()` in
the workflow cannot see them because the job exited 0.

This script is the deterministic tripwire: run it AFTER validate_merge.py. It
fails loudly (exit 1) when the run's own artifacts say it did not really run.

A genuinely zero-find run is HEALTHY: it still sweeps queries (queries_run
non-empty), merges (state.last_run advances), and logs. That is what separates a
verified zero from a broken scan.

Usage: python3 scripts/check_run_health.py --run-dir runs/2026-06-23 [--root .] [--expect-date YYYY-MM-DD]
"""
import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument("--expect-date", default=None,
                    help="date the run should have stamped (default: today UTC)")
    args = ap.parse_args()
    root, run_dir = Path(args.root), Path(args.run_dir)
    expect = args.expect_date or date.today().isoformat()

    errs, warns = [], []

    # 1. The run directory must exist at all.
    if not run_dir.is_dir():
        print(f"DEGRADED: run dir {run_dir} does not exist — the scan produced no run.")
        sys.exit(1)

    # 2. A FAILED.md means the model gave up after retries (CLAUDE.md rule 6).
    #    The scan must NOT be reported as a clean success.
    if (run_dir / "FAILED.md").exists():
        errs.append("FAILED.md present — validate_merge.py rejected this run's JSON after retries.")
    # digest-FAILED.md is non-fatal by design (scan.md step 7) — surface, don't fail.
    if (run_dir / "digest-FAILED.md").exists():
        warns.append("digest-FAILED.md present — digest was rejected (scan itself may be fine).")

    # 3. run_meta.json must show discovery actually happened. An empty/missing
    #    queries_run is the signature of a crash-before-search exit-0.
    meta_path = run_dir / "run_meta.json"
    if not meta_path.exists():
        errs.append("run_meta.json missing — cannot prove discovery ran.")
    else:
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errs.append(f"run_meta.json is not valid JSON: {e}")
            meta = {}
        if not meta.get("queries_run"):
            errs.append("run_meta.queries_run is empty — discovery sweep did not run.")
        if "candidates_evaluated" not in meta:
            warns.append("run_meta.candidates_evaluated missing — cannot confirm candidates were scored.")

    # 4. The merge must have advanced state to this run's date. If state.last_run
    #    is stale, validate_merge.py never ran (scan died before the merge step).
    st_path = root / "data/state.json"
    if not st_path.exists():
        errs.append("data/state.json missing.")
    else:
        try:
            st = json.loads(st_path.read_text(encoding="utf-8"))
            if st.get("last_run") != expect:
                errs.append(f"state.last_run is {st.get('last_run')!r}, expected {expect!r} "
                            "— the merge did not run for this scan.")
        except json.JSONDecodeError as e:
            errs.append(f"data/state.json is not valid JSON: {e}")

    # 5. The registry must still be readable and non-empty.
    reg_path = root / "data/registry.csv"
    if not reg_path.exists():
        errs.append("data/registry.csv missing.")
    else:
        with reg_path.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            errs.append("data/registry.csv has zero rows — the system of record is empty.")

    for w in warns:
        print(f"WARN: {w}")
    if errs:
        print("RUN DEGRADED — a silent failure was caught:\n  - " + "\n  - ".join(errs))
        sys.exit(1)
    print(f"RUN HEALTHY: {expect} — discovery ran, merge advanced state, registry intact.")


if __name__ == "__main__":
    main()
