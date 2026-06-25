#!/usr/bin/env python3
"""Deterministic axis scoring for the competitive map.

Turns each registry row into two 0–100 coordinates, computed only from fields the
registry already holds (cluster + the `what`/`why_tier` text), so the map is a
reproducible view of the data — never hand-placed. Same registry + config in → same
map out.

The axes and their signals live in **config/axes.json** (Frank-editable; a fork's
`/setup` overwrites it for its own market), so this scorer is NOT hardcoded to any one
landscape. If that file is missing, a minimal built-in fallback keeps it from crashing.

  x_axis  e.g. point tool ............ whole-company context layer
  y_axis  e.g. retrieves/answers ..... acts/executes

Stdlib only (the scan runs on bare python3). Prints JSON to stdout; with --write it
also drops data/axes.json for the renderer.

  python3 scripts/score_axes.py [--root .] [--config config/axes.json] [--write] [--all]
"""
import argparse
import csv
import json
import re
from pathlib import Path

# Minimal fallback if config/axes.json is absent — cluster priors only, no keyword tuning.
# The shipped config/axes.json carries the real (market-specific) signal rules.
BUILTIN = {
    "x_axis": {"label": "breadth", "low": "narrow", "high": "broad"},
    "y_axis": {"label": "action", "low": "retrieves", "high": "acts"},
    "x_cluster_base": {"incumbent": 70, "direct": 68, "chief-of-staff": 50,
                       "employee-assist": 46, "infra": 42, "data-intel": 36, "vertical": 28},
    "y_cluster_base": {"direct": 44, "employee-assist": 44, "incumbent": 42, "chief-of-staff": 40,
                       "infra": 34, "vertical": 32, "data-intel": 30},
    "x_default_base": 45, "y_default_base": 36,
    "x_up": {}, "x_down": {}, "y_up": {}, "y_down": {},
    "x_up_cap": 28, "x_down_cap": 30, "y_up_cap": 34, "y_down_cap": 24,
    "clamp_lo": 8, "clamp_hi": 96,
}


def load_config(root: Path, explicit: str | None):
    path = Path(explicit) if explicit else root / "config/axes.json"
    if path.exists():
        cfg = json.loads(path.read_text(encoding="utf-8"))
        # fill any missing keys from BUILTIN so a partial config can't crash the scorer
        return {**BUILTIN, **cfg}
    return BUILTIN


def hits(patterns, text):
    return sum(pts for pat, pts in patterns.items() if re.search(pat, text, re.I))


def score_row(row, cfg):
    text = (row.get("what", "") + " " + row.get("why_tier", "")).lower()
    cluster = row.get("cluster", "")
    b = cfg["x_cluster_base"].get(cluster, cfg["x_default_base"])
    b += min(cfg["x_up_cap"], hits(cfg["x_up"], text)) - min(cfg["x_down_cap"], hits(cfg["x_down"], text))
    a = cfg["y_cluster_base"].get(cluster, cfg["y_default_base"])
    a += min(cfg["y_up_cap"], hits(cfg["y_up"], text)) - min(cfg["y_down_cap"], hits(cfg["y_down"], text))
    lo, hi = cfg["clamp_lo"], cfg["clamp_hi"]
    clamp = lambda v: max(lo, min(hi, round(v)))
    return clamp(b), clamp(a)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--config", default=None, help="axis config path (default: <root>/config/axes.json)")
    ap.add_argument("--write", action="store_true", help="also write data/axes.json")
    ap.add_argument("--all", action="store_true", help="include every row, not just the live-threat map set")
    args = ap.parse_args()
    root = Path(args.root)
    cfg = load_config(root, args.config)
    rows = list(csv.DictReader((root / "data/registry.csv").open(encoding="utf-8")))

    out = []
    for r in rows:
        b, a = score_row(r, cfg)
        on_map = r["status"] == "active" and r["tier"] in ("1", "2")  # live competitive threats
        out.append({
            "domain": r["domain"], "name": r["name"], "tier": r["tier"], "cluster": r["cluster"],
            "status": r["status"], "stage": r["stage"], "hq": r["hq"], "founded": r["founded"],
            "axis_breadth": b, "axis_action": a, "on_map": on_map, "what": r["what"],
        })
    shown = out if args.all else [o for o in out if o["on_map"]]
    payload = {"x_axis": cfg["x_axis"], "y_axis": cfg["y_axis"], "count": len(shown), "companies": shown}
    if args.write:
        (root / "data/axes.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
