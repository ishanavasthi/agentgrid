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
and unittest run is real) and switches to **Gemini 3.5 Flash + Managed
Agents** the moment a `GEMINI_API_KEY` lands in `.env`.

---

## Quickstart (today — no API key, no pip installs)

```bash
python3 -m agentgrid smoke          # all 4 pipelines end-to-end, offline
python3 -m agentgrid serve          # live dashboard → http://127.0.0.1:8765
python3 -m agentgrid run --issue ISSUE-1   # one pipeline in the terminal
python3 -m unittest discover -s tests -t . # unit + e2e suite (13 tests)
```

## Going live (tomorrow — plug the key)

```bash
cp .env.example .env                # then paste GEMINI_API_KEY=...
pip install "google-genai>=2.0.0"   # Tier 1 — required for real agents
python3 -m agentgrid doctor         # verifies key, SDK, model ids, surfaces
python3 -m agentgrid run --issue ISSUE-1 --backend managed
```

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
| 8 | Screenshot-to-feature with visual Verifier (Gemini vision / HTML fallback) | `_run_visual` |
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
         gemini   gemini-3.5-flash function calling (google-genai ≥ 2.0)
         managed  Managed Agents (antigravity-preview-05-2026) via the
                  Interactions API for reasoning roles (Planner, Reviewer,
                  Verifier, Intake, Publisher) + gemini function calling
                  for roles that edit local files (Coder, Integrator,
                  Breaker)  ← the hybrid is the architecture story
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
2. **ISSUE-2** adversarial: Breaker plants red tests, Coder answers,
   Breaker concedes. (~45s)
3. **ISSUE-4** voice: play the Hinglish note, Intake structures it, the
   legacy module gets modernized to green. (~30s)
4. Show `runs/<id>/ledger.json` + the PR preview: every handoff receipted.

## Dependencies

| Tier | What | Needed for |
|------|------|------------|
| 0 | Python ≥ 3.9 + git — **nothing to pip install** | smoke, mock runs, dashboard, unit tests |
| 1 | `pip install "google-genai>=2.0.0"` + `GEMINI_API_KEY` | real Gemini / Managed Agents runs |
| 2 | `pip install playwright` + `playwright install chromium` | real screenshots in visual mode (optional) |
| 3 | `gh` CLI authenticated + `GITHUB_REPO` in `.env` | real GitHub PRs (optional) |
