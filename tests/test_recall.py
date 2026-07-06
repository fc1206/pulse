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
check — the re-find probe in config/queries.md's status-sweep section — not a
unit test. Green here does not by itself prove recall.
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
    # Structural, not vocabulary-pinned: a fork tailors regions to ITS market
    # (LATAM, MENA, ...), so asserting specific region names would fail a
    # correctly tailored battery. The guard is that the channel still carries
    # multiple query lines — deleting or emptying it is what must trip this.
    lines = [l for l in BLOCKS["H"].splitlines() if l.strip().startswith("- ")]
    assert len(lines) >= 2, "Block H lost its geographic recall queries (the low-footprint gap)"


def test_block_i_edge_expansion_signatures():
    # Tolerant of per-market directory tailoring (Clutch/Behance for agencies,
    # G2/Capterra for SaaS): any site:-targeted harvest, an alternatives/compare
    # channel, or an explicit directory line satisfies the edge-expansion intent.
    body = BLOCKS["I"].lower()
    lines = [l for l in BLOCKS["I"].splitlines() if l.strip().startswith("- ")]
    assert len(lines) >= 2, "Block I lost its edge-expansion queries"
    assert ("site:" in body) or ("alternatives" in body) or ("compare" in body) or ("directory" in body), \
        "Block I lost its directory/compare-list harvesting signature"


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


def test_seed_mode_plans_full_battery(tmp_path):
    """--seed plans every block (the day-one deep map); normal mode still rotates —
    including wraparound from a nonzero cursor, which rotation-at-cursor-0 can't see."""
    root = tmp_path / "repo"
    (root / "data").mkdir(parents=True)
    (root / "config").mkdir()
    (root / "data/registry.csv").write_text(
        "domain,name,tier,cluster,status,stage,hq,founded,first_seen,last_checked,"
        "what,why_tier,evidence_url,notes\n",
        encoding="utf-8",
    )
    (root / "config/queries.md").write_text(
        "# Q\n\n## Block A: a\n- q\n\n## Block B: b\n- q\n\n## Block C: c\n- q\n\n"
        "## Block F: always\n- q\n\n## Block I: edge\n- q\n",
        encoding="utf-8",
    )

    def set_cursor(cur):
        (root / "data/state.json").write_text(json.dumps({
            "schema": 1, "block_cursor": cur, "status_cursor": 0, "status_batch": 8,
            "emphasis_per_run": 2, "last_run": "2026-06-10", "last_runner": "test", "coverage": {},
        }), encoding="utf-8")

    def plan(*flags):
        r = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "plan_run.py"), "--root", str(root), *flags],
            capture_output=True, text=True,
        )
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)

    set_cursor(0)
    seed = plan("--seed")
    assert seed["seed"] is True, "--seed plan must mark itself as seed mode"
    assert seed["emphasized_blocks"] == ["A", "B", "C", "I"], \
        "--seed must plan every block (always-on F excluded from emphasis, run as usual)"

    normal = plan()
    assert normal["seed"] is False
    assert normal["emphasized_blocks"] == ["A", "B"], "normal mode must still rotate"

    # nonzero cursor: 3 over the 4 rotating blocks [A, B, C, I] must wrap to [I, A] —
    # a cursor-0-only test would pass even if the modulo wraparound were broken
    set_cursor(3)
    wrapped = plan()
    assert wrapped["emphasized_blocks"] == ["I", "A"], \
        "block_cursor=3 over 4 rotating blocks must wrap around, not fall off the end"
    assert plan("--seed")["emphasized_blocks"] == ["A", "B", "C", "I"], \
        "--seed must plan the full battery regardless of the cursor position"
