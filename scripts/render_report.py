#!/usr/bin/env python3
"""Render data/report.html — the branded, designed deliverable.

Generates the Pulse "company radar" dashboard (warm hero, radar-activity sparkline,
companies list, an auto-selected spotlight card, the breadth x action map, the
decision digest, and the full registry) deterministically from the registry. Brand
+ accent come from config/brand.json. Stdlib-only; the model never writes this file.

Usage: python3 scripts/render_report.py [--root .] [--out data/report.html]
"""
import argparse
import csv
import html
import json
import math
import os
import re
from datetime import date
from pathlib import Path

import score_axes  # sibling in scripts/; computes the map coordinates

FRONTIER_K = 8  # the map NAMES only the K competitors nearest the convergence corner; the rest are a density field

DEFAULT_BRAND = {
    "product": os.environ.get("RADAR_TITLE", "Pulse"),
    "company": "",
    "tagline": "Your competitive landscape, swept twice a week — every entrant tiered, sourced to a live link, and told straight.",
    "accent": "#fc4b32",
    "accent_2": "#e0a44d",
    "logo": "",
    "theme": "light",
    "repo_url": os.environ.get("RADAR_REPO", "").strip(),
}


def esc(s):
    return html.escape(str(s or ""), quote=True)


def esc_ks(s):
    return html.escape(s, quote=False)


def md_inline(s):
    s = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", s)
    return re.sub(r"(https?://[^\s<)\]]+)", r'<a href="\1" target="_blank" rel="noopener">link</a>', s)


def _rgba(hexc, a):
    h = (hexc or "").lstrip("#")
    if len(h) != 6:
        return hexc
    return f"rgba({int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)},{a})"


def load(root):
    rows = list(csv.DictReader((root / "data/registry.csv").open(encoding="utf-8")))
    state = json.loads((root / "data/state.json").read_text(encoding="utf-8"))
    scanlog = (root / "data/SCANLOG.md").read_text(encoding="utf-8")
    landscape = (root / "data/LANDSCAPE.md").read_text(encoding="utf-8")
    dp = root / "data/DIGEST.md"
    digest = dp.read_text(encoding="utf-8") if dp.exists() else ""
    brand = dict(DEFAULT_BRAND)
    bp = root / "config/brand.json"
    if bp.exists():
        try:
            brand.update({k: v for k, v in json.loads(bp.read_text(encoding="utf-8")).items()
                          if not k.startswith("_") and v not in (None, "")})
        except Exception:
            pass
    return rows, state, scanlog, landscape, digest, brand


def parse_funding(*texts):
    for t in texts:
        m = re.search(r"\$\s?(\d[\d.]*)\s?([MB])\b", t or "")
        if m:
            return f"${m.group(1)}{m.group(2)}"
    return ""


def known(v):
    """A metadata value, or '' if empty/unknown (so the UI can omit/dim it gracefully)."""
    v = str(v or "").strip()
    return "" if not v or v.lower() == "unknown" else v


def confidence(r):
    """How well-sourced a row is, from how many core fields are verified + evidence present."""
    n = sum(1 for k in ("stage", "hq", "founded") if known(r.get(k))) + \
        (1 if str(r.get("evidence_url", "")).startswith("http") else 0)
    return "verified" if n >= 3 else ("partial" if n >= 1 else "thin")


CONF_LABEL = {"verified": "verified", "partial": "partial source", "thin": "thin source"}


def _tile(label, val):
    """A metadata tile; dims to a faint em-dash when the value is empty/unknown."""
    v = known(val)
    return f'<div class="tile{"" if v else " dim"}"><div class="lab">{esc(label)}</div><div class="tv">{esc(v or "—")}</div></div>'


def activity_series(scanlog):
    """Per real scan: (date, tracked_cumulative, new) from SCANLOG. No synthetic ramp —
    returns 0, 1, or many points; the renderer shows an honest 'first scan' state for <2."""
    pts, cum = [], 0
    for blk in re.split(r"^## ", scanlog, flags=re.M)[1:]:
        dm = re.match(r"(\d{4}-\d{2}-\d{2})", blk)
        if not dm:
            continue
        nm = re.search(r"net-new added:\s*(\d+)", blk)
        cum += int(nm.group(1)) if nm else 0
        pts.append((dm.group(1)[5:], cum, int(nm.group(1)) if nm else 0))
    return pts[-6:]


def digest_items(digest):
    m = re.search(r"^## (\d{4}-\d{2}-\d{2}) — digest.*?(?=^## \d{4}|\Z)", digest, re.M | re.S)
    if not m:
        return None, []
    block, ddate = m.group(0), m.group(1)
    if "NO ACTIONABLE SIGNAL" in block:
        return ddate, "NO ACTIONABLE SIGNAL — this run's findings didn't clear the action bar. A quiet week is signal too."
    items = []
    for chunk in re.split(r"^### ", block, flags=re.M)[1:]:
        head = re.sub(r"^\d+\.\s*", "", chunk.splitlines()[0].strip())
        def f(name):
            fm = re.search(rf"\*\*{name}:\*\*\s*(.*?)(?=\n\*\*|\Z)", chunk, re.S)
            return fm.group(1).strip().replace("\n", " ") if fm else ""
        items.append({"head": head, "signal": f("Signal"), "why": f("Why it matters"), "action": f("Action")})
    return ddate, items


def pick_spotlight(rows, run_date):
    """Featured company: prefer the newest active Tier-1 that has VERIFIED metadata (so the
    hero card isn't full of 'unknown'), then fall back through looser pools."""
    active = [r for r in rows if r.get("status") == "active"]
    verified = lambda r: all(known(r.get(k)) for k in ("stage", "founded", "hq"))
    pools = ([r for r in active if r["tier"] == "1" and verified(r)],
             [r for r in active if r["tier"] == "1"],
             [r for r in active if r["tier"] in ("1", "2") and verified(r)],
             [r for r in active if r["tier"] in ("1", "2")], active)
    for pool in pools:
        if pool:
            return sorted(pool, key=lambda r: (r.get("first_seen", ""), r["tier"]), reverse=True)[0]
    return rows[0] if rows else None


def threat_top(landscape, n=5):
    m = re.search(r"## Threat assessment.*?\n(.*?)\n## ", landscape, re.S)
    items = re.findall(r"^\d+\.\s+(.*)$", m.group(1), re.M)[:n] if m else []
    return [md_inline(esc_ks(i)) for i in items]


def map_data(rows, root, run_date):
    """The Frontier: rank every active Tier-1/2 by distance to the top-right (convergence)
    corner; NAME the K nearest, render the rest as a faint tier-coloured density field.
    Exactly K labels exist regardless of registry size, so the static render never collides."""
    try:
        cfg = score_axes.load_config(root, None)
        pts = []
        for r in rows:
            if r.get("status") != "active" or r.get("tier") not in ("1", "2"):
                continue
            b, a = score_axes.score_row(r, cfg)
            meta = " · ".join(p for p in [r.get("stage", ""), parse_funding(r.get("what", ""), r.get("notes", "")),
                              r.get("hq", ""), (("est. " + r["founded"]) if r.get("founded") not in ("", "unknown") else "")]
                              if p and p != "unknown")
            pts.append({"n": r["name"], "d": r["domain"], "t": int(r["tier"]), "x": b, "y": a,
                        "m": meta, "w": (r.get("what", "") or "")[:130],
                        "new": 1 if r.get("first_seen") == run_date else 0})
        # rank by proximity to convergence corner; deterministic tie-break (tier → name)
        pts.sort(key=lambda p: (round(math.hypot(100 - p["x"], 100 - p["y"]), 2), p["t"], p["n"]))
        named = pts[:FRONTIER_K]
        faint = [{"x": p["x"], "y": p["y"], "t": p["t"]} for p in pts[FRONTIER_K:]]
        return named, faint, len(faint), cfg["x_axis"], cfg["y_axis"]
    except Exception:
        return [], [], 0, {"low": "narrow", "high": "broad"}, {"low": "retrieves", "high": "acts"}


def render(root, out):
    rows, state, scanlog, landscape, digest, brand = load(root)
    accent, accent2 = brand["accent"], brand["accent_2"]
    product = brand["product"]
    company = brand["company"]
    run_date = state.get("last_run", date.today().isoformat())
    tiers = {t: [r for r in rows if r["tier"] == t] for t in ("1", "2", "3")}
    new_rows = [r for r in rows if r.get("first_seen") == run_date]
    if rows and len(new_rows) >= len(rows):
        m = re.search(r"^### .*? — scan.*?\nAdded: (.*?)$", landscape, re.M | re.S)
        names = {n.strip() for n in re.findall(r"([^;]+?) \(T\d", m.group(1))} if m else set()
        new_rows = [r for r in rows if r["name"] in names]
    new_names = {r["name"] for r in new_rows}

    # ---- radar activity sparkline ----
    series = activity_series(scanlog)
    first_scan = len(series) < 2
    if first_scan:  # only the seed/first scan so far — flat baseline, never a fake ramp
        total = len(rows)
        series = [("baseline", total, 0), ("now", total, len(new_rows))]
    activity_note = ('<div class="cap" style="margin-top:7px">First scan — your activity trend builds from here.</div>'
                     if first_scan else "")
    xs = [i / max(1, len(series) - 1) for i in range(len(series))]
    tmax = max([c for _, c, _ in series] + [1])
    def line(idxs, vals, vmax):
        pts = []
        for i, v in zip(idxs, vals):
            x = 8 + i * 304
            y = 104 - (v / max(1, vmax)) * 74
            pts.append(f"{x:.0f},{y:.0f}")
        return " ".join(pts)
    track_line = line(xs, [c for _, c, _ in series], tmax)
    new_vals = [n for _, _, n in series]
    new_line = line(xs, new_vals, max(new_vals + [1]))
    xlabels = "".join(f"<span>{esc(d)}</span>" for d, _, _ in series)
    net30 = sum(n for _, _, n in series)

    # ---- companies list (active T1 first; clickable drill-down to the detail panel) ----
    order = sorted([r for r in rows if r.get("status") == "active"],
                   key=lambda r: (r["tier"], 0 if r["name"] in new_names else 1, r["name"].lower()))
    crows = ""
    for r in order:
        t = r["tier"]
        av = "av1" if t == "1" else "av2"
        chip = "t1" if t == "1" else "t2"
        stage = known(r.get("stage")).replace("series-", "Series ").title()
        tail = (("est. " + r["founded"]) if known(r.get("founded")) else known(r.get("hq")))
        sub = " · ".join(p for p in [stage, parse_funding(r.get("what", ""), r.get("notes", "")), tail] if p)
        newt = ' <span class="pill pf" style="padding:1px 7px;font-size:9px">New</span>' if r["name"] in new_names else ""
        crows += (f'<button class="crow" type="button" data-domain="{esc(r["domain"])}"><div class="mav {av}">{esc(r["name"][0])}</div>'
                  f'<div class="cmeta"><div class="cname">{esc(r["name"])}{newt}</div>'
                  f'<div class="csub">{esc(sub)}</div></div><span class="tchip {chip}">T{esc(t)}</span></button>')

    # ---- spotlight ----
    sp = pick_spotlight(rows, run_date)
    sp_html = ""
    if sp:
        fund = parse_funding(sp.get("what", ""), sp.get("notes", "")) or "—"
        what = sp.get("what", "")
        title = what.split(";")[0].split(".")[0][:60] if what else sp["name"]
        ev = sp.get("evidence_url", "")
        # suggested steps: digest actions mentioning this company, else generic
        _, ditems = digest_items(digest)
        steps = []
        if isinstance(ditems, list):
            steps = [it["action"] for it in ditems if it["action"] and sp["name"].split()[0].lower() in (it["head"] + it["signal"] + it["action"]).lower()][:3]
        if not steps:
            steps = [f"Harvest {sp['name']}'s /vs and /alternatives pages for the rival set it names",
                     f"Verify the funding and customer logos against primary sources",
                     f"Add {sp['name']} to the next digest if it stays on-trajectory"]
        steps_html = "".join(f'<li><span class="ar">→</span> {esc(s)}</li>' for s in steps)
        clu = sp.get("cluster", "")
        tchip = "pf" if sp["tier"] == "1" else "pa"
        ev_html = ""
        if ev.startswith("http"):
            dom = re.sub(r"^https?://(www\.)?", "", ev).split("/")[0]
            ev_html = (f'<div class="ev"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>'
                       f'<a href="{esc(ev)}" target="_blank" rel="noopener">{esc(dom)}</a> — primary source</div>')
        ev_html += (f'<div class="ev"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 0 20 15.3 15.3 0 0 1 0-20"/></svg>'
                    f'<a href="https://{esc(sp["domain"])}" target="_blank" rel="noopener">{esc(sp["domain"])}</a> — product site</div>')
        sp_html = f"""<div class="card">
        <div class="rb"><div class="pills"><span class="pill {tchip}">Tier {esc(sp["tier"])}</span><span class="pill ps">{esc(clu)}</span><span class="pill conf {confidence(sp)}">{esc(CONF_LABEL[confidence(sp)])}</span></div><span class="lab">tracked</span></div>
        <div class="stitle"><a href="https://{esc(sp["domain"])}" target="_blank" rel="noopener" style="color:inherit;text-decoration:none">{esc(sp["name"])}</a> — {esc(title)}</div>
        <div class="lab" style="margin-top:2px">{esc(sp["domain"])}</div>
        <div class="tiles">{_tile("Funding", parse_funding(sp.get("what",""), sp.get("notes","")))}{_tile("Stage", known(sp.get("stage")).replace("series-","Series ").title())}{_tile("HQ", known(sp.get("hq")).split(",")[0])}{_tile("Founded", sp.get("founded"))}</div>
        <p class="body">{esc(what)}</p>
        <div class="lab" style="margin:18px 0 2px">Suggested next steps</div>
        <ul class="steps">{steps_html}</ul>
        <div class="lab" style="margin:18px 0 6px">Evidence</div>{ev_html}</div>"""

    # ---- map (Frontier) ----
    named, faint, nfaint, xa, ya = map_data(rows, root, run_date)
    morechip = f'<div class="mapmore">+{nfaint} more racing in</div>' if nfaint else ""
    map_section = ""
    if named or faint:
        map_section = (
            '<div class="mapwrap"><div class="eyebrow">The competitive map</div>'
            '<h1 style="font-size:24px;margin:7px 0 4px">Everyone is racing to the same corner.</h1>'
            f'<p class="sub" style="font-size:14px">Scored, not hand-placed — {esc(xa["low"])}→{esc(xa["high"])} × {esc(ya["low"])}→{esc(ya["high"])}. '
            f'The {len(named)} nearest the corner are named; the rest are the field. Hover any dot.</p>'
            '<div class="map" id="pmap"><div class="qtr"></div><div class="qv"></div><div class="qh"></div>'
            '<div class="ql tr">convergence</div>'
            f'<div class="ql tl">{esc(ya["high"])} · narrow</div><div class="ql bl">narrow · {esc(ya["low"])}</div><div class="ql br">broad</div>'
            f'<div class="axx">{esc(xa["low"])}&nbsp;&nbsp;───→&nbsp;&nbsp;{esc(xa["high"])}</div>'
            f'<div class="axy">{esc(ya["low"])}&nbsp;───→&nbsp;{esc(ya["high"])}</div>{morechip}</div></div>')

    # ---- digest section ----
    ddate, ditems = digest_items(digest)
    if isinstance(ditems, str):
        dg_html = f'<div class="dgquiet">{esc(ditems)}</div>'
    elif ditems:
        dg_html = ""
        for it in ditems:
            dg_html += (f'<div class="dgc"><div class="dgh">{md_inline(esc_ks(it["head"]))}</div>'
                        + (f'<div class="dgr"><span>Signal</span><p>{md_inline(esc_ks(it["signal"]))}</p></div>' if it["signal"] else "")
                        + (f'<div class="dgr act"><span>Do</span><p>{md_inline(esc_ks(it["action"]))}</p></div>' if it["action"] else "") + "</div>")
    else:
        dg_html = '<div class="dgquiet">No digest yet — run a scan to generate your first decision brief.</div>'

    # ---- registry table ----
    def trow(r):
        chip = "t1" if r["tier"] == "1" else ("t2" if r["tier"] == "2" else "t3")
        ev = r.get("evidence_url", "")
        nt = ' <span class="pill pf" style="padding:1px 6px;font-size:9px">NEW</span>' if r["name"] in new_names else ""
        return (f'<tr data-domain="{esc(r["domain"])}" data-tier="{esc(r["tier"])}"{" data-new=1" if r["name"] in new_names else ""}>'
                f'<td><div class="cname">{esc(r["name"])}{nt}</div><a class="tdom" href="https://{esc(r["domain"])}" target="_blank" rel="noopener">{esc(r["domain"])}</a></td>'
                f'<td><span class="tchip {chip}">T{esc(r["tier"])}</span></td><td>{esc(r.get("cluster",""))}</td>'
                f'<td>{esc(known(r.get("stage")))}</td><td>{esc(known(r.get("hq")))}</td>'
                f'<td class="twhat">{esc(r.get("what",""))}'
                + (f' · <a href="{esc(ev)}" target="_blank" rel="noopener">evidence</a>' if ev.startswith("http") else "") + "</td></tr>")
    table_rows = "\n".join(trow(r) for r in sorted(rows, key=lambda r: (r["tier"], r["name"].lower())))

    headline = brand["tagline"]
    builtby = f' <b style="color:{accent}">Built by {esc(company)}.</b>' if company else ""
    logo = brand["logo"]
    if logo.startswith("http"):
        logo_svg = f'<img src="{esc(logo)}" alt="" style="width:19px;height:19px;border-radius:5px">'
    elif logo:
        logo_svg = f'<span style="font-size:18px">{esc(logo)}</span>'
    else:
        logo_svg = f'<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="{accent}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/></svg>'

    repo = brand["repo_url"]
    repo_foot = f' · <a href="{esc(repo)}" style="color:inherit" target="_blank" rel="noopener">repo</a>' if repo.startswith("http") else ""

    companies_json = json.dumps([{**r, "conf": confidence(r)} for r in rows], ensure_ascii=False)
    doc = TEMPLATE
    subs = {
        "ACCENT": accent, "ACC2": accent2, "ACCSOFT": _rgba(accent, .10), "ACCSOFT2": _rgba(accent, .07),
        "ACC1DOT": _rgba(accent, .10), "ACC2DOT": _rgba(accent2, .13),
        "EYEBROW": esc(f"{product} · competitive radar"), "LOGO": logo_svg,
        "HEADLINE": esc(headline), "BUILTBY": builtby, "RUNDATE": esc(run_date),
        "NET30": ("+" + str(net30)) if net30 else "0", "TRACKLINE": track_line, "NEWLINE": new_line,
        "XLABELS": xlabels, "NALL": str(len(rows)), "NT1": str(len(tiers["1"])),
        "NT2": str(len(tiers["2"])), "NNEW": str(len(new_rows)), "CROWS": crows,
        "COMPANYDATA": companies_json, "ACTIVITYNOTE": activity_note,
        "SPOTLIGHT": sp_html or '<div class="card"><p class="body">No companies yet — run a scan.</p></div>',
        "MAPSECTION": map_section,
        "MAPDATA": json.dumps(named, ensure_ascii=False), "FAINT": json.dumps(faint, ensure_ascii=False),
        "DDATE": esc(ddate or run_date), "DIGEST": dg_html, "TABLE": table_rows,
        "THREATS": "".join(f"<li>{t}</li>" for t in threat_top(landscape)) or "<li>No threat read yet.</li>",
        "REPOFOOT": repo_foot, "PRODUCT": esc(product),
    }
    for k, v in subs.items():
        doc = doc.replace("{{" + k + "}}", v)
    out.write_text(doc, encoding="utf-8")
    print(f"report.html: {len(rows)} rows, {len(new_rows)} new, spotlight={sp['name'] if sp else None!r} → {out}")


TEMPLATE = r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{PRODUCT}} — competitive radar — {{RUNDATE}}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,300;6..72,400;6..72,500&family=JetBrains+Mono:wght@400;500;600&family=Geist:wght@300;400;500;600&display=swap');
body{margin:0;background:#f4f1ea;padding:24px;}
.pb{--flame:{{ACCENT}};--ink:#20201c;--mut:#6f6a60;--line:#efe7dd;--card:#fff;
 background:radial-gradient(125% 70% at 50% -8%,{{ACCSOFT2}} 0%,#faf1ea 32%,#f8f7f4 100%);
 font-family:'Geist','Inter',-apple-system,sans-serif;color:var(--ink);border-radius:18px;padding:30px 32px 36px;max-width:1120px;margin:0 auto;}
.pb *{box-sizing:border-box;}
.brand{display:flex;align-items:center;gap:9px;}
.eyebrow{font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--flame);font-weight:500;}
.pb h1{font-family:'Newsreader',serif;font-weight:400;font-size:30px;line-height:1.14;letter-spacing:-.015em;margin:10px 0 9px;max-width:760px;}
.sub{color:#6f6a60;font-size:15px;max-width:680px;margin:0;}
.statline{display:flex;gap:20px;margin-top:16px;font-family:'JetBrains Mono',monospace;font-size:12px;color:#6f6a60;}
.statline b{color:var(--ink);font-size:15px;}
.grid{display:grid;grid-template-columns:0.86fr 1.14fr;gap:16px;margin-top:22px;}
.col{display:flex;flex-direction:column;gap:16px;min-width:0;}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px 20px;box-shadow:0 1px 2px rgba(40,28,12,.04),0 22px 46px -32px rgba(40,28,12,.24);min-width:0;}
.lab{font-family:'JetBrains Mono',monospace;font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--mut);font-weight:500;}
.rb{display:flex;align-items:center;justify-content:space-between;gap:8px;}
.net{font-family:'JetBrains Mono',monospace;font-weight:600;color:var(--flame);font-size:13px;text-align:right;}
.net small{display:block;color:var(--mut);font-weight:400;font-size:9.5px;letter-spacing:.1em;}
.legend{display:flex;gap:14px;margin:10px 0 2px;}.legend span{font-size:11px;color:#6f6a60;display:inline-flex;align-items:center;gap:5px;}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;}
.xaxis{display:flex;justify-content:space-between;font-family:'JetBrains Mono',monospace;font-size:9.5px;color:#b3ada3;margin-top:3px;padding:0 2px;}
.pills{display:flex;gap:7px;flex-wrap:wrap;}
.pill{display:inline-flex;align-items:center;gap:5px;border-radius:999px;padding:4px 11px;font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:.05em;text-transform:uppercase;font-weight:500;border:1px solid transparent;}
.pf{background:{{ACCSOFT}};color:{{ACCENT}};border-color:{{ACCSOFT}};}.pa{background:#fdf1da;color:#8a6a1e;border-color:#f4e2bf;}.ps{background:#eef0f2;color:#586170;border-color:#e2e5e9;}.pn{background:#f4f1ec;color:#6f6a60;border-color:#e8e3da;}
.pill.conf{font-size:9px;padding:3px 8px;}.conf.verified{background:#e8f5ec;color:#2c7a4b;}.conf.partial{background:#fdf4e3;color:#9a6a1e;}.conf.thin{background:#f4f1ec;color:#8a8478;}
.companylist{max-height:496px;overflow:auto;margin:0 -4px;padding:0 4px;}
.crow{width:100%;display:flex;align-items:center;gap:11px;padding:9px 5px;border:0;border-top:1px solid #f4efe7;background:transparent;color:inherit;text-align:left;font:inherit;cursor:pointer;border-radius:9px;}.crow:first-child{border-top:0;}.crow:hover,.crow.active{background:#fcf8f3;}.crow.active{box-shadow:inset 3px 0 0 var(--flame);}
.mav{width:26px;height:26px;border-radius:8px;flex:none;display:flex;align-items:center;justify-content:center;font-weight:600;font-size:12px;}
.av1{background:{{ACCSOFT}};color:{{ACCENT}};}.av2{background:#fdf1da;color:#8a6a1e;}
.cmeta{flex:1;min-width:0;}.cname{font-weight:500;font-size:13.5px;}.csub{font-size:11.5px;color:var(--mut);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.tchip{font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:600;padding:2px 7px;border-radius:6px;flex:none;}
.t1{background:{{ACCSOFT}};color:{{ACCENT}};}.t2{background:#fdf1da;color:#8a6a1e;}.t3{background:#eef0f2;color:#586170;}
.stitle{font-family:'Newsreader',serif;font-weight:400;font-size:22px;margin:13px 0 2px;letter-spacing:-.01em;}
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:9px;margin:14px 0;}
.tile{border:1px solid var(--line);border-radius:11px;padding:9px 11px;background:#fffdfb;}.tile .tv{font-size:15px;font-weight:500;margin-top:3px;}.tile.dim{background:#fbf9f6;}.tile.dim .tv{color:#c3bcb0;font-weight:400;}
.body{font-size:13.5px;color:#56524a;line-height:1.55;}
.steps{list-style:none;margin:6px 0 0;padding:0;}.steps li{display:flex;gap:9px;padding:6px 0;font-size:13.5px;}.ar{color:var(--flame);font-weight:600;}
.ev{display:flex;align-items:center;gap:9px;padding:9px 0;border-top:1px solid #f4efe7;font-size:12.5px;color:#56524a;}.ev svg{color:var(--flame);flex:none;}.ev a{color:var(--ink);text-decoration:none;font-weight:500;}
.mapwrap{margin-top:30px;}
.map{position:relative;height:500px;margin-top:14px;border:1px solid var(--line);border-radius:16px;overflow:hidden;background:linear-gradient(180deg,#fff,#fdfbf8);box-shadow:0 1px 2px rgba(40,28,12,.04),0 22px 46px -32px rgba(40,28,12,.24);}
.qv{position:absolute;left:50%;top:6%;bottom:6%;width:1px;background:#ece6dc;}.qh{position:absolute;top:50%;left:5%;right:5%;height:1px;background:#ece6dc;}
.qtr{position:absolute;left:50%;top:0;width:50%;height:50%;background:linear-gradient(225deg,{{ACCSOFT}},rgba(255,255,255,0));}
.ql{position:absolute;font-family:'JetBrains Mono',monospace;font-size:9.5px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#6a5d50;z-index:1;}
.ql.tr{right:16px;top:14px;color:{{ACCENT}};}.ql.tl{left:118px;top:14px;}.ql.bl{left:118px;bottom:32px;}.ql.br{right:16px;bottom:32px;}
.axx{position:absolute;left:90px;right:20px;bottom:11px;text-align:center;font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#696157;}
.axy{position:absolute;left:8px;top:50%;transform:translateY(-50%) rotate(-90deg);font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#696157;white-space:nowrap;}
.fd{position:absolute;width:6px;height:6px;border-radius:50%;transform:translate(-50%,-50%);opacity:.34;pointer-events:none;}.fd1{background:{{ACCENT}};}.fd2{background:{{ACC2}};}
.mapmore{position:absolute;left:16px;bottom:13px;font-family:'JetBrains Mono',monospace;font-size:9.5px;letter-spacing:.08em;text-transform:uppercase;color:#8a8478;}
.bub{position:absolute;transform:translate(0,-50%);display:flex;align-items:center;gap:6px;padding:3px 10px 3px 4px;border-radius:999px;background:rgba(255,255,255,.92);border:1px solid transparent;cursor:pointer;color:inherit;text-decoration:none;transition:box-shadow .12s,background .12s;}
.bub:focus-visible{outline:2px solid {{ACCENT}};outline-offset:2px;}
.bub:hover{background:#fff;border-color:var(--line);box-shadow:0 8px 22px -10px rgba(40,28,12,.34);z-index:20;}
.bd{width:11px;height:11px;border-radius:50%;flex:none;}.bd1{background:{{ACCENT}};box-shadow:0 0 0 3.5px {{ACC1DOT}};}.bd2{background:{{ACC2}};box-shadow:0 0 0 3.5px {{ACC2DOT}};}
.bl{font-size:11.5px;font-weight:500;white-space:nowrap;}
.tip{display:none;position:absolute;left:50%;top:160%;transform:translateX(-50%);width:184px;background:#fff;border:1px solid var(--line);border-radius:12px;padding:11px 13px;box-shadow:0 16px 36px -14px rgba(40,28,12,.42);z-index:30;text-align:left;}
.bub.up .tip{top:auto;bottom:160%;}.bub:hover .tip{display:block;}
.tip .tn{font-weight:500;font-size:13px;display:flex;align-items:center;gap:6px;}.tip .tm{font-family:'JetBrains Mono',monospace;font-size:9.5px;color:var(--mut);margin:3px 0 6px;}.tip .tw{font-size:12px;color:#56524a;line-height:1.45;}
.sec{margin-top:30px;}.sechead{font-family:'Newsreader',serif;font-size:22px;margin:0 0 4px;}
.dgc{background:#fff;border:1px solid var(--line);border-left:3px solid var(--flame);border-radius:14px;padding:15px 18px;margin-top:11px;box-shadow:0 1px 2px rgba(40,28,12,.04),0 18px 40px -34px rgba(40,28,12,.22);}
.dgh{font-family:'Newsreader',serif;font-size:18px;line-height:1.3;margin-bottom:8px;}
.dgr{display:flex;gap:10px;font-size:13.5px;padding:3px 0;color:#56524a;}.dgr>span{flex:none;width:48px;font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:#b3ada3;padding-top:3px;}.dgr p{margin:0;}.dgr.act{border-top:1px solid #f4efe7;margin-top:5px;padding-top:8px;}.dgr.act>span{color:var(--flame);}.dgr.act p{font-weight:500;color:var(--ink);}
.dgquiet{color:#6f6a60;background:#fff;border:1px dashed var(--line);border-radius:14px;padding:16px 18px;margin-top:11px;}
.threats{padding-left:20px;color:#56524a;font-size:14px;}.threats li{margin-bottom:7px;}
.controls{display:flex;gap:8px;margin:10px 0 12px;flex-wrap:wrap;}
.controls input{flex:1;min-width:200px;background:#fff;border:1px solid var(--line);border-radius:9px;padding:8px 12px;font-size:14px;color:var(--ink);}
.fb{background:#fff;border:1px solid var(--line);border-radius:9px;color:#6f6a60;padding:7px 13px;cursor:pointer;font-size:13px;}.fb.on{color:var(--flame);border-color:var(--flame);}
.tablebox{max-height:560px;overflow:auto;border:1px solid var(--line);border-radius:13px;background:var(--card);box-shadow:0 1px 2px rgba(40,28,12,.04),0 18px 40px -34px rgba(40,28,12,.2);}
table{width:100%;border-collapse:collapse;}th{text-align:left;font-family:'JetBrains Mono',monospace;font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);padding:9px 12px;border-bottom:1px solid var(--line);white-space:nowrap;}
#reg thead th{position:sticky;top:0;background:var(--card);z-index:2;}#reg tr:last-child td{border-bottom:0;}
td{padding:10px 9px;border-bottom:1px solid #f4efe7;vertical-align:top;font-size:13px;color:#56524a;}td .cname{color:var(--ink);}
#reg tbody tr{cursor:pointer;}#reg tbody tr:hover{background:#fcf8f3;}
a.tdom{color:var(--flame);font-size:11.5px;text-decoration:none;}.twhat{max-width:430px;}.twhat a{color:var(--flame);}
.foot{margin-top:28px;font-family:'JetBrains Mono',monospace;font-size:10.5px;letter-spacing:.06em;color:#b3ada3;text-transform:uppercase;}.foot b{color:var(--flame);font-weight:500;}
</style></head><body><div class="pb">
<div class="brand">{{LOGO}}<span class="eyebrow">{{EYEBROW}}</span></div>
<h1>{{HEADLINE}}</h1>
<p class="sub">Swept twice a week — every entrant tiered, sourced to a live link, and told straight.{{BUILTBY}}</p>
<div class="statline"><span><b>{{NALL}}</b> tracked</span><span><b style="color:{{ACCENT}}">{{NNEW}}</b> new this scan</span><span><b style="color:{{ACCENT}}">{{NT1}}</b> Tier&nbsp;1</span><span><b>{{NT2}}</b> Tier&nbsp;2</span><span>scan {{RUNDATE}}</span></div>

<div class="grid">
  <div class="col">
    <div class="card">
      <div class="rb"><span class="lab">Radar activity</span><span class="net">{{NET30}}<small>net · new</small></span></div>
      <div class="legend"><span><i class="dot" style="background:#3b82c4"></i>Tracked</span><span><i class="dot" style="background:#1d9e75"></i>New</span></div>
      <svg viewBox="0 0 320 118" width="100%" height="118" preserveAspectRatio="none" aria-hidden="true">
        <line x1="8" y1="104" x2="312" y2="104" stroke="#ece6dc" stroke-width="1" stroke-dasharray="3 4"/><line x1="8" y1="58" x2="312" y2="58" stroke="#f1ece3" stroke-width="1" stroke-dasharray="3 4"/>
        <polyline fill="none" stroke="#3b82c4" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round" points="{{TRACKLINE}}"/>
        <polyline fill="none" stroke="#1d9e75" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round" points="{{NEWLINE}}"/>
      </svg>
      <div class="xaxis">{{XLABELS}}</div>{{ACTIVITYNOTE}}
    </div>
    <div class="card">
      <div class="rb" style="margin-bottom:10px"><span class="lab">Companies · {{NALL}}</span><span class="lab" style="font-size:9px">click to inspect →</span></div>
      <div class="companylist">{{CROWS}}</div>
    </div>
  </div>
  <div class="col" id="spotlight">{{SPOTLIGHT}}</div>
</div>

{{MAPSECTION}}

<div class="sec"><div class="eyebrow" style="color:{{ACCENT}}">What changed &amp; what to do · {{DDATE}}</div>{{DIGEST}}</div>

<div class="sec"><div class="eyebrow">Top threats right now</div><ol class="threats">{{THREATS}}</ol></div>

<div class="sec"><div class="eyebrow">Full registry · {{NALL}}</div>
<div class="controls"><input id="q" placeholder="Search name, domain, description…"><button class="fb on" data-t="all">All</button><button class="fb" data-t="1">T1</button><button class="fb" data-t="2">T2</button><button class="fb" data-t="3">T3</button><button class="fb" data-t="new">New</button></div>
<div class="cap" style="margin:-2px 0 9px">The complete index — search a name or filter by tier; the full list scrolls inside.</div>
<div class="tablebox"><table id="reg"><thead><tr><th>Company</th><th>Tier</th><th>Cluster</th><th>Stage</th><th>HQ</th><th>What / why it matters</th></tr></thead><tbody>{{TABLE}}</tbody></table></div></div>

<div class="foot">{{PRODUCT}} · {{NALL}} tracked · positions from axis scores in the registry · <b>built by Astell</b>{{REPOFOOT}}</div>
</div>
<script>
(function(){
 var named={{MAPDATA}},faint={{FAINT}},companies={{COMPANYDATA}},map=document.getElementById('pmap');
 function jesc(s){return String(s||'').replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
 function jknown(s){s=String(s||'').trim();return (!s||s.toLowerCase()==='unknown')?'':s;}
 function jfund(c){var t=(c.what||'')+' '+(c.notes||''),m=t.match(/\$\s?(\d[\d.]*)\s?([MB])\b/i);return m?'$'+m[1]+m[2].toUpperCase():'';}
 function jtile(label,val){var v=jknown(val);return '<div class="tile'+(v?'':' dim')+'"><div class="lab">'+label+'</div><div class="tv">'+(v?jesc(v):'—')+'</div></div>';}
 var JCONF={verified:'verified',partial:'partial source',thin:'thin source'};
 function showCompany(domain){
  var c=companies.find(function(x){return x.domain===domain;});if(!c)return;
  document.querySelectorAll('.crow').forEach(function(x){x.classList.toggle('active',x.getAttribute('data-domain')===domain);});
  var host=document.getElementById('spotlight'),ev=c.evidence_url||'',evdom=ev.replace(/^https?:\/\/(www\.)?/,'').split('/')[0],site='https://'+c.domain;
  var stage=jknown(c.stage).replace(/^series-/,'Series '),tier=c.tier||'',tchip=tier==='1'?'pf':(tier==='2'?'pa':'ps'),cf=c.conf||'thin';
  host.innerHTML='<div class="card"><div class="rb"><div class="pills"><span class="pill '+tchip+'">Tier '+jesc(tier)+'</span><span class="pill ps">'+jesc(c.cluster||'')+'</span><span class="pill conf '+cf+'">'+JCONF[cf]+'</span></div><span class="lab">tracked</span></div>'
   +'<div class="stitle"><a href="'+jesc(site)+'" target="_blank" rel="noopener" style="color:inherit;text-decoration:none">'+jesc(c.name)+'</a> — '+jesc((c.what||c.name).split(/[.;]/)[0].slice(0,80))+'</div>'
   +'<div class="lab" style="margin-top:2px">'+jesc(c.domain)+'</div>'
   +'<div class="tiles">'+jtile('Funding',jfund(c))+jtile('Stage',stage)+jtile('HQ',jknown(c.hq).split(',')[0])+jtile('Founded',c.founded)+'</div>'
   +'<p class="body">'+jesc(c.what||'')+'</p>'+(c.why_tier?'<div class="lab" style="margin:18px 0 2px">Why tier</div><p class="body">'+jesc(c.why_tier)+'</p>':'')
   +'<div class="lab" style="margin:18px 0 6px">Evidence</div>'
   +(ev.indexOf('http')===0?'<div class="ev"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg><a href="'+jesc(ev)+'" target="_blank" rel="noopener">'+jesc(evdom)+'</a> — primary source</div>':'')
   +'<div class="ev"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 0 20 15.3 15.3 0 0 1 0-20"/></svg><a href="'+jesc(site)+'" target="_blank" rel="noopener">'+jesc(c.domain)+'</a> — product site</div></div>';
 }
 function PX(d,W){return (50+(d.x-50)*0.62)/100*W;} function PY(d,H){return (50-(d.y-50)*0.64)/100*H;}
 function build(){if(!map)return;var W=map.clientWidth,H=map.clientHeight;if(!W)return setTimeout(build,60);
  faint.forEach(function(d){var el=document.createElement('span');el.className='fd fd'+d.t;el.style.left=PX(d,W)+'px';el.style.top=PY(d,H)+'px';map.appendChild(el);});
  var ns=named.map(function(d){return {d:d,x:PX(d,W),y:PY(d,H)};});
  ns.forEach(function(n){var b=document.createElement('a');b.className='bub';b.href='https://'+n.d.d;b.target='_blank';b.rel='noopener';b.setAttribute('aria-label',n.d.n+' — Tier '+n.d.t);
   b.innerHTML='<span class="bd bd'+n.d.t+'"></span><span class="bl">'+n.d.n+'</span><div class="tip"><div class="tn">'+n.d.n+' <span class="tchip t'+n.d.t+'">T'+n.d.t+'</span></div><div class="tm">'+n.d.m+'</div><div class="tw">'+n.d.w+'</div></div>';
   map.appendChild(b);n.el=b;n.w=b.offsetWidth;n.h=b.offsetHeight;});
  for(var it=0;it<120;it++){for(var i=0;i<ns.length;i++)for(var j=i+1;j<ns.length;j++){
    var a=ns[i],c=ns[j],acx=a.x+a.w/2,ccx=c.x+c.w/2,dx=ccx-acx,dy=c.y-a.y;
    var ox=(a.w/2+c.w/2+8)-Math.abs(dx),oy=(a.h/2+c.h/2+8)-Math.abs(dy);
    if(ox>0&&oy>0){if(oy<=ox){var s=oy/2*(dy<0?-1:1)||oy/2;a.y-=s;c.y+=s;}else{var s2=ox/2*(dx<0?-1:1)||ox/2;a.x-=s2;c.x+=s2;}}}}
  ns.forEach(function(n){n.x=Math.max(10,Math.min(W-n.w-10,n.x));n.y=Math.max(n.h/2+10,Math.min(H-n.h/2-34,n.y));n.el.style.left=n.x+'px';n.el.style.top=n.y+'px';if(n.y>H*0.55)n.el.classList.add('up');});}
 build();
 var q=document.getElementById('q'),rows=[].slice.call(document.querySelectorAll('#reg tbody tr')),mode='all';
 function ap(){var t=(q.value||'').toLowerCase();rows.forEach(function(r){var okM=mode==='all'||(mode==='new'?r.hasAttribute('data-new'):r.getAttribute('data-tier')===mode);var okT=!t||r.textContent.toLowerCase().indexOf(t)!==-1;r.style.display=(okM&&okT)?'':'none';});}
 q.addEventListener('input',ap);document.querySelectorAll('.fb').forEach(function(b){b.addEventListener('click',function(){document.querySelectorAll('.fb').forEach(function(x){x.classList.remove('on');});b.classList.add('on');mode=b.getAttribute('data-t');ap();});});
 document.querySelectorAll('.crow').forEach(function(b){b.addEventListener('click',function(){showCompany(b.getAttribute('data-domain'));});});
 rows.forEach(function(r){r.addEventListener('click',function(e){if(e.target.closest('a'))return;showCompany(r.getAttribute('data-domain'));document.getElementById('spotlight').scrollIntoView({behavior:'smooth',block:'start'});});});
})();
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    root = Path(a.root)
    render(root, Path(a.out) if a.out else root / "data/report.html")


if __name__ == "__main__":
    main()
