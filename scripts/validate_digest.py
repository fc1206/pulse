#!/usr/bin/env python3
"""Lint runs/<date>/digest.md against config/digest-spec.md rules and, on pass,
prepend it to data/DIGEST.md and log its Action lines to data/ACTIONS.md.
The ONLY writer of data/DIGEST.md and data/ACTIONS.md. Stdlib-only.

Usage:
  python3 scripts/validate_digest.py --run-dir runs/2026-06-15 [--root .] [--dry-run]
  python3 scripts/validate_digest.py --backfill [--root .]
  python3 scripts/validate_digest.py --resolve 2026-06-15.1 --status done [--note "..."]
"""
import argparse
import csv
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

MARKER = "<!-- entries below -->"
ACTIONS_MARKER = "<!-- rows below -->"
MAX_ITEMS = 2
MAX_CHARS = 6000
EXCERPT_CHARS = 140
# fork-specific digest label lives in config/brand.json ("why_label"); this is
# the generic fallback so the template works before any branding exists.
DEFAULT_WHY_LABEL = "Why it matters:"

# data/ACTIONS.md scaffold, created on first extraction.
ACTIONS_HEADER = """# Action Ledger

Digest Action lines, extracted by scripts/validate_digest.py — the only writer of
this file. Never hand-edit. Row format (one action per line):

    - <id> | <status>[ <resolved YYYY-MM-DD>] | due <YYYY-MM-DD or -> | <excerpt>[ | note: <text>]

Statuses: open, done, dropped, deferred. Close the loop with (writes are env-gated,
and --resolve is inherently a local maintenance command):
RADAR_ALLOW_WRITE=1 python3 scripts/validate_digest.py --resolve <id> --status done|dropped|deferred [--note "..."]

<!-- rows below -->
"""

SLOP = [
    "rapidly evolving", "ever-changing", "landscape is shifting", "it's worth noting",
    "stay vigilant", "keep an eye", "monitor closely", "monitor the situation",
    "double down", "in conclusion", "game-chang", "cutting-edge", "synerg",
    "best-in-class", "world-class", "delve", "underscores the",
    "highlights the importance", "top of mind going forward", "actionable insights",
]
BAD_ACTION_OPENERS = ("monitor", "watch", "consider", "keep", "continue", "stay", "track", "explore")

ROW_RE = re.compile(
    r"^- (\d{4}-\d{2}-\d{2}\.\d+) \| (open|done|dropped|deferred)"
    r"(?: (\d{4}-\d{2}-\d{2}))? \| due (\d{4}-\d{2}-\d{2}|-) \| (.*)$")

# The Action is a PARAGRAPH: it runs to the next blank line, the next bold
# **Label:** line, or the end of the item. A first-line-only capture would drop a
# wrapped line's "by YYYY-MM-DD" due date and truncate the excerpt.
ACTION_RE = re.compile(r"\*\*Action:\*\*[^\S\n]*(.+?)(?=\n\s*\n|\n\*\*[^*\n]*:\*\*|\Z)", re.S)


def action_text(item: str):
    """Whole Action paragraph, whitespace-normalized to one line, pipes replaced
    (pipe is the ledger row delimiter). None when the item has no Action label."""
    m = ACTION_RE.search(item)
    if not m:
        return None
    return " ".join(m.group(1).split()).replace("|", "/")


def required_labels(root: Path) -> tuple:
    try:
        label = json.loads((root / "config/brand.json").read_text(encoding="utf-8")).get("why_label")
    except (OSError, ValueError):
        label = None
    return ("**Signal:**", f"**{label or DEFAULT_WHY_LABEL}**", "**Action:**")


def require_write_auth():
    # single canonical writer guard — same convention as validate_merge.py: only
    # GitHub Actions (the canonical runner) writes data/*; an intentional local
    # run must opt in explicitly (and `git pull` first).
    if not os.environ.get("GITHUB_ACTIONS") and os.environ.get("RADAR_ALLOW_WRITE") != "1":
        sys.exit(
            "REFUSING TO WRITE: not the canonical runner (GitHub Actions). "
            "Set RADAR_ALLOW_WRITE=1 for an intentional, pull-first local run."
        )


def atomic_write(path: Path, text: str):
    # atomic replace: a torn write must never leave a half-written data file
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def lint(entry: str, registry_domains: set, labels: tuple) -> list:
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
        for label in labels:
            if label not in item:
                errs.append(f"{tag}: missing {label}")
        cited = "http" in item or any(d in item for d in registry_domains)
        if not cited:
            errs.append(f"{tag}: no citation (needs an http link or a registry domain)")
        action = action_text(item)
        if action is not None:
            first = re.sub(r"[^a-zA-Z].*", "", action.split()[0]).lower() if action.split() else ""
            if first in BAD_ACTION_OPENERS:
                errs.append(f"{tag}: action opens with '{first}' — that's the radar's job, not a human action. Name a deliverable or decision")
            if len(action) < 20:
                errs.append(f"{tag}: action too thin ('{action}') — what's the deliverable, who could own it?")
    return errs


def extract_actions(entry: str) -> list:
    """[(id, due, excerpt)] for one digest entry; ids are <entry-date>.<item-n>."""
    m = re.match(r"^## (\d{4}-\d{2}-\d{2})", entry)
    if not m:
        return []
    rows = []
    for i, item in enumerate(re.split(r"^### ", entry, flags=re.M)[1:], 1):
        action = action_text(item)  # full paragraph, normalized (see ACTION_RE)
        if not action:
            continue
        dm = re.search(r"\bby (\d{4}-\d{2}-\d{2})", action)
        rows.append((f"{m.group(1)}.{i}", dm.group(1) if dm else "-", action[:EXCERPT_CHARS]))
    return rows


def append_actions(root: Path, entries: list) -> int:
    """Append an open row per not-yet-logged action. Dedupe is by DATE-SCOPED EXCERPT,
    not bare id: a second same-date entry (recovery runs are real) would otherwise
    collide on <date>.<n> and be silently dropped forever — and --resolve could hit
    the wrong action. A true retry (same date, same excerpt) is skipped; a new action
    whose computed id is taken gets the next free <date>.<n>. Idempotent."""
    path = root / "data/ACTIONS.md"
    doc = path.read_text(encoding="utf-8") if path.exists() else ACTIONS_HEADER
    if ACTIONS_MARKER not in doc:
        sys.exit(f"ERROR: marker '{ACTIONS_MARKER}' missing from data/ACTIONS.md")
    ids, logged = set(), {}  # logged: date -> {excerpt} already in the ledger
    for line in doc.splitlines():
        if m := ROW_RE.match(line):
            ids.add(m.group(1))
            d = m.group(1).split(".", 1)[0]
            logged.setdefault(d, set()).add(m.group(5).split(" | note: ", 1)[0])
    new = []
    for entry in entries:
        for rid, due, excerpt in extract_actions(entry):
            d = rid.split(".", 1)[0]
            if excerpt in logged.get(d, set()):
                continue  # true retry of an already-logged action
            if rid in ids:  # id taken by a DIFFERENT action → next free slot
                n = int(rid.split(".", 1)[1])
                while f"{d}.{n}" in ids:
                    n += 1
                rid = f"{d}.{n}"
            ids.add(rid)
            logged.setdefault(d, set()).add(excerpt)
            new.append(f"- {rid} | open | due {due} | {excerpt}")
    if new:
        atomic_write(path, doc.rstrip("\n") + "\n" + "\n".join(new) + "\n")
    return len(new)


def resolve_action(root: Path, rid: str, status: str, note: str):
    path = root / "data/ACTIONS.md"
    if not path.exists():
        sys.exit("ERROR: data/ACTIONS.md not found — nothing to resolve")
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        m = ROW_RE.match(line)
        if m and m.group(1) == rid:
            excerpt = m.group(5).split(" | note: ", 1)[0]  # drop any prior note
            row = f"- {rid} | {status} {date.today().isoformat()} | due {m.group(4)} | {excerpt}"
            if note:
                row += " | note: " + " ".join(note.split()).replace("|", "/")
            lines[i] = row
            atomic_write(path, "\n".join(lines) + "\n")
            print(f"ACTION {rid} → {status}")
            return
    sys.exit(f"ERROR: unknown action id '{rid}' — see data/ACTIONS.md for valid ids")


def digest_entries(root: Path) -> list:
    path = root / "data/DIGEST.md"
    if not path.exists():
        sys.exit(f"ERROR: {path} not found")
    doc = path.read_text(encoding="utf-8")
    body = doc.split(MARKER, 1)[1] if MARKER in doc else doc
    return ["## " + e for e in re.split(r"^## ", body, flags=re.M)[1:]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir")
    ap.add_argument("--root", default=".")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--backfill", action="store_true",
                    help="log Action rows from every entry already in data/DIGEST.md (idempotent)")
    ap.add_argument("--resolve", metavar="ID", help="close an action row (requires --status)")
    ap.add_argument("--status", choices=("done", "dropped", "deferred"))
    ap.add_argument("--note", default="")
    args = ap.parse_args()
    root = Path(args.root)

    if args.resolve:
        if not args.status:
            ap.error("--resolve requires --status {done,dropped,deferred}")
        require_write_auth()
        resolve_action(root, args.resolve, args.status, args.note)
        return
    if args.backfill:
        require_write_auth()
        n = append_actions(root, digest_entries(root))
        print(f"BACKFILL OK: {n} action row(s) added to data/ACTIONS.md")
        return
    if not args.run_dir:
        ap.error("--run-dir is required (or use --backfill / --resolve)")

    run_dir = Path(args.run_dir)
    src = run_dir / "digest.md"
    if not src.exists():
        sys.exit(f"ERROR: {src} not found")
    entry = src.read_text(encoding="utf-8").strip()

    with (root / "data/registry.csv").open(encoding="utf-8") as f:
        domains = {r["domain"] for r in csv.DictReader(f)}

    errs = lint(entry, domains, required_labels(root))
    if errs:
        print("DIGEST REJECTED — fix and re-run:\n  - " + "\n  - ".join(errs))
        sys.exit(1)

    if args.dry_run:
        print("DIGEST OK (dry-run, not written)")
        return

    require_write_auth()
    dig_path = root / "data/DIGEST.md"
    doc = dig_path.read_text(encoding="utf-8")
    if MARKER not in doc:
        sys.exit(f"ERROR: marker '{MARKER}' missing from data/DIGEST.md")
    doc = doc.replace(MARKER, MARKER + "\n\n" + entry, 1)
    # ledger first: re-running after a failure converges (append skips known ids;
    # the DIGEST prepend, by contrast, would duplicate the entry on a blind retry)
    n_actions = append_actions(root, [entry])
    atomic_write(dig_path, doc)
    n_items = len(re.split(r"^### ", entry, flags=re.M)) - 1
    print(f"DIGEST ACCEPTED: {max(n_items, 0)} item(s) prepended to data/DIGEST.md; "
          f"{n_actions} action row(s) logged to data/ACTIONS.md")


if __name__ == "__main__":
    main()
