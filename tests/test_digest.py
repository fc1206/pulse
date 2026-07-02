"""Tests for the digest linter — the anti-slop gate — and the action ledger."""
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

GOOD = """## 2026-06-15 — digest (test)

### 1. Acme pivoted into our lane
**Signal:** Acme now sells cross-tool context (https://acme.test/post).
**Why it matters:** Collides with pillar 2 in our exact ICP.
**Action:** Write the Acme battlecard and ship a positioning memo by 2026-06-19.
"""

SECOND = """## 2026-06-20 — digest (test)

### 1. Beta raised a big round
**Signal:** Beta raised $50M (https://beta.test/round).
**Why it matters:** Prices our exact wedge.
**Action:** Add the Beta slide to the fundraise deck by 2026-07-01.

### 2. Gamma shipped a rival graph
**Signal:** Gamma launched cross-tool graph search (https://gamma.test).
**Why it matters:** Pillar 2 collision in our ICP.
**Action:** Draft the Gamma teardown memo this week.
"""

# a same-date SECOND entry (recovery runs are real) with a different action
SAME_DAY = """## 2026-06-15 — digest (recovery)

### 1. Delta shipped a rival connector
**Signal:** Delta shipped a cross-tool connector (https://delta.test/launch).
**Why it matters:** Second entrant in our lane this week.
**Action:** Ship the Delta counter-positioning note by 2026-06-21.
"""

# the Action paragraph wraps: the due date sits on the continuation line
WRAPPED = """## 2026-06-15 — digest (test)

### 1. Acme pivoted into our lane
**Signal:** Acme now sells cross-tool context (https://acme.test/post).
**Why it matters:** Collides with pillar 2 in our exact ICP.
**Action:** Write the Acme battlecard and ship a positioning memo
covering the wrapped continuation line by 2026-06-19.
"""

def make_repo(tmp_path):
    # no config/brand.json on purpose: exercises the generic why_label default
    root = tmp_path / "r"
    (root / "data").mkdir(parents=True)
    (root / "runs/2026-06-15").mkdir(parents=True)
    (root / "data/registry.csv").write_text(
        "domain,name,tier,cluster,status,stage,hq,founded,first_seen,last_checked,what,why_tier,evidence_url,notes\n"
        "acme.test,Acme,2,direct,active,seed,US,2024,2026-06-10,2026-06-10,x,y,https://acme.test/,\n",
        encoding="utf-8")
    (root / "data/DIGEST.md").write_text("# Digest\n\n<!-- entries below -->\n", encoding="utf-8")
    return root

def env_for(clean):
    """Authorize writes (intentional local test writes) via RADAR_ALLOW_WRITE=1;
    clean=True strips that and GITHUB_ACTIONS to simulate an unauthorized runner."""
    if clean:
        return {k: v for k, v in os.environ.items()
                if k not in ("GITHUB_ACTIONS", "RADAR_ALLOW_WRITE")}
    return {**os.environ, "RADAR_ALLOW_WRITE": "1"}

def run(root, digest_text, dry=False, clean=False):
    (root / "runs/2026-06-15/digest.md").write_text(digest_text, encoding="utf-8")
    args = [sys.executable, str(REPO / "scripts/validate_digest.py"),
            "--run-dir", str(root / "runs/2026-06-15"), "--root", str(root)]
    if dry:
        args.append("--dry-run")
    return subprocess.run(args, capture_output=True, text=True, env=env_for(clean))

def run_cli(root, *args, clean=False):
    return subprocess.run(
        [sys.executable, str(REPO / "scripts/validate_digest.py"), "--root", str(root), *args],
        capture_output=True, text=True, env=env_for(clean))

def test_good_digest_accepted_and_prepended(tmp_path):
    root = make_repo(tmp_path)
    r = run(root, GOOD)
    assert r.returncode == 0, r.stdout + r.stderr
    doc = (root / "data/DIGEST.md").read_text(encoding="utf-8")
    assert "Acme pivoted into our lane" in doc
    assert doc.index("<!-- entries below -->") < doc.index("Acme pivoted")

def test_slop_phrase_rejected(tmp_path):
    root = make_repo(tmp_path)
    bad = GOOD.replace("Collides with pillar 2", "The rapidly evolving landscape collides with pillar 2")
    r = run(root, bad)
    assert r.returncode == 1 and "slop" in r.stdout

def test_lazy_action_rejected(tmp_path):
    root = make_repo(tmp_path)
    bad = GOOD.replace("Write the Acme battlecard and ship a positioning memo by 2026-06-19.",
                       "Monitor Acme for further developments in the coming weeks.")
    r = run(root, bad)
    assert r.returncode == 1 and "monitor" in r.stdout

def test_missing_label_rejected(tmp_path):
    root = make_repo(tmp_path)
    bad = GOOD.replace("**Why it matters:** Collides with pillar 2 in our exact ICP.\n", "")
    r = run(root, bad)
    assert r.returncode == 1 and "Why it matters" in r.stdout

def test_uncited_item_rejected(tmp_path):
    root = make_repo(tmp_path)
    bad = GOOD.replace("(https://acme.test/post)", "").replace("acme.test", "somewhere")
    r = run(root, bad)
    assert r.returncode == 1 and "citation" in r.stdout

def test_no_signal_sentinel_accepted(tmp_path):
    root = make_repo(tmp_path)
    r = run(root, "## 2026-06-15 — digest (test)\n\nNO ACTIONABLE SIGNAL — four T3 infra finds, nothing clears the 2-8 week bar.\n")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "NO ACTIONABLE SIGNAL" in (root / "data/DIGEST.md").read_text(encoding="utf-8")

def test_three_items_rejected(tmp_path):
    root = make_repo(tmp_path)
    extra = ("\n### {n}. Item number {n}\n"
             "**Signal:** Fact number {n} (https://acme.test/{n}).\n"
             "**Why it matters:** Collides with pillar 2.\n"
             "**Action:** Ship teardown memo number {n} by 2026-07-01.\n")
    r = run(root, GOOD + extra.format(n=2) + extra.format(n=3))
    assert r.returncode == 1 and "max 2" in r.stdout

def test_actions_logged_on_merge(tmp_path):
    root = make_repo(tmp_path)
    r = run(root, GOOD)
    assert r.returncode == 0, r.stdout + r.stderr
    led = (root / "data/ACTIONS.md").read_text(encoding="utf-8")
    assert "- 2026-06-15.1 | open | due 2026-06-19 | Write the Acme battlecard" in led

def test_merge_never_duplicates_ledger_ids(tmp_path):
    root = make_repo(tmp_path)
    assert run(root, GOOD).returncode == 0
    assert run(root, GOOD).returncode == 0  # blind retry of the same run
    led = (root / "data/ACTIONS.md").read_text(encoding="utf-8")
    assert led.count("2026-06-15.1") == 1

def test_backfill_idempotent(tmp_path):
    root = make_repo(tmp_path)
    (root / "data/DIGEST.md").write_text(
        "# Digest\n\n<!-- entries below -->\n\n" + SECOND + "\n" + GOOD, encoding="utf-8")
    r = run_cli(root, "--backfill")
    assert r.returncode == 0, r.stdout + r.stderr
    first = (root / "data/ACTIONS.md").read_text(encoding="utf-8")
    assert "- 2026-06-20.1 | open | due 2026-07-01 |" in first
    assert "- 2026-06-20.2 | open | due - |" in first  # no "by YYYY-MM-DD" in action
    assert "- 2026-06-15.1 | open | due 2026-06-19 |" in first
    r2 = run_cli(root, "--backfill")
    assert r2.returncode == 0 and "0 action row(s)" in r2.stdout
    assert (root / "data/ACTIONS.md").read_text(encoding="utf-8") == first

def test_same_date_second_entry_gets_next_free_id(tmp_path):
    """A same-date second entry's DIFFERENT action must not be dropped by an id
    collision: it takes the next free <date>.<n> and the merge reports it logged."""
    root = make_repo(tmp_path)
    assert run(root, GOOD).returncode == 0
    r = run(root, SAME_DAY)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "1 action row(s) logged" in r.stdout  # nonzero, not silently deduped away
    led = (root / "data/ACTIONS.md").read_text(encoding="utf-8")
    assert "- 2026-06-15.1 | open | due 2026-06-19 | Write the Acme battlecard" in led
    assert "- 2026-06-15.2 | open | due 2026-06-21 | Ship the Delta counter-positioning note" in led

def test_same_date_reallocation_stays_idempotent(tmp_path):
    """After a same-date id reallocation, a blind merge retry and a --backfill must
    both add nothing (dedupe is by date-scoped excerpt, so retries converge)."""
    root = make_repo(tmp_path)
    assert run(root, GOOD).returncode == 0
    assert run(root, SAME_DAY).returncode == 0
    led = (root / "data/ACTIONS.md").read_text(encoding="utf-8")
    r = run(root, SAME_DAY)  # blind retry of the recovery run
    assert r.returncode == 0 and "0 action row(s)" in r.stdout
    r2 = run_cli(root, "--backfill")
    assert r2.returncode == 0 and "0 action row(s)" in r2.stdout
    assert (root / "data/ACTIONS.md").read_text(encoding="utf-8") == led

def test_wrapped_action_keeps_due_date_and_full_excerpt(tmp_path):
    """The Action is a paragraph: a wrapped line must keep its 'by YYYY-MM-DD' due
    date and its continuation text in the ledger excerpt, not stop at the newline."""
    root = make_repo(tmp_path)
    r = run(root, WRAPPED)
    assert r.returncode == 0, r.stdout + r.stderr
    led = (root / "data/ACTIONS.md").read_text(encoding="utf-8")
    assert ("- 2026-06-15.1 | open | due 2026-06-19 | Write the Acme battlecard and ship "
            "a positioning memo covering the wrapped continuation line by 2026-06-19.") in led

def test_resolve_happy_path(tmp_path):
    root = make_repo(tmp_path)
    assert run(root, GOOD).returncode == 0
    r = run_cli(root, "--resolve", "2026-06-15.1", "--status", "done", "--note", "shipped memo")
    assert r.returncode == 0, r.stdout + r.stderr
    led = (root / "data/ACTIONS.md").read_text(encoding="utf-8")
    assert f"- 2026-06-15.1 | done {date.today().isoformat()} | due 2026-06-19 |" in led
    assert "note: shipped memo" in led

def test_resolve_unknown_id_errors(tmp_path):
    root = make_repo(tmp_path)
    assert run(root, GOOD).returncode == 0
    r = run_cli(root, "--resolve", "2099-01-01.9", "--status", "done")
    assert r.returncode != 0 and "2099-01-01.9" in (r.stdout + r.stderr)

def test_dry_run_writes_nothing(tmp_path):
    root = make_repo(tmp_path)
    r = run(root, GOOD, dry=True, clean=True)  # lint needs no write auth
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (root / "data/ACTIONS.md").exists()
    assert "Acme pivoted" not in (root / "data/DIGEST.md").read_text(encoding="utf-8")

def test_unauthorized_runner_cannot_write(tmp_path):
    root = make_repo(tmp_path)
    r = run(root, GOOD, clean=True)
    assert r.returncode != 0 and "REFUSING TO WRITE" in (r.stdout + r.stderr)
    assert not (root / "data/ACTIONS.md").exists()
    assert "Acme pivoted" not in (root / "data/DIGEST.md").read_text(encoding="utf-8")

def test_unauthorized_backfill_blocked(tmp_path):
    root = make_repo(tmp_path)
    (root / "data/DIGEST.md").write_text(
        "# Digest\n\n<!-- entries below -->\n\n" + GOOD, encoding="utf-8")
    r = run_cli(root, "--backfill", clean=True)
    assert r.returncode != 0 and "REFUSING TO WRITE" in (r.stdout + r.stderr)
    assert not (root / "data/ACTIONS.md").exists()
