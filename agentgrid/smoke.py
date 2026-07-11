"""Offline smoke suite: all four pipelines end-to-end on the mock backend.

No API key, no third-party packages — the LLM is scripted, but every
file write, git branch, worktree, merge conflict, and unittest run is
real. Exercises Functionalities 1–9 minus live-model reasoning.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .pipeline import Orchestrator
from .util import color


def _ledger_stats(run_dir: str) -> dict:
    data = json.loads((Path(run_dir) / "ledger.json").read_text(encoding="utf-8"))
    return {"handoffs": len(data["handoffs"]), "tasks": len(data["tasks"]),
            "messages": len(data["messages"])}


def _check_block(title: str, checks: list[tuple[str, bool]], verbose: bool) -> bool:
    ok = all(passed for _, passed in checks)
    if verbose:
        head = color("PASS", "green") if ok else color("FAIL", "red")
        print(f"\n[{head}] {title}")
        for name, passed in checks:
            mark = color("✓", "green") if passed else color("✗", "red")
            print(f"   {mark} {name}")
    return ok


def smoke_standard(orch: Orchestrator, verbose: bool = True) -> bool:
    s = orch.run_issue("ISSUE-1", "standard")
    stats = _ledger_stats(s["run_dir"])
    return _check_block("ISSUE-1 standard — plan → parallel code → review → merge → test → PR", [
        ("planner split into ≥2 parallel subtasks", s["subtasks"] >= 2),
        ("reviewer rejected at least one round", s["review_rejections"] >= 1),
        ("merge conflict hit and resolved by Integrator", s["conflicts_resolved"] >= 1),
        ("integrated suite green", s["tests_passed"]),
        ("branch pushed to origin", s["pr"]["pushed"]),
        ("PR preview written", Path(s["pr"]["preview_path"]).exists()),
        ("ledger persisted with handoffs", stats["handoffs"] >= 5),
    ], verbose)


def smoke_adversarial(orch: Orchestrator, verbose: bool = True) -> bool:
    s = orch.run_issue("ISSUE-2", "adversarial")
    stats = _ledger_stats(s["run_dir"])
    return _check_block("ISSUE-2 adversarial — breaker red → coder green → concession", [
        ("breaker landed ≥2 legitimate red rounds", s["breaker_rounds"] >= 2),
        ("breaker eventually conceded", s["conceded"]),
        ("final suite green (incl. breaker tests)", s["tests_passed"]),
        ("PR preview written", Path(s["pr"]["preview_path"]).exists()),
        ("ledger persisted with handoffs", stats["handoffs"] >= 3),
    ], verbose)


def smoke_visual(orch: Orchestrator, verbose: bool = True) -> bool:
    s = orch.run_issue("ISSUE-3", "visual")
    return _check_block("ISSUE-3 visual — mockup → implement → verify mismatch → fix → match", [
        ("verifier looped (mismatch then fix)", s["verify_rounds"] >= 2),
        ("final verdict: match", s["matched"]),
        ("unit suite still green", s["tests_passed"]),
        ("PR preview written", Path(s["pr"]["preview_path"]).exists()),
    ], verbose)


def smoke_voice(orch: Orchestrator, verbose: bool = True) -> bool:
    s = orch.run_issue("ISSUE-4", "voice")
    return _check_block("ISSUE-4 voice — audio intake → structured issue → modernize legacy", [
        ("intake produced a structured issue", bool(s.get("intake_title"))),
        ("language detected", bool(s.get("detected_language"))),
        ("pipeline completed to green tests", s["tests_passed"]),
        ("PR preview written", Path(s["pr"]["preview_path"]).exists()),
    ], verbose)


ALL = [smoke_standard, smoke_adversarial, smoke_visual, smoke_voice]


def run_smoke(verbose: bool = True) -> bool:
    os.environ["AGENTGRID_MOCK_DELAY"] = "0"
    orch = Orchestrator(backend_name="mock")
    setup = orch.setup_demo(force=True)
    if verbose:
        print(color("AgentGrid smoke suite (mock backend, zero deps, no API key)", "bold"))
        print(f"demo origin: {setup['origin']}"
              + (f" — baseline {setup.get('baseline', '')}" if setup.get("created") else ""))
    results = [fn(orch, verbose) for fn in ALL]
    ok = all(results)
    if verbose:
        verdict = (color("ALL 4 PIPELINES PASS", "green") if ok
                   else color("SMOKE FAILURES", "red"))
        print(f"\n{verdict}  ({sum(results)}/{len(results)})")
        if ok:
            print("Tomorrow: put GEMINI_API_KEY in .env, pip install "
                  "'google-genai>=2.0.0', then `python3 -m agentgrid doctor`.")
    return ok
