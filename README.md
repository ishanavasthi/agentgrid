# ⚡ AgentGrid — autonomous multi-agent coding pipeline

**Google DeepMind Bangalore Hackathon — Track: Autonomous Orchestration
with Managed Agents (iAPI / Antigravity)**

Nine specialized agents take a software issue from report to merged,
tested, PR-ready code — planning, delegating through a **structured
handoff ledger**, coding **in parallel git worktrees**, arguing through
**review rejections**, resolving **real merge conflicts**, surviving
**adversarial test attacks**, matching **design mockups by vision**, and
accepting issues **by voice note in Hinglish**.

The entire pipeline runs offline with **zero third-party dependencies**
(deterministic mock backend; every file write, git branch, merge conflict
and unittest run is real) and switches to **live Gemini function-calling**
the moment a `GEMINI_API_KEY` lands in `.env` — with a real Managed
Agents hybrid path (`client.agents`/`client.interactions`, confirmed
live end-to-end 2026-07-11 on google-genai 2.11.0) for the tool-less
reasoning roles, and Gemini function-calling for roles that touch the
local repo. The Managed Agents surface needs **Python >= 3.10**
specifically — google-genai dropped 3.9 support after 1.47.0, and pip
silently installs that older, surface-less release on 3.9 with no error.
Feature-detected either way: HybridBackend falls back to pure
function-calling for every role if the surface isn't there, so the
pipeline never breaks — it just quietly loses the Managed Agents story
on old Python.

---

## Quickstart (today — no API key, no pip installs)

```bash
python3 -m agentgrid smoke          # all 4 pipelines end-to-end, offline
python3 -m agentgrid serve          # live dashboard → http://127.0.0.1:8765
python3 -m agentgrid run --issue ISSUE-1   # one pipeline in the terminal
python3 -m unittest discover -s tests -t . # unit + e2e suite (13 tests)
```

## Going live (plug the key)

```bash
python3.10 -m venv .venv && source .venv/bin/activate  # MUST be >= 3.10 —
                                                          # see note below
cp .env.example .env                # then paste GEMINI_API_KEY=...
pip install google-genai            # Tier 1 — required for real agents
python3 -m agentgrid doctor --probe # verifies key, SDK, model ids, surfaces, live round-trip
python3 -m agentgrid run --issue ISSUE-1 --backend auto
```

**Use a Python >= 3.10 interpreter for the venv.** On Python 3.9, `pip
install google-genai` silently resolves to 1.47.0 (the last
3.9-compatible release) instead of the real 2.x line — it installs
cleanly, `doctor` shows everything green except a plain "surface absent"
on the managed-agents row, and there's no error pointing at the actual
cause. `gemini`/`auto`/mock backends work fine on 3.9 either way; only
the real Managed Agents path needs 3.10+.

`doctor` lists exactly which model ids your key can reach — pick one via
`AGENTGRID_MODEL` in `.env` (verified working: `gemini-3.5-flash`,
`gemini-flash-latest`). `--backend managed`/`auto` use the real
`client.agents`/`client.interactions` surface when Python >= 3.10 +
google-genai >= 2.0 are both present; otherwise they fall back to
`gemini` (pure function-calling) automatically.

Optional extras:

```bash
pip install playwright && playwright install chromium   # Tier 2: real screenshots for visual mode
brew install gh && gh auth login                        # Tier 3: real GitHub PRs (set GITHUB_REPO in .env)
```

Without Tier 2/3 nothing breaks: the Verifier falls back to HTML-source
inspection, and the Publisher pushes to a local bare origin + writes
`runs/<id>/pr_preview.md`.

---

## The 9 functionalities

| # | Functionality | Where |
|---|---------------|-------|
| 1 | Core issue→patch loop (Planner → Coder → Tester) | `pipeline/orchestrator.py` |
| 2 | Structured handoff ledger (tasks, packets, no lost context) | `ledger.py` |
| 3 | Reviewer–Coder critique loop (real rejections, bounded rounds) | `_implement_subtask` |
| 4 | Parallel coder fan-out in git worktrees + Integrator resolving real merge conflicts | `_standard_core` + `tools/gitops.py` |
| 5 | Live dashboard (SSE, agent graph, feed, ledger board — stdlib server, no CDNs) | `server/` |
| 6 | PR finale (gh CLI when available; local push + preview always) | `tools/github.py` |
| 7 | Breaker/Fixer adversarial TDD (failing spec tests until concession) | `_run_adversarial` |
| 8 | Screenshot-to-feature with an **interactive Computer Use Verifier** — drives a real browser (click/scroll/type) via Gemini 3.5 Flash's `computer_use` tool to check the fix, not just a static screenshot diff; falls back to vision-on-screenshot / HTML source if unavailable | `_run_visual`, `llm/computer_use.py`, `tools/computer_use.py` |
| 9 | Voice-issue intake (Hinglish audio → structured issue) + legacy modernization | `_run_voice` |

## Architecture

```
            ┌────────────────────────── EventBus ── SSE ──► Dashboard / CLI
            │
 issue ─► Orchestrator ─► Planner ──► plan (1–3 subtasks)
            │                │ handoff packets via Task Ledger (ledger.json)
            │        ┌───────┴────────┐        parallel git worktrees
            │     Coder A          Coder B ◄──── Reviewer (reject → revise)
            │        └───────┬────────┘
            │            Integrator  ◄──── real `git merge` conflicts
            │              Tester    ◄──── stdlib unittest = ground truth
            │             Publisher  ──► branch push + PR
            │
       LLM backends (swappable, one interface — llm/base.py):
         mock     deterministic fixtures; tools execute for real (today)
         gemini   gemini-3.5-flash function calling (any google-genai
                  release, Python >= 3.9 is fine)
         managed  Managed Agents (antigravity-preview-05-2026) via the
                  Interactions API for reasoning roles (Planner, Reviewer,
                  Verifier, Intake, Publisher) + gemini function calling
                  for roles that edit local files (Coder, Integrator,
                  Breaker)  ← the hybrid is the architecture story
                  (needs google-genai >= 2.0, which needs Python >= 3.10)
```

Design decisions that matter in judging Q&A:

- **Handoffs don't lose context** because agents exchange structured
  packets (task, acceptance criteria, prior critiques) via the ledger —
  not chat transcripts. Every handoff is recorded and visible live.
- **Tests are ground truth, not opinions**: the Tester is deterministic
  code; no model sits between the suite and control flow.
- **Safety/predictability**: every agent's file access is jailed to its
  worktree (`tools/fs.py` rejects path escapes), tool crashes return
  errors instead of killing the run, and review/attack loops are bounded.
- **The mock backend mocks only the intelligence** — file writes, git
  worktrees, merges, conflicts and test runs are real, so offline smoke
  tests exercise the true pipeline.

## Demo repo: SplitSathi 🇮🇳

The target is `demo/target_template` — a UPI-flavored expense-splitting
library with a passing suite and four planted issues:
paisa truncation + settlement-summary feature (engineered to collide in
`money.py` → live merge conflict), a paise-conservation leak for the
Breaker, a stats-page mockup for the Verifier, and a 2019-vintage legacy
module filed **by Hinglish voice note** — the legacy-modernization story
Indian IT services run at scale.

`python3 -m agentgrid setup-demo` seeds a bare origin under `runs/`;
every run clones fresh, so demos reset for free.

## 3-minute demo script

1. Dashboard up (`serve`), pick **ISSUE-1** → watch Planner fan out two
   Coders in parallel; Reviewer **rejects** the float fix; Coder rebuilds
   on Decimal; **merge conflict flashes**; Integrator resolves; tests go
   green; PR appears. (~90s)
2. **ISSUE-3** visual: the Verifier drives a real browser via Gemini's
   **Computer Use** tool — clicking/scrolling the live page itself
   (`AGENTGRID_CU_HEADED=1` to watch the window) instead of judging a
   static screenshot. (~20s)
3. **ISSUE-2** adversarial: Breaker plants red tests, Coder answers,
   Breaker concedes. (~45s)
4. **ISSUE-4** voice: play the Hinglish note, Intake structures it, the
   legacy module gets modernized to green. (~30s)
5. Show `runs/<id>/ledger.json` + the PR preview: every handoff receipted.

## Dependencies

| Tier | What | Needed for |
|------|------|------------|
| 0 | Python ≥ 3.9 + git — **nothing to pip install** | smoke, mock runs, dashboard, unit tests |
| 1 | Python ≥ 3.9, `pip install google-genai` + `GEMINI_API_KEY` | real Gemini function-calling runs (`--backend gemini`) |
| 1.5 | **Python ≥ 3.10** venv, `pip install google-genai` (resolves to 2.x) | real Managed Agents runs (`--backend managed`/`auto`) — on Python 3.9 the same pip command silently installs 1.47.0 instead, which lacks the surface entirely |
| 2 | `pip install playwright` + `playwright install chromium` | Computer Use Verifier's execution arm + static screenshots — without it, visual mode falls back to vision-on-HTML-source (optional, but recommended: this is where Computer Use lives) |
| 3 | `gh` CLI authenticated + `GITHUB_REPO` in `.env` | real GitHub PRs (optional) |
