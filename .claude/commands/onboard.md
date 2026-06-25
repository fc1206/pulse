---
description: First-run onboarding. Sets this radar up end-to-end from one command, right after forking. Run this if someone just pointed you at the repo.
---

# Onboard

You are setting this competitor radar up for a new owner who may be **non-technical**. Do **everything for them in this chat** — never tell them to edit a file, run a terminal command, or read YAML. Be warm, brief, concrete. One or two questions at a time, never a wall.

## 0. Welcome (2 lines)
Tell them what they're getting: *a private competitor radar they own — it scans the web twice a week, keeps a tiered, deduped database of their competitors, and hands them a short "what changed → what to do" brief.* Say you'll ask a few quick questions and build it live, right now.

## 1. Interview + configure → run `/setup`
Execute the `/setup` command in full: interview them about their company, lane, and known competitors; capture their **brand** (company name, accent color); and write `config/context.md`, `config/rubric.md`, `config/queries.md`, `config/brand.json`, and a seed registry.
**`config/context.md` is the highest-leverage file** — a vague lane produces a useless brief. Push for sharpness: the exact promise a rival must threaten, the 3–5 axes that decide who competes, and the *wrong-vocabulary* competitor they're most likely to miss.

## 2. First scan — NO API key needed yet
Run `/scan` now, interactively. This uses **your own model access** (you, the agent, are running it), so they get their first real result **without setting up any key or secret**. Produce the registry, the digest, and the report.

## 3. Show them the payoff
Render and open the deliverable:
```bash
python3 scripts/render_report.py && open data/report.html 2>/dev/null || true
```
Then, in one short paragraph, walk them through the **digest**: the 1–3 things that changed and what to do about each. This is the moment they understand the product — make it land. Point them at `data/report.html` as their living dashboard.

## 4. Autopilot — the one manual step, and it's a GUI
For the radar to run itself twice a week it needs their Anthropic API key stored as a GitHub **secret**. This is the only thing they do by hand, and it is a **graphical web page — never a terminal or text editor**:
1. Get their repo path: `git remote get-url origin` → derive `<owner>/<repo>`.
2. Give them this exact deep link (GitHub's secrets GUI, name pre-filled):
   `https://github.com/<owner>/<repo>/settings/secrets/actions/new?name=ANTHROPIC_API_KEY`
   Tell them: open it → paste their key from **console.anthropic.com** (Settings → API Keys) → click **Add secret**. ~30 seconds.
3. Once they confirm it's added, **you** enable the schedule for them: uncomment the `schedule:` block at the top of `.github/workflows/scan.yml` and commit. From then on it runs Mon/Thu on its own.
- If they're not ready for autopilot, that's fine — they can run `/scan` manually anytime, key-free, through you.

## 5. Done — recap
Summarize: their radar is live (N competitors tracked, here's this week's brief in one line), what happens next (auto-scan Mon/Thu if they added the key), and the one habit that keeps it sharp — keep `config/context.md` current as their strategy moves. Privacy note: keep the repo **private** if their competitor set is sensitive; the report is a local file, not published anywhere unless they choose to.
