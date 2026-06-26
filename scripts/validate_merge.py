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
# The valid cluster set is MARKET-SPECIFIC and lives in config/clusters.json so a fork
# retargets by editing config, never this code. This is only the fallback when that file
# is absent (older forks / the test harness's throwaway repos).
DEFAULT_CLUSTERS = {"direct", "chief-of-staff", "data-intel", "incumbent", "employee-assist", "infra", "vertical"}
STATUSES = {"active", "acquired", "dead", "feature"}
REQUIRED = ["name", "domain", "tier", "cluster", "status", "stage", "hq", "founded", "what", "why_tier", "evidence_url"]
FIELDNAMES = ["domain", "name", "tier", "cluster", "status", "stage", "hq", "founded",
              "first_seen", "last_checked", "what", "why_tier", "evidence_url", "notes"]
# `founded` and `hq` are corrigible factual fields, not identity: data-entry errors
# (conflating a YC batch / first-funding / launch year with the founding year; recording
# a founder's city as HQ when the company is elsewhere) and relocations are common and
# are legitimate corrections the canonical writer should accept without a hand-edit. Only
# identity fields (domain, name) and system timestamps (first_seen, last_checked) stay off-limits.
UPDATABLE = {"tier", "cluster", "status", "stage", "founded", "hq", "what", "why_tier", "evidence_url", "notes"}
ALWAYS_BLOCK = "F"  # always-run recall safety-net block; stamped in the coverage ledger every run


def norm_domain(d: str) -> str:
    d = (d or "").strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = d.removeprefix("www.")
    return d.split("/")[0].split("?")[0]


def load_clusters(root: Path) -> set:
    """Valid cluster set from config/clusters.json (so a fork retargets via config, not
    code). Falls back to the default set when the file is absent or malformed."""
    p = root / "config/clusters.json"
    if p.exists():
        try:
            cl = json.loads(p.read_text(encoding="utf-8")).get("clusters", [])
            if cl:
                return set(cl)
        except (json.JSONDecodeError, AttributeError, TypeError):
            pass
    return set(DEFAULT_CLUSTERS)


def load_json(path: Path, default=None):
    if not path.exists():
        if default is not None:
            return default
        sys.exit(f"ERROR: missing {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"ERROR: {path} is not valid JSON: {e}")


def validate_candidates(cands, known, clusters):
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
        if c.get("cluster") not in clusters:
            errs.append(f"{tag}: cluster must be one of {sorted(clusters)} (edit config/clusters.json to change)")
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
    ap.add_argument("--corrections-only", action="store_true",
                    help="apply status_updates as out-of-band data corrections: write the registry "
                         "and a correction-tagged changelog/scanlog entry, but do NOT add candidates, "
                         "advance scan cursors, or stamp coverage. Use for accuracy fixes between scans.")
    args = ap.parse_args()

    # --- single canonical writer guard (divergence prevention) ---
    # Only GitHub Actions (the canonical runner) may write the system of record. An
    # automatic non-CI run writing here can fork the registry into divergent lineages
    # that silently lose competitors. Intentional local maintenance must opt in
    # explicitly (and `git pull` first).
    if not os.environ.get("GITHUB_ACTIONS") and os.environ.get("RADAR_ALLOW_WRITE") != "1":
        sys.exit(
            "REFUSING TO WRITE: not the canonical runner (GitHub Actions).\n"
            "Automatic non-CI runs must not write the registry — that can fork it into\n"
            "divergent lineages and silently lose competitors. GitHub Actions is the sole\n"
            "writer. For an intentional, pull-first local run, set RADAR_ALLOW_WRITE=1."
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

    errs = validate_candidates(cands, set(by_domain), load_clusters(root)) + validate_updates(ups, by_domain)
    if args.corrections_only and cands:
        errs.append("--corrections-only run must not add candidates; new companies go through a scan, not a correction batch")
    if args.corrections_only and not ups:
        errs.append("--corrections-only run needs at least one status_update")
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

    # --- changelog (+ last-scan stamp, scans only) in LANDSCAPE.md ---
    land_path = root / "data/LANDSCAPE.md"
    land = land_path.read_text(encoding="utf-8")
    kind = "correction" if args.corrections_only else "scan"
    entry = [f"### {run_date} — {kind} ({args.runner})"]
    if new_t1:
        entry.append("**⚠ NEW TIER 1:** " + ", ".join(f"{r['name']} ({r['domain']})" for r in new_t1))
    if added:
        entry.append("Added: " + "; ".join(f"{r['name']} (T{r['tier']}, {r['cluster']})" for r in added))
    if updated:
        entry.append(("Corrected: " if args.corrections_only else "Updated: ")
                     + "; ".join(f"{n} — {s}" for n, s in updated))
    if not added and not updated and not args.corrections_only:
        entry.append("No new companies, no material status changes. Blocks swept: "
                     + ", ".join(meta.get("emphasized_blocks", [])) + ".")
    land = land.replace("## Changelog\n", "## Changelog\n\n" + "\n".join(entry) + "\n", 1)
    if not args.corrections_only:  # a correction is not a scan — don't move the scan watermark
        land = re.sub(r"\*\*Last scan:\*\* .*", f"**Last scan:** {run_date} ({args.runner}) · **Tracked:** {len(rows)} companies", land, count=1)
    land_path.write_text(land, encoding="utf-8")

    # --- scan log (append-only; every run logs, including zero-find runs) ---
    with (root / "data/SCANLOG.md").open("a", encoding="utf-8") as f:
        if args.corrections_only:
            f.write(f"\n## {run_date} — correction ({args.runner})\n"
                    f"- Out-of-band accuracy corrections: {len(updated)} rows. "
                    f"No scan; cursors/coverage untouched.\n")
        else:
            f.write(f"\n## {run_date} ({args.runner})\n"
                    f"- Queries run: {len(meta.get('queries_run', []))} "
                    f"(blocks: {', '.join(meta.get('emphasized_blocks', ['?']))} + F + wildcards)\n"
                    f"- Candidates evaluated: {meta.get('candidates_evaluated', len(cands))}; "
                    f"net-new added: {len(added)}; status updates: {len(updated)}\n"
                    f"- Escalations: {len(new_t1) + len(tier1_updates)}\n")
        if meta.get("notes"):
            f.write(f"- Notes: {meta['notes']}\n")

    # --- advance cursors + stamp coverage (scans only; a correction must not move the scheduler) ---
    if not args.corrections_only:
        st_path = root / "data/state.json"
        st = json.loads(st_path.read_text(encoding="utf-8"))
        st["block_cursor"] = st.get("block_cursor", 0) + st.get("emphasis_per_run", 2)
        st["status_cursor"] = st.get("status_cursor", 0) + st.get("status_batch", 8)
        st["last_run"], st["last_runner"] = run_date, args.runner
        # coverage ledger: stamp the blocks this run actually swept (emphasized + always-on F)
        cov = st.get("coverage", {})
        for b in list(meta.get("emphasized_blocks", [])) + [ALWAYS_BLOCK]:
            cov[str(b)] = run_date
        st["coverage"] = cov
        st_path.write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")

    verb = "CORRECTED" if args.corrections_only else "MERGED"
    print(f"{verb}: +{len(added)} companies, {len(updated)} updates, "
          f"{len(new_t1) + len(tier1_updates)} escalations. Registry now {len(rows)} rows."
          + (" (cursors/coverage untouched)" if args.corrections_only else ""))


if __name__ == "__main__":
    main()
