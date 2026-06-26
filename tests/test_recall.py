"""Recall-channel regression guard.

The founding failure (low-footprint) was a RECALL miss — a real competitor in
adjacent vocabulary, no US press, invisible to the obvious queries. The defense
is the breadth of the query battery, not the merge plumbing. These tests fail if
a recall-critical channel is silently deleted or emptied:

- Block F  — always-on lookalikes/alternatives/vs (every entrant writes a vs-X page)
- Block H  — geographic / non-US (the literal low-footprint gap: Melbourne, no US press)
- Block I  — edge-expansion: harvest the competitor sets G2/rivals already publish
- Block B  — data-intelligence vocabulary (low-footprint's own cluster)

NOTE: this is the DETERMINISTIC half of recall — it proves the channels exist and
are wired into rotation. The SUFFICIENT proof (remove a known company and watch
live discovery re-find it) needs live web search and is a periodic integration
check, documented in the project README — not a unit test. Green here does
not by itself prove recall.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
QUERIES = (REPO / "config" / "queries.md").read_text(encoding="utf-8")


def block_bodies(text: str) -> dict:
    """Map block id -> body text, matching plan_run.py's '## Block X:' contract."""
    parts = re.split(r"^## Block ([A-Z]):", text, flags=re.M)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts), 2)}


BLOCKS = block_bodies(QUERIES)


def test_recall_critical_blocks_exist():
    for b in ("B", "F", "H", "I"):
        assert b in BLOCKS, f"recall-critical Block {b} is missing from config/queries.md"
        assert BLOCKS[b].strip(), f"Block {b} exists but is empty"


def test_block_f_has_alternatives_and_vs():
    body = BLOCKS["F"].lower()
    assert "alternative" in body, "Block F lost its 'alternatives' channel"
    assert "vs " in body or '"vs ' in body, "Block F lost its per-Tier-1 'vs X' channel"


def test_block_h_covers_non_us():
    body = BLOCKS["H"].lower()
    regions = ("australia", "india", "europe", "israel", "singapore", "uk", "germany", "new zealand")
    assert any(r in body for r in regions), "Block H lost non-US geographic coverage (the low-footprint gap)"


def test_block_i_edge_expansion_signatures():
    body = BLOCKS["I"].lower()
    signatures = ("g2", "capterra", "sourceforge", "compare", "alternatives", "similar companies")
    hits = [s for s in signatures if s in body]
    assert len(hits) >= 2, f"Block I missing edge-expansion signatures (found {hits})"


def test_block_b_is_substantive():
    """Block B is the wrong-vocabulary / low-footprint channel. Its exact words are
    market-specific (a fork's /setup rewrites them), so we test the mechanism — that the
    channel carries real queries — not one market's vocabulary."""
    queries = [l for l in BLOCKS["B"].splitlines() if l.strip().startswith("-")]
    assert queries, "Block B (the wrong-vocabulary low-footprint channel) has no queries"


def test_plan_run_sees_new_block(tmp_path):
    """plan_run.py must parse Block I and track it in the coverage ledger."""
    root = tmp_path / "repo"
    (root / "data").mkdir(parents=True)
    (root / "config").mkdir()
    (root / "data/registry.csv").write_text(
        "domain,name,tier,cluster,status,stage,hq,founded,first_seen,last_checked,"
        "what,why_tier,evidence_url,notes\n"
        "alpha.example,Alpha,1,direct,active,series-f,US,2019,2026-06-10,2026-06-10,x,y,https://alpha.example/,\n",
        encoding="utf-8",
    )
    (root / "data/state.json").write_text(json.dumps({
        "schema": 1, "block_cursor": 0, "status_cursor": 0, "status_batch": 8,
        "emphasis_per_run": 2, "last_run": "2026-06-10", "last_runner": "test", "coverage": {},
    }), encoding="utf-8")
    # Battery including Block I but with I never swept (not in coverage).
    (root / "config/queries.md").write_text(
        "# Q\n\n## Block A: self\n- q1\n\n## Block F: lookalike\n- alternatives\n\n"
        "## Block I: edge-expansion\n- site:g2.com compare\n",
        encoding="utf-8",
    )
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "plan_run.py"), "--root", str(root)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    plan = json.loads(r.stdout)
    stale = {s["block"] for s in plan["stale_coverage"]}
    assert "I" in stale, "plan_run.py did not parse/track Block I in the coverage ledger"
