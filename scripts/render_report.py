#!/usr/bin/env python3
"""Render data/report.html from the system of record. Deterministic, stdlib-only.

Reads registry.csv, state.json, SCANLOG.md, LANDSCAPE.md. Never written by the
model — this script is the only producer of report.html.

Usage: python3 scripts/render_report.py [--root .] [--out data/report.html]
"""
import argparse
import csv
import html
import json
import os
import re
from datetime import date
from pathlib import Path

TITLE = os.environ.get("RADAR_TITLE", "Pulse")
REPO = os.environ.get("RADAR_REPO", "").strip()

TIER_META = {
    "1": ("T1 · direct lane", "#ff5d5d"),
    "2": ("T2 · adjacent", "#5da9ff"),
    "3": ("T3 · context", "#9aa3ad"),
}
STATUS_BADGE = {"acquired": "#b08cff", "dead": "#6b7280", "feature": "#46c28e"}


def esc(s):
    return html.escape(str(s or ""), quote=True)


def load(root: Path):
    with (root / "data/registry.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    state = json.loads((root / "data/state.json").read_text(encoding="utf-8"))
    scanlog = (root / "data/SCANLOG.md").read_text(encoding="utf-8")
    landscape = (root / "data/LANDSCAPE.md").read_text(encoding="utf-8")
    digest_p = root / "data/DIGEST.md"
    digest = digest_p.read_text(encoding="utf-8") if digest_p.exists() else ""
    return rows, state, scanlog, landscape, digest


def latest_scan_notes(scanlog: str) -> str:
    """Last '## ...' section of the scan log."""
    parts = re.split(r"^## ", scanlog, flags=re.M)
    return ("## " + parts[-1]).strip() if len(parts) > 1 else ""


def threat_top5(landscape: str):
    m = re.search(r"## Threat assessment.*?\n(.*?)\n## ", landscape, re.S)
    if not m:
        return []
    items = re.findall(r"^\d+\.\s+(.*)$", m.group(1), re.M)
    return [re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", esc_keep_strong(i)) for i in items[:5]]


def esc_keep_strong(s: str) -> str:
    """Escape, but allow the ** -> <strong> conversion afterwards."""
    return html.escape(s, quote=False)


def render(root: Path, out: Path):
    rows, state, scanlog, landscape, digest = load(root)
    run_date = state.get("last_run", date.today().isoformat())
    runner = state.get("last_runner", "?")
    tiers = {t: [r for r in rows if r["tier"] == t] for t in ("1", "2", "3")}
    new_rows = [r for r in rows if r.get("first_seen") == run_date]
    if len(new_rows) >= len(rows):  # baseline day: dates can't distinguish — use the changelog's Added list
        m = re.search(r"^### .*? — scan.*?\nAdded: (.*?)$", landscape, re.M | re.S)
        names = set()
        if m:
            names = {n.strip() for n in re.findall(r"([^;]+?) \(T\d", m.group(1))}
        new_rows = [r for r in rows if r["name"] in names]
    new_domains = {r["domain"] for r in new_rows}
    threats = threat_top5(landscape)
    notes = latest_scan_notes(scanlog)

    digest_html = ""
    dm = re.search(r"^## (\d{4}-\d{2}-\d{2}) — digest.*?(?=^## \d{4}|\Z)", digest, re.M | re.S)
    if dm:
        d = esc(dm.group(0).strip())
        d = re.sub(r"^## (.*)$", r'<div class="dghead">\1</div>', d, count=1, flags=re.M)
        d = re.sub(r"^### (.*)$", r'<div class="dgitem">\1</div>', d, flags=re.M)
        d = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", d)
        d = re.sub(r"(https?://[^\s<)]+)", r'<a href="\1" target="_blank" rel="noopener">\1</a>', d)
        digest_html = d.replace("\n", "<br>")

    def row_html(r):
        label, color = TIER_META.get(r["tier"], ("T?", "#888"))
        status = r.get("status", "")
        sbadge = ""
        if status in STATUS_BADGE:
            sbadge = f'<span class="badge" style="background:{STATUS_BADGE[status]}22;color:{STATUS_BADGE[status]}">{esc(status)}</span>'
        is_new = ' data-new="1"' if r["domain"] in new_domains else ""
        newtag = '<span class="badge new">NEW</span>' if is_new else ""
        ev = esc(r.get("evidence_url", ""))
        return (
            f'<tr data-tier="{esc(r["tier"])}"{is_new}>'
            f'<td><div class="nm">{esc(r["name"])} {newtag}</div>'
            f'<a class="dom" href="https://{esc(r["domain"])}" target="_blank" rel="noopener">{esc(r["domain"])}</a></td>'
            f'<td><span class="badge" style="background:{color}22;color:{color}">{label.split(" ")[0]}</span> {sbadge}</td>'
            f'<td>{esc(r.get("cluster", ""))}</td>'
            f'<td>{esc(r.get("stage", ""))}</td>'
            f'<td>{esc(r.get("hq", ""))}</td>'
            f'<td class="dt">{esc(r.get("first_seen", ""))}</td>'
            f'<td class="what">{esc(r.get("what", ""))}'
            f'<div class="why">{esc(r.get("why_tier", ""))}'
            + (f' · <a href="{ev}" target="_blank" rel="noopener">evidence</a>' if ev.startswith("http") else "")
            + (f'<div class="note">⚠ {esc(r["notes"])}</div>' if r.get("notes") else "")
            + "</div></td></tr>"
        )

    body_rows = "\n".join(row_html(r) for r in sorted(rows, key=lambda r: (r["tier"], r["name"].lower())))

    new_cards = "".join(
        f'<div class="card"><div class="nm">{esc(r["name"])} '
        f'<span class="badge" style="background:{TIER_META[r["tier"]][1]}22;color:{TIER_META[r["tier"]][1]}">T{esc(r["tier"])}</span></div>'
        f'<div class="cl">{esc(r["cluster"])} · {esc(r["stage"])} · {esc(r["hq"])}</div>'
        f'<div class="wt">{esc(r["what"])}</div>'
        f'<div class="why">{esc(r["why_tier"])}</div></div>'
        for r in new_rows
    ) or '<div class="quiet">No net-new companies this run — and that is a verified zero, not an unchecked one.</div>'

    threat_html = "".join(f"<li>{t}</li>" for t in threats)
    notes_html = esc(notes).replace("\n", "<br>")

    repo_html = f'Repo: <a href="https://github.com/{REPO}">{REPO}</a> · ' if REPO else ""
    doc = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(TITLE)} — {esc(run_date)}</title>
<style>
:root {{ color-scheme: dark; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:#0d1117; color:#e6edf3; font:14px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif; }}
.wrap {{ max-width:1180px; margin:0 auto; padding:32px 20px 80px; }}
h1 {{ font-size:22px; margin:0; letter-spacing:.04em; }}
h1 .accent {{ color:#5da9ff; }}
h2 {{ font-size:15px; text-transform:uppercase; letter-spacing:.08em; color:#9aa3ad; margin:36px 0 12px; }}
.meta {{ color:#9aa3ad; margin-top:6px; }}
.stats {{ display:flex; gap:12px; flex-wrap:wrap; margin-top:18px; }}
.stat {{ background:#161b22; border:1px solid #21262d; border-radius:10px; padding:12px 18px; min-width:110px; }}
.stat b {{ display:block; font-size:22px; }}
.stat span {{ color:#9aa3ad; font-size:12px; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(330px,1fr)); gap:12px; }}
.card {{ background:#161b22; border:1px solid #21262d; border-left:3px solid #5da9ff; border-radius:10px; padding:14px 16px; }}
.card .nm {{ font-weight:600; }}
.card .cl {{ color:#9aa3ad; font-size:12px; margin:4px 0 8px; }}
.card .wt {{ margin-bottom:6px; }}
.card .why {{ color:#9aa3ad; font-size:12.5px; }}
.quiet {{ color:#9aa3ad; background:#161b22; border:1px dashed #21262d; border-radius:10px; padding:16px; }}
ol.threats {{ padding-left:20px; }} ol.threats li {{ margin-bottom:8px; }}
.controls {{ display:flex; gap:10px; flex-wrap:wrap; margin-bottom:12px; }}
input[type=search] {{ flex:1; min-width:220px; background:#161b22; border:1px solid #30363d; border-radius:8px; color:#e6edf3; padding:8px 12px; font-size:14px; }}
button.f {{ background:#161b22; border:1px solid #30363d; border-radius:8px; color:#9aa3ad; padding:7px 14px; cursor:pointer; font-size:13px; }}
button.f.on {{ color:#e6edf3; border-color:#5da9ff; }}
table {{ width:100%; border-collapse:collapse; }}
th {{ text-align:left; color:#9aa3ad; font-size:12px; text-transform:uppercase; letter-spacing:.05em; padding:8px 10px; border-bottom:1px solid #30363d; cursor:pointer; white-space:nowrap; }}
td {{ padding:10px; border-bottom:1px solid #21262d; vertical-align:top; }}
td .nm {{ font-weight:600; }}
a.dom {{ color:#5da9ff; font-size:12px; text-decoration:none; }}
td.what {{ max-width:430px; }}
.why {{ color:#9aa3ad; font-size:12px; margin-top:4px; }}
.why a {{ color:#5da9ff; }}
.note {{ color:#d29922; font-size:12px; margin-top:3px; }}
.dt {{ white-space:nowrap; color:#9aa3ad; font-size:12.5px; }}
.badge {{ display:inline-block; border-radius:20px; padding:2px 9px; font-size:11.5px; font-weight:600; }}
.badge.new {{ background:#23863622; color:#3fb950; border:1px solid #3fb95055; }}
.lognotes {{ background:#161b22; border:1px solid #21262d; border-radius:10px; padding:14px 16px; color:#bac3cc; font-size:13px; }}
.foot {{ margin-top:40px; color:#6b7280; font-size:12px; }}
.foot a {{ color:#5da9ff; }}
@media print {{ body {{ background:#fff; color:#111; }} }}
</style></head><body><div class="wrap">

<h1>{esc(TITLE)}</h1>
<div class="meta">Competitive landscape · scan of <b>{esc(run_date)}</b> ({esc(runner)}) · system of record: <code>data/registry.csv</code></div>

<div class="stats">
  <div class="stat"><b>{len(rows)}</b><span>companies tracked</span></div>
  <div class="stat"><b style="color:#ff5d5d">{len(tiers['1'])}</b><span>Tier 1 · direct lane</span></div>
  <div class="stat"><b style="color:#5da9ff">{len(tiers['2'])}</b><span>Tier 2 · adjacent</span></div>
  <div class="stat"><b style="color:#9aa3ad">{len(tiers['3'])}</b><span>Tier 3 · context</span></div>
  <div class="stat"><b style="color:#3fb950">{len(new_rows)}</b><span>new this run</span></div>
</div>

<h2>Decision digest — what it means, what to do</h2>
<div class="lognotes" style="border-left:3px solid #3fb950">{digest_html if digest_html else 'No digest entry for this scan yet — see <code>data/DIGEST.md</code>.'}</div>

<h2>New this run</h2>
<div class="cards">{new_cards}</div>

<h2>Current threat assessment — top 5</h2>
<ol class="threats">{threat_html}</ol>

<h2>Full registry</h2>
<div class="controls">
  <input type="search" id="q" placeholder="Search name, domain, description, cluster…">
  <button class="f on" data-t="all">All</button>
  <button class="f" data-t="1">Tier 1</button>
  <button class="f" data-t="2">Tier 2</button>
  <button class="f" data-t="3">Tier 3</button>
  <button class="f" data-t="new">New</button>
</div>
<table id="reg"><thead><tr>
<th>Company</th><th>Tier</th><th>Cluster</th><th>Stage</th><th>HQ</th><th>First seen</th><th>What / why it matters</th>
</tr></thead><tbody>
{body_rows}
</tbody></table>

<h2>Latest scan log</h2>
<div class="lognotes">{notes_html}</div>

<div class="foot">Generated by <code>scripts/render_report.py</code> — deterministic render of the registry; the model never writes this file.
{repo_html}Narrative map: <code>data/LANDSCAPE.md</code> · Audit: <code>data/SCANLOG.md</code></div>

</div>
<script>
(function() {{
  var q = document.getElementById('q'), rows = Array.prototype.slice.call(document.querySelectorAll('#reg tbody tr'));
  var mode = 'all';
  function apply() {{
    var t = (q.value || '').toLowerCase();
    rows.forEach(function(r) {{
      var okMode = mode === 'all' || (mode === 'new' ? r.hasAttribute('data-new') : r.getAttribute('data-tier') === mode);
      var okText = !t || r.textContent.toLowerCase().indexOf(t) !== -1;
      r.style.display = (okMode && okText) ? '' : 'none';
    }});
  }}
  q.addEventListener('input', apply);
  document.querySelectorAll('button.f').forEach(function(b) {{
    b.addEventListener('click', function() {{
      document.querySelectorAll('button.f').forEach(function(x) {{ x.classList.remove('on'); }});
      b.classList.add('on'); mode = b.getAttribute('data-t'); apply();
    }});
  }});
}})();
</script>
</body></html>"""
    out.write_text(doc, encoding="utf-8")
    print(f"report.html: {len(rows)} rows, {len(new_rows)} new, {len(threats)} threats → {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    root = Path(a.root)
    out = Path(a.out) if a.out else root / "data/report.html"
    render(root, out)


if __name__ == "__main__":
    main()
