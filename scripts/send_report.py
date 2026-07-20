#!/usr/bin/env python3
"""Email data/report.html after a scan. Stdlib-only (smtplib over SSL).

Env: MAIL_USER (gmail/workspace address), MAIL_PASSWORD (app password),
     MAIL_TO (required to send), MAIL_SMTP (default smtp.gmail.com), RADAR_TITLE (default "Pulse").
Sends the report inline AND attached. Exits 0 (skip, naming what's missing) if any
of MAIL_USER/MAIL_PASSWORD/MAIL_TO is unset.
"""
from __future__ import annotations

import csv
import json
import os
import re
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path


def main():
    user = os.environ.get("MAIL_USER", "")
    pw = os.environ.get("MAIL_PASSWORD", "")
    to = os.environ.get("MAIL_TO", "")
    host = os.environ.get("MAIL_SMTP", "smtp.gmail.com")
    if not pw or not user or not to:
        missing = [n for n, v in (("MAIL_USER", user), ("MAIL_PASSWORD", pw), ("MAIL_TO", to)) if not v]
        print(f"{'/'.join(missing)} not set — skipping email.")
        return

    root = Path(".")
    report = root / "data/report.html"
    if not report.exists():
        sys.exit("ERROR: data/report.html missing — run render_report.py first")

    state = json.loads((root / "data/state.json").read_text(encoding="utf-8"))
    run_date = state.get("last_run", "?")
    with (root / "data/registry.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    new = [r for r in rows if r.get("first_seen") == run_date]
    esc_dir = root / "runs" / run_date
    escalated = (esc_dir / "ESCALATION.md").exists()

    subject = f"{os.environ.get('RADAR_TITLE', 'Pulse')} {run_date}: +{len(new)} new"
    if new:
        subject += " (" + ", ".join(r["name"] for r in new[:4]) + ("…" if len(new) > 4 else "") + ")"
    if escalated:
        subject = "⚠ TIER-1 ALERT — " + subject

    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(f"Radar scan {run_date}: {len(new)} net-new companies, {len(rows)} tracked. "
                    "Open the attached report.html (or view inline in an HTML-capable client).")
    html = report.read_text(encoding="utf-8")
    msg.add_alternative(html, subtype="html")
    # attachment name follows the fork's RADAR_TITLE, not a hardcoded product name
    slug = re.sub(r"[^a-z0-9]+", "-", os.environ.get("RADAR_TITLE", "Pulse").lower()).strip("-")
    msg.add_attachment(html.encode("utf-8"), maintype="text", subtype="html",
                       filename=f"{slug}-{run_date}.html")

    with smtplib.SMTP_SSL(host, 465, context=ssl.create_default_context()) as s:
        s.login(user, pw)
        s.send_message(msg)
    print(f"Sent '{subject}' -> {to}")


if __name__ == "__main__":
    main()
