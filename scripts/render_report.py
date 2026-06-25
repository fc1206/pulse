#!/usr/bin/env python3
"""Render data/report.html — the branded, deterministic deliverable.

Leads with the DIGEST (what changed -> what to do), then the competitive map,
new entrants, threat read, and the full registry. Brand + theme come from
config/brand.json (env RADAR_TITLE/RADAR_REPO still honored for back-compat).
Stdlib-only; the model never writes this file.

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

import score_axes  # sibling in scripts/; computes the map coordinates

DEFAULT_BRAND = {
    "product": os.environ.get("RADAR_TITLE", "Pulse"),
    "company": "",
    "tagline": "Your competitive landscape, watched — what changed and what to do about it.",
    "accent": "#fc4b32",
    "accent_2": "#2f6df0",
    "logo": "",
    "theme": "light",
    "repo_url": os.environ.get("RADAR_REPO", "").strip(),
}

THEMES = {
    "light": {"bg": "#f6f4ef", "panel": "#ffffff", "panel2": "#fbfaf7", "ink": "#20201c",
              "mut": "#6f6a60", "faint": "#b3ada3", "line": "#ece6dc", "crowd": "#d9cfc2",
              "shadow": "0 1px 2px rgba(40,28,12,.04), 0 22px 46px -32px rgba(40,28,12,.22)"},
    "dark": {"bg": "#0d1117", "panel": "#161b22", "panel2": "#11161d", "ink": "#e6edf3",
             "mut": "#9aa3ad", "faint": "#6b7280", "line": "#21262d", "crowd": "#39414d",
             "shadow": "0 1px 2px rgba(0,0,0,.3), 0 18px 40px -22px rgba(0,0,0,.6)"},
}


def esc(s):
    return html.escape(str(s or ""), quote=True)


def esc_keep_strong(s):
    return html.escape(s, quote=False)


def md_inline(s):
    s = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(https?://[^\s<)\]]+)", r'<a href="\1" target="_blank" rel="noopener">link</a>', s)
    return s


def load(root):
    with (root / "data/registry.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    state = json.loads((root / "data/state.json").read_text(encoding="utf-8"))
    scanlog = (root / "data/SCANLOG.md").read_text(encoding="utf-8")
    landscape = (root / "data/LANDSCAPE.md").read_text(encoding="utf-8")
    dp = root / "data/DIGEST.md"
    digest = dp.read_text(encoding="utf-8") if dp.exists() else ""
    bp = root / "config/brand.json"
    brand = dict(DEFAULT_BRAND)
    if bp.exists():
        try:
            brand.update({k: v for k, v in json.loads(bp.read_text(encoding="utf-8")).items()
                          if not k.startswith("_") and v not in (None, "")})
        except Exception:
            pass
    return rows, state, scanlog, landscape, digest, brand


def digest_items(digest):
    """Parse the latest digest entry into [{head, signal, why, action}] or a sentinel string."""
    m = re.search(r"^## (\d{4}-\d{2}-\d{2}) — digest.*?(?=^## \d{4}|\Z)", digest, re.M | re.S)
    if not m:
        return None, []
    block = m.group(0)
    date_m = re.match(r"^## (\d{4}-\d{2}-\d{2})", block)
    ddate = date_m.group(1) if date_m else ""
    if "NO ACTIONABLE SIGNAL" in block:
        return ddate, "NO ACTIONABLE SIGNAL — this run's findings didn't clear the action bar. A quiet week is signal too."
    items = []
    for chunk in re.split(r"^### ", block, flags=re.M)[1:]:
        head = chunk.splitlines()[0].strip()
        head = re.sub(r"^\d+\.\s*", "", head)
        def field(name):
            fm = re.search(rf"\*\*{name}:\*\*\s*(.*?)(?=\n\*\*|\Z)", chunk, re.S)
            return fm.group(1).strip().replace("\n", " ") if fm else ""
        items.append({"head": head, "signal": field("Signal"),
                      "why": field("Why it matters"), "action": field("Action")})
    return ddate, items


def threat_top5(landscape):
    m = re.search(r"## Threat assessment.*?\n(.*?)\n## ", landscape, re.S)
    if not m:
        return []
    return [md_inline(esc_keep_strong(i)) for i in re.findall(r"^\d+\.\s+(.*)$", m.group(1), re.M)[:5]]


def latest_scan_notes(scanlog):
    parts = re.split(r"^## ", scanlog, flags=re.M)
    return ("## " + parts[-1]).strip() if len(parts) > 1 else ""


def competitive_map(rows, root, P, accent, accent2):
    """Theme-aware breadth x action map; dots fixed at computed coords, T1 leader-line labels."""
    try:
        cfg = score_axes.load_config(root, None)
        on = [r for r in rows if r.get("status") == "active" and r.get("tier") in ("1", "2")]
        data = []
        for r in on:
            b, a = score_axes.score_row(r, cfg)
            meta = " · ".join(p for p in [r.get("stage", ""), r.get("hq", ""),
                              (("est. " + r["founded"]) if r.get("founded") not in ("", "unknown") else "")]
                              if p and p != "unknown")
            data.append({"n": esc(r["name"]), "x": b, "y": a, "t": int(r["tier"]),
                         "labeled": r["tier"] == "1", "m": esc(meta), "w": esc((r.get("what", "") or "")[:150])})
        if not data:
            return ""
        data.sort(key=lambda c: c["labeled"])
        xa, ya = cfg["x_axis"], cfg["y_axis"]
    except Exception as e:
        return f"<!-- map skipped: {esc(str(e))} -->"
    tmpl = r"""<section class="sec"><div class="sh">The competitive map</div>
<div class="map" id="cmap"><div class="cmq cmv"></div><div class="cmq cmh"></div>
<div class="cmax cmx">__XLO__&nbsp;───→&nbsp;__XHI__</div><div class="cmax cmy">__YLO__&nbsp;───→&nbsp;__YHI__</div>
<svg class="cmlead" id="cmlead"></svg></div>
<div class="cap">__N__ active Tier-1/2 plotted by <b>computed</b> __XL__ × __YL__ — positions from the registry, never hand-placed. Tier-1 labelled; hover any dot.</div>
<script>(function(){
var DATA=__DATA__,m=document.getElementById('cmap'),svg=document.getElementById('cmlead');
function build(){var W=m.clientWidth,H=m.clientHeight;if(!W)return setTimeout(build,60);var PADX=86,PADY=40;
 var ns=DATA.map(function(d){return {d:d,px:PADX+d.x/100*(W-PADX-20),py:H-PADY-d.y/100*(H-2*PADY)};});
 ns.forEach(function(n){var dot=document.createElement('div');dot.className='cmdot t'+n.d.t;
  dot.style.left=n.px+'px';dot.style.top=n.py+'px';
  dot.innerHTML='<div class="cmtip"><div class="cmtn">'+n.d.n+' <span class="cmtc t'+n.d.t+'">T'+n.d.t+'</span></div><div class="cmtm">'+n.d.m+'</div><div class="cmtw">'+n.d.w+'</div></div>';
  m.appendChild(dot);n.dot=dot;});
 var L=ns.filter(function(n){return n.d.labeled;});
 L.forEach(function(n){var el=document.createElement('div');el.className='cmlbl';el.textContent=n.d.n;m.appendChild(el);n.el=el;n.w=el.offsetWidth;n.h=el.offsetHeight;});
 var GUT=L.filter(function(n){return n.d.x>=78;});
 GUT.forEach(function(g){g.dir=1;g.lx=W-12-g.w/2;g.ly=g.py;});
 var NEAR=L.filter(function(n){return n.d.x<78;});
 NEAR.forEach(function(n){n.dir=n.px<W*0.5?-1:1;n.lx=n.px+n.dir*(n.w/2+14);n.ly=n.py;});
 [GUT,NEAR].forEach(function(G){for(var it=0;it<240;it++){
   for(var i=0;i<G.length;i++)for(var j=i+1;j<G.length;j++){
     var a=G[i],b=G[j],dy=b.ly-a.ly,oy=(a.h/2+b.h/2+7)-Math.abs(dy);
     if(oy>0&&Math.abs(b.lx-a.lx)<(a.w/2+b.w/2+12)){var s=oy/2*(dy<0?-1:1)||oy/2;a.ly-=s;b.ly+=s;}}
   G.forEach(function(n){n.ly=Math.max(n.h/2+6,Math.min(H-n.h/2-26,n.ly));});}});
 var SN='http://www.w3.org/2000/svg';
 L.forEach(function(n){n.el.style.left=n.lx+'px';n.el.style.top=n.ly+'px';
  var ex=n.lx-n.dir*(n.w/2+2),ln=document.createElementNS(SN,'line');
  ln.setAttribute('x1',n.px);ln.setAttribute('y1',n.py);ln.setAttribute('x2',ex);ln.setAttribute('y2',n.ly);
  ln.setAttribute('stroke',n.d.t===1?'__ACC1L__':'__ACC2L__');ln.setAttribute('stroke-width','1');svg.appendChild(ln);
  n.el.addEventListener('mouseenter',function(){var t=n.dot.querySelector('.cmtip');if(t)t.style.display='block';});
  n.el.addEventListener('mouseleave',function(){var t=n.dot.querySelector('.cmtip');if(t)t.style.display='none';});});}
build();})();</script></section>"""
    return (tmpl.replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__XL__", esc(xa["label"])).replace("__YL__", esc(ya["label"]))
            .replace("__XLO__", esc(xa["low"])).replace("__XHI__", esc(xa["high"]))
            .replace("__YLO__", esc(ya["low"])).replace("__YHI__", esc(ya["high"]))
            .replace("__ACC1L__", accent).replace("__ACC2L__", accent2)
            .replace("__N__", str(len(data))))


def render(root, out):
    rows, state, scanlog, landscape, digest, brand = load(root)
    theme = brand["theme"] if brand["theme"] in THEMES else "light"
    P = THEMES[theme]
    accent, accent2 = brand["accent"], brand["accent_2"]
    title = (f'{brand["company"]} Radar' if brand["company"] else brand["product"])
    run_date = state.get("last_run", date.today().isoformat())
    runner = state.get("last_runner", "?")
    tiers = {t: [r for r in rows if r["tier"] == t] for t in ("1", "2", "3")}
    new_rows = [r for r in rows if r.get("first_seen") == run_date]
    if rows and len(new_rows) >= len(rows):
        m = re.search(r"^### .*? — scan.*?\nAdded: (.*?)$", landscape, re.M | re.S)
        names = {n.strip() for n in re.findall(r"([^;]+?) \(T\d", m.group(1))} if m else set()
        new_rows = [r for r in rows if r["name"] in names]
    new_domains = {r["domain"] for r in new_rows}

    # ---- digest (the hero) ----
    ddate, items = digest_items(digest)
    if isinstance(items, str):
        digest_html = f'<div class="quiet">{esc(items)}</div>'
    elif items:
        cards = ""
        for it in items:
            cards += (
                f'<div class="dg"><div class="dgh">{md_inline(esc_keep_strong(it["head"]))}</div>'
                + (f'<div class="dgr"><span class="dgk">Signal</span><span>{md_inline(esc_keep_strong(it["signal"]))}</span></div>' if it["signal"] else "")
                + (f'<div class="dgr"><span class="dgk">Why</span><span>{md_inline(esc_keep_strong(it["why"]))}</span></div>' if it["why"] else "")
                + (f'<div class="dgr act"><span class="dgk">Do</span><span>{md_inline(esc_keep_strong(it["action"]))}</span></div>' if it["action"] else "")
                + "</div>")
        digest_html = cards
    else:
        digest_html = '<div class="quiet">No digest yet — run a scan to generate your first decision brief.</div>'

    map_html = competitive_map(rows, root, P, accent, accent2)

    new_cards = "".join(
        f'<div class="card"><div class="nm">{esc(r["name"])} <span class="pill t{esc(r["tier"])}">T{esc(r["tier"])}</span></div>'
        f'<div class="cl">{esc(r["cluster"])} · {esc(r["stage"])} · {esc(r["hq"])}</div>'
        f'<div class="wt">{esc(r["what"])}</div></div>'
        for r in new_rows
    ) or '<div class="quiet">No net-new competitors this run — a verified zero, not an unchecked one.</div>'

    threats = threat_top5(landscape)
    threat_html = "".join(f"<li>{t}</li>" for t in threats) or '<li class="quiet">No threat read yet.</li>'

    def row_html(r):
        sb = ""
        is_new = ' data-new="1"' if r["domain"] in new_domains else ""
        newtag = '<span class="pill new">NEW</span>' if is_new else ""
        ev = esc(r.get("evidence_url", ""))
        return (
            f'<tr data-tier="{esc(r["tier"])}"{is_new}>'
            f'<td><div class="nm">{esc(r["name"])} {newtag}</div>'
            f'<a class="dom" href="https://{esc(r["domain"])}" target="_blank" rel="noopener">{esc(r["domain"])}</a></td>'
            f'<td><span class="pill t{esc(r["tier"])}">T{esc(r["tier"])}</span></td>'
            f'<td>{esc(r.get("cluster",""))}</td><td>{esc(r.get("stage",""))}</td><td>{esc(r.get("hq",""))}</td>'
            f'<td class="dt">{esc(r.get("first_seen",""))}</td>'
            f'<td class="what">{esc(r.get("what",""))}'
            f'<div class="why">{esc(r.get("why_tier",""))}'
            + (f' · <a href="{ev}" target="_blank" rel="noopener">evidence</a>' if ev.startswith("http") else "")
            + (f'<div class="note">⚠ {esc(r["notes"])}</div>' if r.get("notes") else "")
            + "</div></td></tr>")
    body_rows = "\n".join(row_html(r) for r in sorted(rows, key=lambda r: (r["tier"], r["name"].lower())))
    logo = brand["logo"]
    logo_html = (f'<img src="{esc(logo)}" alt="" class="logo">' if logo.startswith("http")
                 else (f'<span class="logo emoji">{esc(logo)}</span>' if logo else
                       f'<span class="logo dot" style="background:{accent}"></span>'))
    repo = brand["repo_url"]
    repo_link = f' · <a href="{esc(repo)}" target="_blank" rel="noopener">repo</a>' if repo.startswith("http") else ""

    doc = TEMPLATE
    for k, v in {
        "TITLE": esc(title), "TAGLINE": esc(brand["tagline"]), "RUNDATE": esc(run_date),
        "RUNNER": esc(runner), "LOGO": logo_html, "DDATE": esc(ddate or run_date),
        "N_ALL": str(len(rows)), "N_T1": str(len(tiers["1"])), "N_T2": str(len(tiers["2"])),
        "N_T3": str(len(tiers["3"])), "N_NEW": str(len(new_rows)),
        "DIGEST": digest_html, "MAP": map_html, "NEWCARDS": new_cards, "THREATS": threat_html,
        "ROWS": body_rows, "NOTES": esc(latest_scan_notes(scanlog)).replace("\n", "<br>"),
        "REPOLINK": repo_link,
        "BG": P["bg"], "PANEL": P["panel"], "PANEL2": P["panel2"], "INK": P["ink"], "MUT": P["mut"],
        "FAINT": P["faint"], "LINE": P["line"], "CROWD": P["crowd"], "SHADOW": P["shadow"],
        "ACCENT": accent, "ACCENT2": accent2,
        "ACC1L": _rgba(accent, .42), "ACC2L": _rgba(accent2, .42),
        "ACCSOFT": _rgba(accent, .10), "ACC2SOFT": _rgba(accent2, .12),
    }.items():
        doc = doc.replace("{{" + k + "}}", v)
    out.write_text(doc, encoding="utf-8")
    print(f"report.html: {len(rows)} rows, {len(new_rows)} new, theme={theme}, brand={title!r} → {out}")


def _rgba(hexc, a):
    h = hexc.lstrip("#")
    if len(h) != 6:
        return hexc
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{a})"


TEMPLATE = r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{TITLE}} — {{RUNDATE}}</title>
<style>
*{box-sizing:border-box;} html{-webkit-font-smoothing:antialiased;}
body{margin:0;background:{{BG}};color:{{INK}};font:15px/1.55 ui-sans-serif,system-ui,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;}
.wrap{max-width:1080px;margin:0 auto;padding:34px 22px 90px;}
a{color:{{ACCENT}};} .quiet{color:{{MUT}};}
.brandrow{display:flex;align-items:center;gap:11px;}
.logo{width:26px;height:26px;border-radius:8px;display:inline-flex;align-items:center;justify-content:center;font-size:16px;}
.logo.dot{width:14px;height:14px;border-radius:50%;}
h1{font-size:26px;font-weight:680;letter-spacing:-.01em;margin:0;}
.tagline{color:{{MUT}};margin:8px 0 0;font-size:15px;max-width:680px;}
.meta{color:{{FAINT}};font-size:12.5px;margin-top:7px;letter-spacing:.02em;}
.stats{display:flex;gap:10px;flex-wrap:wrap;margin:20px 0 6px;}
.stat{background:{{PANEL}};border:1px solid {{LINE}};border-radius:12px;padding:11px 16px;min-width:96px;box-shadow:{{SHADOW}};}
.stat b{display:block;font-size:22px;font-weight:680;} .stat span{color:{{MUT}};font-size:11.5px;}
.sec{margin-top:34px;}
.sh{font-size:12.5px;text-transform:uppercase;letter-spacing:.13em;color:{{MUT}};font-weight:600;margin-bottom:13px;}
.hero-sh{color:{{ACCENT}};}
.dg{background:{{PANEL}};border:1px solid {{LINE}};border-left:3px solid {{ACCENT}};border-radius:13px;padding:16px 18px;margin-bottom:11px;box-shadow:{{SHADOW}};}
.dgh{font-size:16.5px;font-weight:640;letter-spacing:-.01em;margin-bottom:9px;line-height:1.3;}
.dgr{display:flex;gap:11px;font-size:14px;padding:3px 0;}
.dgr .dgk{flex:none;width:46px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:{{FAINT}};padding-top:2px;}
.dgr.act{margin-top:5px;padding-top:9px;border-top:1px solid {{LINE}};}
.dgr.act .dgk{color:{{ACCENT}};} .dgr.act span:last-child{font-weight:560;}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:11px;}
.card{background:{{PANEL}};border:1px solid {{LINE}};border-radius:12px;padding:14px 16px;box-shadow:{{SHADOW}};}
.card .nm{font-weight:620;} .card .cl{color:{{MUT}};font-size:12px;margin:4px 0 8px;} .card .wt{font-size:13.5px;color:{{INK}};}
.pill{display:inline-block;border-radius:20px;padding:1px 8px;font-size:10.5px;font-weight:700;letter-spacing:.02em;vertical-align:middle;}
.pill.t1{background:{{ACCSOFT}};color:{{ACCENT}};} .pill.t2{background:{{ACC2SOFT}};color:{{ACCENT2}};} .pill.t3{background:{{LINE}};color:{{MUT}};}
.pill.new{background:{{ACCSOFT}};color:{{ACCENT}};}
ol.threats{padding-left:20px;margin:0;} ol.threats li{margin-bottom:8px;}
.map{position:relative;height:480px;background:{{PANEL}};border:1px solid {{LINE}};border-radius:14px;overflow:hidden;box-shadow:{{SHADOW}};}
.cmq{position:absolute;background:{{LINE}};} .cmv{left:50%;top:5%;bottom:9%;width:1px;} .cmh{top:50%;left:6%;right:4%;height:1px;}
.cmax{position:absolute;font-size:9px;letter-spacing:.08em;text-transform:uppercase;color:{{FAINT}};}
.cmx{left:84px;right:18px;bottom:11px;text-align:center;} .cmy{left:5px;top:50%;transform:translateY(-50%) rotate(-90deg);white-space:nowrap;}
.cmlead{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;}
.cmdot{position:absolute;border-radius:50%;transform:translate(-50%,-50%);cursor:default;}
.cmdot.t1{width:11px;height:11px;background:{{ACCENT}};box-shadow:0 0 0 3px {{ACCSOFT}};}
.cmdot.t2{width:9px;height:9px;background:{{ACCENT2}};opacity:.85;}
.cmlbl{position:absolute;transform:translate(-50%,-50%);font-size:11px;font-weight:620;white-space:nowrap;color:{{INK}};background:{{PANEL}};padding:1px 4px;border-radius:4px;cursor:default;}
.cmtip{display:none;position:absolute;left:0;top:0;width:194px;background:{{PANEL}};border:1px solid {{LINE}};border-radius:11px;padding:10px 12px;box-shadow:{{SHADOW}};z-index:40;transform:translate(-50%,12px);text-align:left;white-space:normal;}
.cmdot:hover{z-index:30;} .cmdot:hover .cmtip{display:block;}
.cmtn{font-weight:640;font-size:13px;display:flex;align-items:center;gap:6px;} .cmtm{color:{{MUT}};font-size:11px;margin:3px 0 5px;} .cmtw{color:{{INK}};font-size:11.5px;line-height:1.4;}
.cmtc{font-size:10px;font-weight:700;padding:1px 6px;border-radius:5px;} .cmtc.t1{background:{{ACCSOFT}};color:{{ACCENT}};} .cmtc.t2{background:{{ACC2SOFT}};color:{{ACCENT2}};}
.cap{color:{{FAINT}};font-size:12px;margin-top:9px;}
.controls{display:flex;gap:9px;flex-wrap:wrap;margin-bottom:12px;}
input[type=search]{flex:1;min-width:220px;background:{{PANEL}};border:1px solid {{LINE}};border-radius:9px;color:{{INK}};padding:9px 13px;font-size:14px;}
button.f{background:{{PANEL}};border:1px solid {{LINE}};border-radius:9px;color:{{MUT}};padding:8px 14px;cursor:pointer;font-size:13px;}
button.f.on{color:{{ACCENT}};border-color:{{ACCENT}};}
table{width:100%;border-collapse:collapse;} th{text-align:left;color:{{MUT}};font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;padding:8px 10px;border-bottom:1px solid {{LINE}};white-space:nowrap;}
td{padding:11px 10px;border-bottom:1px solid {{LINE}};vertical-align:top;} td .nm{font-weight:620;}
a.dom{color:{{ACCENT}};font-size:12px;text-decoration:none;} td.what{max-width:420px;font-size:13.5px;} .why{color:{{MUT}};font-size:12px;margin-top:4px;} .note{color:#c08a1a;font-size:12px;margin-top:3px;}
.dt{white-space:nowrap;color:{{MUT}};font-size:12.5px;}
.lognotes{background:{{PANEL2}};border:1px solid {{LINE}};border-radius:12px;padding:14px 16px;color:{{MUT}};font-size:13px;}
.foot{margin-top:46px;color:{{FAINT}};font-size:12px;} .foot a{color:{{ACCENT}};}
</style></head><body><div class="wrap">

<div class="brandrow">{{LOGO}}<h1>{{TITLE}}</h1></div>
<p class="tagline">{{TAGLINE}}</p>
<div class="meta">Scan of {{RUNDATE}} ({{RUNNER}}) · {{N_ALL}} competitors tracked</div>

<div class="stats">
  <div class="stat"><b style="color:{{ACCENT}}">{{N_NEW}}</b><span>new this scan</span></div>
  <div class="stat"><b>{{N_ALL}}</b><span>tracked</span></div>
  <div class="stat"><b style="color:{{ACCENT}}">{{N_T1}}</b><span>Tier 1 · direct</span></div>
  <div class="stat"><b style="color:{{ACCENT2}}">{{N_T2}}</b><span>Tier 2 · adjacent</span></div>
  <div class="stat"><b>{{N_T3}}</b><span>Tier 3 · context</span></div>
</div>

<section class="sec"><div class="sh hero-sh">What changed &amp; what to do · {{DDATE}}</div>
{{DIGEST}}</section>

{{MAP}}

<section class="sec"><div class="sh">New this scan</div><div class="cards">{{NEWCARDS}}</div></section>

<section class="sec"><div class="sh">Top threats right now</div><ol class="threats">{{THREATS}}</ol></section>

<section class="sec"><div class="sh">Full registry</div>
<div class="controls"><input type="search" id="q" placeholder="Search name, domain, description, cluster…">
<button class="f on" data-t="all">All</button><button class="f" data-t="1">Tier 1</button>
<button class="f" data-t="2">Tier 2</button><button class="f" data-t="3">Tier 3</button><button class="f" data-t="new">New</button></div>
<table id="reg"><thead><tr><th>Company</th><th>Tier</th><th>Cluster</th><th>Stage</th><th>HQ</th><th>First seen</th><th>What / why it matters</th></tr></thead>
<tbody>{{ROWS}}</tbody></table></section>

<section class="sec"><div class="sh">Latest scan log</div><div class="lognotes">{{NOTES}}</div></section>

<div class="foot">Deterministic render of your registry — the model never writes this file. Powered by <b>Pulse</b>{{REPOLINK}}.</div>
</div>
<script>(function(){var q=document.getElementById('q'),rows=[].slice.call(document.querySelectorAll('#reg tbody tr')),mode='all';
function apply(){var t=(q.value||'').toLowerCase();rows.forEach(function(r){var okM=mode==='all'||(mode==='new'?r.hasAttribute('data-new'):r.getAttribute('data-tier')===mode);var okT=!t||r.textContent.toLowerCase().indexOf(t)!==-1;r.style.display=(okM&&okT)?'':'none';});}
q.addEventListener('input',apply);document.querySelectorAll('button.f').forEach(function(b){b.addEventListener('click',function(){document.querySelectorAll('button.f').forEach(function(x){x.classList.remove('on');});b.classList.add('on');mode=b.getAttribute('data-t');apply();});});})();</script>
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    root = Path(a.root)
    render(root, Path(a.out) if a.out else root / "data/report.html")


if __name__ == "__main__":
    main()
