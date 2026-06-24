#!/usr/bin/env python3
"""Validate this run's outputs and merge them into the system of record.

The ONLY writer of data/registry.csv, data/LANDSCAPE.md (changelog), data/SCANLOG.md,
and data/state.json. The agent writes runs/<date>/candidates.json (+ optional
status_updates.json, run_meta.json); this script validates hard and merges, or
exits 1 with actionable errors and writes NOTHING.

Usage: python scripts/validate_merge.py --run-dir runs/2026-06-15 [--root .] [--runner github]
"""
import argparse
import csv
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

TIERS = {"1", "2", "3"}
CLUSTERS = {"direct", "chief-of-staff", "data-intel", "incumbent", "employee-assist", "infra", "vertical"}
STATUSES = {"active", "acquired", "dead", "feature"}
REQUIRED = ["name", "domain", "tier", "cluster", "status", "stage", "hq", "founded", "what", "why_tier", "evidence_url"]
FIELDNAMES = ["domain", "name", "tier", "cluster", "status", "stage", "hq", "founded",
              "first_seen", "last_checked", "what", "why_tier", "evidence_url", "notes"]
UPDATABLE = {"tier", "cluster", "status", "stage", "what", "why_tier", "evidence_url", "notes"}
ALWAYS_BLOCK = "F"  # always-run recall safety-net block; stamped in the coverage ledger every run


def norm_domain(d: str) -> str:
    d = (d or "").strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = d.removeprefix("www.")
    return d.split("/")[0].split("?")[0]


def load_json(path: Path, default=None):
    if not path.exists():
        if default is not None:
            return default
        sys.exit(f"ERROR: missing {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"ERROR: {path} is not valid JSON: {e}")


def validate_candidates(cands, known):
    errs, seen = [], set()
    for i, c in enumerate(cands):
        tag = f"candidates[{i}] ({c.get('name', '?')})"
        for f in REQUIRED:
            if not str(c.get(f, "")).strip():
                errs.append(f"{tag}: missing required field '{f}'")
        d = norm_domain(c.get("domain", ""))
        if not d or "." not in d:
            errs.append(f"{tag}: invalid domain '{c.get('domain')}'")
        elif d in known:
            errs.append(f"{tag}: domain '{d}' already in registry — if status changed, use status_updates.json; otherwise drop it")
        elif d in seen:
            errs.append(f"{tag}: domain '{d}' duplicated within candidates.json")
        seen.add(d)
        if str(c.get("tier")) not in TIERS:
            errs.append(f"{tag}: tier must be one of {sorted(TIERS)}")
        if c.get("cluster") not in CLUSTERS:
            errs.append(f"{tag}: cluster must be one of {sorted(CLUSTERS)}")
        if c.get("status") not in STATUSES:
            errs.append(f"{tag}: status must be one of {sorted(STATUSES)}")
        if not str(c.get("evidence_url", "")).startswith("http"):
            errs.append(f"{tag}: evidence_url must be a URL")
    return errs


def validate_updates(ups, by_domain):
    errs = []
    for i, u in enumerate(ups):
        tag = f"status_updates[{i}] ({u.get('domain', '?')})"
        d = norm_domain(u.get("domain", ""))
        if d not in by_domain:
            errs.append(f"{tag}: domain not in registry")
        changed = u.get("fields_changed", {})
        if not isinstance(changed, dict) or not changed:
            errs.append(f"{tag}: fields_changed must be a non-empty object")
            continue
        for k, v in changed.items():
            if k not in UPDATABLE:
                errs.append(f"{tag}: field '{k}' is not updatable (allowed: {sorted(UPDATABLE)})")
            if k == "tier" and str(v) not in TIERS:
                errs.append(f"{tag}: tier must be one of {sorted(TIERS)}")
            if k == "status" and v not in STATUSES:
                errs.append(f"{tag}: status must be one of {sorted(STATUSES)}")
        if not str(u.get("change_summary", "")).strip():
            errs.append(f"{tag}: missing change_summary")
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument("--runner", default="local")
    args = ap.parse_args()

    # --- single canonical writer guard (divergence prevention) ---
    # Only the canonical runner (CI) may write the system of record. An automatic
    # non-CI run writing here creates divergent git histories that can silently drop
    # entries on the next reconcile. Intentional local maintenance opts in explicitly
    # (and `git pull` first).
    if not os.environ.get("GITHUB_ACTIONS") and os.environ.get("RADAR_ALLOW_WRITE") != "1":
        sys.exit(
            "REFUSING TO WRITE: not the canonical runner (GitHub Actions).\n"
            "Automatic non-CI runs must not write the registry — parallel writers create\n"
            "divergent histories that silently drop entries. GitHub Actions is the sole writer.\n"
            "For an intentional, pull-first local run, set RADAR_ALLOW_WRITE=1."
        )

    root, run_dir = Path(args.root), Path(args.run_dir)
    run_date = date.today().isoformat()

    reg_path = root / "data/registry.csv"
    with reg_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    by_domain = {norm_domain(r["domain"]): r for r in rows}

    cands = load_json(run_dir / "candidates.json", default=[])
    ups = load_json(run_dir / "status_updates.json", default=[])
    meta = load_json(run_dir / "run_meta.json", default={})

    errs = validate_candidates(cands, set(by_domain)) + validate_updates(ups, by_domain)
    if errs:
        print("VALIDATION FAILED — fix and re-run:\n  - " + "\n  - ".join(errs))
        sys.exit(1)

    # --- merge candidates ---
    added = []
    for c in cands:
        row = {
            "domain": norm_domain(c["domain"]), "name": c["name"].strip(),
            "tier": str(c["tier"]), "cluster": c["cluster"], "status": c["status"],
            "stage": c["stage"], "hq": c["hq"], "founded": str(c["founded"]),
            "first_seen": run_date, "last_checked": run_date,
            "what": c["what"], "why_tier": c["why_tier"],
            "evidence_url": c["evidence_url"], "notes": c.get("notes", ""),
        }
        rows.append(row)
        added.append(row)

    # --- apply status updates ---
    updated, tier1_updates = [], []
    for u in ups:
        row = by_domain[norm_domain(u["domain"])]
        for k, v in u["fields_changed"].items():
            row[k] = str(v)
        row["last_checked"] = run_date
        updated.append((row["name"], u["change_summary"]))
        if str(u["fields_changed"].get("tier", "")) == "1":
            tier1_updates.append((row["name"], u["change_summary"]))

    with reg_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(rows)

    # --- escalation ---
    new_t1 = [r for r in added if r["tier"] == "1"]
    if new_t1 or tier1_updates:
        lines = [f"# Escalation — {run_date}", ""]
        for r in new_t1:
            lines += [f"## NEW TIER 1: {r['name']} ({r['domain']})",
                      f"- {r['what']}", f"- Why Tier 1: {r['why_tier']}",
                      f"- Evidence: {r['evidence_url']}", ""]
        for name, summary in tier1_updates:
            lines += [f"## MOVED TO TIER 1: {name}", f"- {summary}", ""]
        (run_dir / "ESCALATION.md").write_text("\n".join(lines), encoding="utf-8")

    # --- changelog + last-scan stamp in LANDSCAPE.md ---
    land_path = root / "data/LANDSCAPE.md"
    land = land_path.read_text(encoding="utf-8")
    entry = [f"### {run_date} — scan ({args.runner})"]
    if new_t1:
        entry.append("**⚠ NEW TIER 1:** " + ", ".join(f"{r['name']} ({r['domain']})" for r in new_t1))
    if added:
        entry.append("Added: " + "; ".join(f"{r['name']} (T{r['tier']}, {r['cluster']})" for r in added))
    if updated:
        entry.append("Updated: " + "; ".join(f"{n} — {s}" for n, s in updated))
    if not added and not updated:
        entry.append("No new companies, no material status changes. Blocks swept: "
                     + ", ".join(meta.get("emphasized_blocks", [])) + ".")
    land = land.replace("## Changelog\n", "## Changelog\n\n" + "\n".join(entry) + "\n", 1)
    land = re.sub(r"\*\*Last scan:\*\* .*", f"**Last scan:** {run_date} ({args.runner}) · **Tracked:** {len(rows)} companies", land, count=1)
    land_path.write_text(land, encoding="utf-8")

    # --- scan log (append-only; every run logs, including zero-find runs) ---
    with (root / "data/SCANLOG.md").open("a", encoding="utf-8") as f:
        f.write(f"\n## {run_date} ({args.runner})\n"
                f"- Queries run: {len(meta.get('queries_run', []))} "
                f"(blocks: {', '.join(meta.get('emphasized_blocks', ['?']))} + F + wildcards)\n"
                f"- Candidates evaluated: {meta.get('candidates_evaluated', len(cands))}; "
                f"net-new added: {len(added)}; status updates: {len(updated)}\n"
                f"- Escalations: {len(new_t1) + len(tier1_updates)}\n")
        if meta.get("notes"):
            f.write(f"- Notes: {meta['notes']}\n")

    # --- advance cursors (only on success) ---
    st_path = root / "data/state.json"
    st = json.loads(st_path.read_text(encoding="utf-8"))
    st["block_cursor"] = st.get("block_cursor", 0) + st.get("emphasis_per_run", 2)
    st["status_cursor"] = st.get("status_cursor", 0) + st.get("status_batch", 8)
    st["last_run"], st["last_runner"] = run_date, args.runner
    # --- coverage ledger: stamp the blocks this run actually swept (emphasized + always-on F) ---
    cov = st.get("coverage", {})
    for b in list(meta.get("emphasized_blocks", [])) + [ALWAYS_BLOCK]:
        cov[str(b)] = run_date
    st["coverage"] = cov
    st_path.write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")

    print(f"MERGED: +{len(added)} companies, {len(updated)} updates, "
          f"{len(new_t1) + len(tier1_updates)} escalations. Registry now {len(rows)} rows.")


if __name__ == "__main__":
    main()
