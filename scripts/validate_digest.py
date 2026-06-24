#!/usr/bin/env python3
"""Lint runs/<date>/digest.md against config/digest-spec.md rules and, on pass,
prepend it to data/DIGEST.md. The ONLY writer of data/DIGEST.md. Stdlib-only.

Usage: python3 scripts/validate_digest.py --run-dir runs/2026-06-15 [--root .] [--dry-run]
"""
import argparse
import csv
import re
import sys
from pathlib import Path

MARKER = "<!-- entries below -->"
MAX_ITEMS = 5
MAX_CHARS = 6000

SLOP = [
    "rapidly evolving", "ever-changing", "landscape is shifting", "it's worth noting",
    "stay vigilant", "keep an eye", "monitor closely", "monitor the situation",
    "double down", "in conclusion", "game-chang", "cutting-edge", "synerg",
    "best-in-class", "world-class", "delve", "underscores the",
    "highlights the importance", "top of mind going forward", "actionable insights",
]
BAD_ACTION_OPENERS = ("monitor", "watch", "consider", "keep", "continue", "stay", "track", "explore")
REQUIRED_LABELS = ("**Signal:**", "**Why it matters:**", "**Action:**")


def lint(entry: str, registry_domains: set) -> list:
    errs = []
    if not re.match(r"^## \d{4}-\d{2}-\d{2} — digest \(\w+\)\s*$", entry.splitlines()[0]):
        errs.append("first line must be '## YYYY-MM-DD — digest (runner)'")
    if len(entry) > MAX_CHARS:
        errs.append(f"entry too long ({len(entry)} > {MAX_CHARS} chars) — cut to the sharp items")

    low = entry.lower()
    for phrase in SLOP:
        if phrase in low:
            errs.append(f"banned slop phrase: '{phrase}' — rewrite with specifics")

    if "NO ACTIONABLE SIGNAL" in entry:
        if re.search(r"^### ", entry, re.M):
            errs.append("entry declares NO ACTIONABLE SIGNAL but also contains items — pick one")
        return errs

    items = re.split(r"^### ", entry, flags=re.M)[1:]
    if not items:
        errs.append("no items and no 'NO ACTIONABLE SIGNAL' sentinel")
    if len(items) > MAX_ITEMS:
        errs.append(f"{len(items)} items > max {MAX_ITEMS} — keep only what clears the bar")

    for i, item in enumerate(items, 1):
        tag = f"item {i} ('{item.splitlines()[0][:50]}')"
        for label in REQUIRED_LABELS:
            if label not in item:
                errs.append(f"{tag}: missing {label}")
        cited = "http" in item or any(d in item for d in registry_domains)
        if not cited:
            errs.append(f"{tag}: no citation (needs an http link or a registry domain)")
        m = re.search(r"\*\*Action:\*\*\s*(.+)", item)
        if m:
            action = m.group(1).strip()
            first = re.sub(r"[^a-zA-Z].*", "", action.split()[0]).lower() if action.split() else ""
            if first in BAD_ACTION_OPENERS:
                errs.append(f"{tag}: action opens with '{first}' — that's the radar's job, not a human action. Name a deliverable or decision")
            if len(action) < 20:
                errs.append(f"{tag}: action too thin ('{action}') — what's the deliverable, who could own it?")
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    root, run_dir = Path(args.root), Path(args.run_dir)

    src = run_dir / "digest.md"
    if not src.exists():
        sys.exit(f"ERROR: {src} not found")
    entry = src.read_text(encoding="utf-8").strip()

    with (root / "data/registry.csv").open(encoding="utf-8") as f:
        domains = {r["domain"] for r in csv.DictReader(f)}

    errs = lint(entry, domains)
    if errs:
        print("DIGEST REJECTED — fix and re-run:\n  - " + "\n  - ".join(errs))
        sys.exit(1)

    if args.dry_run:
        print("DIGEST OK (dry-run, not written)")
        return

    dig_path = root / "data/DIGEST.md"
    doc = dig_path.read_text(encoding="utf-8")
    if MARKER not in doc:
        sys.exit(f"ERROR: marker '{MARKER}' missing from data/DIGEST.md")
    doc = doc.replace(MARKER, MARKER + "\n\n" + entry, 1)
    dig_path.write_text(doc, encoding="utf-8")
    n_items = len(re.split(r"^### ", entry, flags=re.M)) - 1
    print(f"DIGEST ACCEPTED: {max(n_items, 0)} item(s) prepended to data/DIGEST.md")


if __name__ == "__main__":
    main()
