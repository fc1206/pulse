#!/usr/bin/env python3
"""Ping an external dead-man switch so a scan that NEVER RUNS gets noticed. Stdlib-only.

The failure this closes: `if: failure()` in scan.yml only fires inside a job that
actually started. If the scheduled run never fires — GitHub disables cron after
~60 days of repo inactivity, and this repo's only activity is its own scans — no
job runs, so nothing alerts. The radar dies silently. That is the exact class of
failure this project exists to prevent.

A heartbeat inverts the check: the scan pings an EXTERNAL monitor on every
success, and the monitor (e.g. a free Healthchecks.io check) alarms when an
expected ping is overdue. The watcher lives outside GitHub, so it survives
GitHub silently dropping the schedule.

Env: HEARTBEAT_URL (required to send; exits 0 quietly if unset, like the email path).
     Set it to a Healthchecks.io check URL (or any URL that records a GET as "alive").
Usage: python3 scripts/heartbeat.py [--status success|fail] [--root .] [--dry-run]

Wiring (scan.yml): ping success at the very end of a healthy run, and ping
`--status fail` from the `if: failure()` step so the monitor distinguishes
"ran and failed" from "never ran".
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path


def summary(root: Path) -> str:
    """A short human-readable line for the ping body (best-effort; never raises)."""
    try:
        st = json.loads((root / "data/state.json").read_text(encoding="utf-8"))
        return f"{os.environ.get('RADAR_TITLE', 'Pulse')} scan {st.get('last_run','?')} ({st.get('last_runner','?')})"
    except Exception:
        return os.environ.get("RADAR_TITLE", "Pulse") + " scan"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", choices=["success", "fail"], default="success")
    ap.add_argument("--root", default=".")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    base = os.environ.get("HEARTBEAT_URL", "").strip()
    # Healthchecks.io convention: append /fail to signal a failed run.
    url = base + "/fail" if (base and args.status == "fail") else base
    body = summary(Path(args.root)).encode("utf-8")

    if args.dry_run:
        print(f"[dry-run] would ping ({args.status}): {url or '<HEARTBEAT_URL unset>'}")
        return
    if not base:
        print("HEARTBEAT_URL not set — skipping heartbeat (no dead-man switch configured).")
        return
    try:
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "text/plain"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"Heartbeat ({args.status}): HTTP {resp.status}")
    except Exception as e:
        # Never fail the scan because the monitor was unreachable.
        print(f"::warning::heartbeat ping failed ({args.status}): {e}")


if __name__ == "__main__":
    main()
