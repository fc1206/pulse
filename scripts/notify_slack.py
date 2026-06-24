#!/usr/bin/env python3
"""Post the scan digest to Slack via incoming webhook. Stdlib-only.

Leads with the decision digest (data/DIGEST.md latest entry) when one exists for
this run; falls back to the raw new-company list otherwise.

Env: SLACK_WEBHOOK_URL (required to send; exits 0 quietly if unset).
Usage: python3 scripts/notify_slack.py [--dry-run]
"""
import csv
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

_REPO = os.environ.get("RADAR_REPO", "").strip()
_BASE = f"https://github.com/{_REPO}/blob/main/data" if _REPO else "."
REPORT_URL = f"{_BASE}/report.html"
DIGEST_URL = f"{_BASE}/DIGEST.md"
LANDSCAPE_URL = f"{_BASE}/LANDSCAPE.md"
TITLE = os.environ.get("RADAR_TITLE", "Pulse")


def latest_digest_entry(root: Path, run_date: str):
    """Return the newest digest entry if it matches run_date, else None."""
    p = root / "data/DIGEST.md"
    if not p.exists():
        return None
    doc = p.read_text(encoding="utf-8")
    m = re.search(r"^## (\d{4}-\d{2}-\d{2}) — digest.*?(?=^## \d{4}|\Z)", doc, re.M | re.S)
    if not m or m.group(1) != run_date:
        return None
    return m.group(0).strip()


def digest_lines(entry: str):
    if "NO ACTIONABLE SIGNAL" in entry:
        m = re.search(r"NO ACTIONABLE SIGNAL.*", entry)
        return ["_" + (m.group(0) if m else "No actionable signal this run.") + "_"]
    out = []
    for item in re.split(r"^### ", entry, flags=re.M)[1:]:
        head = re.sub(r"^\d+\.\s*", "", item.splitlines()[0]).strip()
        why = re.search(r"\*\*Why it matters:\*\*\s*(.+)", item)
        act = re.search(r"\*\*Action:\*\*\s*(.+)", item)
        out.append(f"*{head}*")
        if why:
            out.append(f"_{why.group(1).strip()}_")
        if act:
            out.append(f"→ {act.group(1).strip()}")
        out.append("")
    return out


def build_message(root: Path) -> str:
    state = json.loads((root / "data/state.json").read_text(encoding="utf-8"))
    run_date = state.get("last_run", "?")
    with (root / "data/registry.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    new = [r for r in rows if r.get("first_seen") == run_date]
    if len(new) >= len(rows):  # date collision (baseline day): derive from latest changelog Added list
        land = (root / "data/LANDSCAPE.md").read_text(encoding="utf-8")
        m = re.search(r"^### .*? — scan.*?\nAdded: (.*?)$", land, re.M | re.S)
        names = {n.strip() for n in re.findall(r"([^;]+?) \(T\d", m.group(1))} if m else set()
        new = [r for r in rows if r["name"] in names]
    esc_file = root / "runs" / run_date / "ESCALATION.md"

    lines = [f":satellite_antenna: *{TITLE} — scan {run_date}*",
             f"+{len(new)} new · {len(rows)} tracked", ""]
    if esc_file.exists():
        lines.insert(0, ":rotating_light: *NEW TIER-1 COMPETITOR DETECTED*")
        for ln in esc_file.read_text(encoding="utf-8").splitlines():
            if ln.startswith("## "):
                lines.insert(1, "> " + ln[3:])

    entry = latest_digest_entry(root, run_date)
    if entry:
        lines.append(":compass: *What it means / what to do:*")
        lines.extend(digest_lines(entry))
    elif new:
        for r in new[:8]:
            what = r.get("what", "")
            what = what if len(what) <= 140 else what[:137] + "…"
            lines.append(f"• *{r['name']}* (T{r['tier']}, {r['cluster']}) — {what}")
    else:
        lines.append("No net-new companies — verified zero (see scan log).")

    lines.append(f"<{DIGEST_URL}|Digest history> · <{REPORT_URL}|Full HTML report> · <{LANDSCAPE_URL}|Landscape map>")
    return "\n".join(lines)


def main():
    dry = "--dry-run" in sys.argv
    hook = os.environ.get("SLACK_WEBHOOK_URL", "")
    text = build_message(Path("."))
    if dry:
        print(text)
        return
    if not hook:
        print("SLACK_WEBHOOK_URL not set — skipping Slack notify.")
        return
    req = urllib.request.Request(
        hook,
        data=json.dumps({"text": text}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        print(f"Slack notify: HTTP {resp.status}")


if __name__ == "__main__":
    main()
