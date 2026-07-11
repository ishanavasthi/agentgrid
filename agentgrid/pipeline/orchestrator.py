"""The Orchestrator: plans, delegates, and drives the multi-agent pipeline.

Modes
  standard    Planner → parallel Coders (git worktrees) → Reviewer loops →
              Integrator (merge-conflict resolution) → Tester → Publisher
  adversarial Breaker plants failing tests, Coder fixes, until concession
  visual      Coder implements a mockup, Verifier judges render, loop
  voice       Intake structures an audio bug report, then standard flow
"""

from __future__ import annotations

import os
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

from ..agents import Agent, ROLES
from ..bus import BUS
from ..config import ORIGIN_BARE, RUNS_DIR, TEMPLATE_DIR, settings as load_settings
from ..errors import PipelineError
from ..ledger import Ledger
from ..llm import get_backend
from ..tools import Toolbox, make_fs_tools, make_test_tool, run_unittests
from ..tools import gitops as g
from ..tools.github import publish_pr
from ..tools.screenshot import take_screenshot
from ..util import truncate
from .. import assets

_FRONT_RE = re.compile(r"<!--\s*agentgrid\s*(.*?)-->", re.DOTALL)


def parse_frontmatter(text: str) -> dict:
    match = _FRONT_RE.search(text)
    front = {}
    if match:
        for line in match.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                front[k.strip()] = v.strip()
    return front


def file_listing(repo: Path, cap: int = 120) -> str:
    out = []
    for p in sorted(repo.rglob("*")):
        if ".git" in p.parts or "__pycache__" in p.parts:
            continue
        if p.is_file():
            out.append(str(p.relative_to(repo)))
        if len(out) >= cap:
            out.append("...")
            break
    return "\n".join(out)


class Orchestrator:
    def __init__(self, backend_name: str | None = None, bus=BUS) -> None:
        self.settings = load_settings()
        self.backend_name = backend_name or self.settings.backend_pref
        self.bus = bus
        self.backend = None
        self.ledger: Ledger | None = None

    # ================================================== demo environment

    def setup_demo(self, force: bool = False) -> dict:
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        if ORIGIN_BARE.exists():
            if not force:
                return {"origin": str(ORIGIN_BARE), "created": False}
            shutil.rmtree(ORIGIN_BARE)
        work = RUNS_DIR / "template-work"
        if work.exists():
            shutil.rmtree(work)
        shutil.copytree(TEMPLATE_DIR, work)
        assets.make_mockup_png(work / "issues" / "ISSUE-3.mockup.png")
        assets.make_demo_wav(work / "issues" / "ISSUE-4.wav")
        g.init_repo(work)
        g.commit_all(work, "chore: SplitSathi baseline (seeded by AgentGrid setup-demo)")
        baseline = run_unittests(work)
        if not baseline["passed"]:
            raise PipelineError(
                f"target template baseline tests FAIL — fix the template first:\n"
                f"{baseline['output']}")
        g.clone_bare(work, ORIGIN_BARE)
        shutil.rmtree(work)
        return {"origin": str(ORIGIN_BARE), "created": True,
                "baseline": baseline["summary"]}

    # ============================================================ entry

    def run_issue(self, issue_id: str, mode: str = "auto",
                  reset_bus: bool = True) -> dict:
        if not ORIGIN_BARE.exists():
            self.setup_demo()
        self.backend, note = get_backend(self.backend_name, self.settings)

        run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + issue_id.lower()
        run_dir = RUNS_DIR / run_id
        run_dir.mkdir(parents=True)
        repo = run_dir / "repo"
        g.clone(ORIGIN_BARE, repo)

        issue_path = repo / "issues" / f"{issue_id}.md"
        if not issue_path.exists():
            raise PipelineError(f"no such issue: {issue_id} "
                                f"(expected {issue_path})")
        issue_text = issue_path.read_text(encoding="utf-8")
        front = parse_frontmatter(issue_text)
        resolved_mode = mode if mode not in ("", "auto") else front.get("mode", "standard")

        self.ledger = Ledger(run_dir, self.bus)
        self.ledger.meta = {"run_id": run_id, "issue": issue_id,
                            "mode": resolved_mode, "backend": self.backend.name}
        if reset_bus:
            self.bus.reset()
        self.bus.publish("run_started", run_id=run_id, issue=issue_id,
                         mode=resolved_mode, backend=self.backend.name,
                         backend_note=note)

        ctx = SimpleNamespace(issue_id=issue_id, issue_text=issue_text,
                              front=front, run_dir=run_dir, repo=repo,
                              mode=resolved_mode)
        ctx.root = self.ledger.new_task(f"{issue_id}: resolve end-to-end",
                                        "issue", owner="Orchestrator",
                                        detail=truncate(issue_text, 1200))
        try:
            runner = {"standard": self._run_standard,
                      "adversarial": self._run_adversarial,
                      "visual": self._run_visual,
                      "voice": self._run_voice}.get(resolved_mode)
            if runner is None:
                raise PipelineError(f"unknown mode {resolved_mode!r}")
            summary = runner(ctx)
        except Exception as exc:
            self.ledger.update(ctx.root.id, status="failed", note=str(exc))
            self.bus.publish("error", message=f"{type(exc).__name__}: {exc}")
            self.bus.publish("run_finished", ok=False, run_id=run_id,
                             error=str(exc))
            self.ledger.save()
            raise
        summary.update({"run_id": run_id, "issue": issue_id,
                        "mode": resolved_mode, "run_dir": str(run_dir),
                        "backend": self.backend.name})
        self.ledger.update(ctx.root.id, status="done")
        self.bus.publish("run_finished", ok=True, **{
            k: v for k, v in summary.items() if k != "run_dir"})
        self.ledger.save()
        return summary

    # ========================================================== helpers

    def _phase(self, name: str) -> None:
        self.bus.publish("phase", name=name)

    def _meta(self, **kv) -> str:
        pairs = " ".join(f"{k}={v}" for k, v in kv.items() if v is not None)
        return f"[TASK-META] {pairs}"

    def _agent(self, role_name: str, root: Path | None = None) -> Agent:
        role = ROLES[role_name]
        toolbox = None
        if role.tool_names and root is not None:
            specs = [s for s in make_fs_tools(root) if s.name in role.tool_names]
            if "run_tests" in role.tool_names:
                specs.append(make_test_tool(root))
            toolbox = Toolbox(specs)
        return Agent(role, self.backend, self.ledger, self.bus, toolbox)

    def _embed_files(self, root: Path, paths: list[str], limit: int = 3500) -> str:
        chunks = []
        for rel in paths or []:
            p = root / rel
            if p.exists() and p.is_file():
                chunks.append(f"--- {rel} ---\n{truncate(p.read_text(encoding='utf-8'), limit)}")
        return "\n\n".join(chunks)

    def _ledger_digest(self) -> str:
        snap = self.ledger.snapshot()
        lines = [f"- [{t['status']}] ({t['owner']}) {t['title']}"
                 for t in snap["tasks"]]
        lines.append(f"handoffs recorded: {len(snap['handoffs'])}")
        return "\n".join(lines)

    def _interactive_visual_verify(self, ctx, repo: Path, page: str,
                                   mockup: Path) -> dict | None:
        """Try the Computer Use interactive Verifier. Returns a result
        dict on success, or None if this path isn't usable right now
        (mock backend, no key, disabled via AGENTGRID_CU_DISABLE, missing
        playwright/SDK, model/API error, safety stop) — callers must fall
        back to the static-screenshot Verifier in that case. Never raises."""
        disabled = os.environ.get("AGENTGRID_CU_DISABLE", "").strip().lower() in (
            "1", "true", "yes")
        if disabled or self.backend.name == "mock" or not self.settings.has_key:
            return None
        try:
            from ..llm.computer_use import run_interactive_verify
            task_prompt = (
                f"ISSUE:\n{truncate(ctx.issue_text, 1200)}\n\n"
                "The browser you are controlling is already open on the "
                "live implementation of this page. Interact with it "
                "(click, scroll) as needed to check its content and "
                "behavior match the mockup and the issue's acceptance "
                "criteria, then report your verdict.")
            result = run_interactive_verify(
                self.settings, repo / page, task_prompt,
                reference_image=mockup if mockup.exists() else None)
            self.bus.publish(
                "agent_message", agent="Verifier",
                content=f"[computer_use] {result['steps']} action(s) taken — "
                        + "; ".join(f"{e['action']}({e.get('intent', '')[:40]})"
                                    for e in result["transcript"][:4]))
            return result
        except Exception as exc:
            self.bus.publish(
                "agent_message", agent="Verifier",
                content=f"[computer_use] unavailable this round, falling back "
                        f"to static screenshot: {type(exc).__name__}: {exc}")
            return None

    # ================================================== standard mode

    def _run_standard(self, ctx) -> dict:
        summary = self._standard_core(ctx, ctx.issue_text)
        return summary

    def _standard_core(self, ctx, issue_text: str) -> dict:
        issue_id, repo, run_dir = ctx.issue_id, ctx.repo, ctx.run_dir

        # ---- plan
        self._phase("Planning")
        plan_task = self.ledger.new_task("Decompose issue into parallel subtasks",
                                         "plan", owner="Planner", parent=ctx.root.id)
        self.ledger.handoff("Orchestrator", "Planner", plan_task.id,
                            self.ledger.packet_for(plan_task.id,
                                                   issue=truncate(issue_text, 2000)))
        self.ledger.update(plan_task.id, status="in_progress")
        planner = self._agent("planner")
        res = planner.run(
            f"{self._meta(issue=issue_id, mode=ctx.mode)}\n\n"
            f"ISSUE REPORT:\n{issue_text}\n\n"
            f"REPOSITORY FILES:\n{file_listing(repo)}",
            task_id=plan_task.id)
        subs = ((res.data or {}).get("subtasks") or [])[:3]
        if not subs:
            raise PipelineError("Planner produced no subtasks")
        self.ledger.update(plan_task.id, status="done", plan=subs)

        # ---- parallel implementation in worktrees
        self._phase("Parallel implementation")
        jobs = []
        for sub in subs:
            branch = f"agent/{issue_id.lower()}-{str(sub['id']).lower()}"
            wt = run_dir / f"wt-{sub['id']}"
            g.add_worktree(repo, wt, branch)
            jobs.append((sub, branch, wt))
        try:
            if len(jobs) > 1:
                with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
                    results = list(pool.map(
                        lambda j: self._implement_subtask(ctx, issue_text, *j), jobs))
            else:
                results = [self._implement_subtask(ctx, issue_text, *jobs[0])]
        finally:
            for _, _, wt in jobs:
                g.remove_worktree(repo, wt)
        rejections = sum(r["rejections"] for r in results)

        # ---- integrate
        self._phase("Integration")
        integration_branch = f"integration/{issue_id.lower()}"
        g.checkout_new(repo, integration_branch, "main")
        conflicts_resolved = 0
        for r in results:
            clean, conflicted = g.merge(repo, r["branch"],
                                        f"merge {r['branch']} into {integration_branch}")
            if clean:
                continue
            self.bus.publish("merge_conflict", branch=r["branch"],
                             files=conflicted)
            integ_task = self.ledger.new_task(
                f"Resolve merge conflict in {', '.join(conflicted)}",
                "integrate", owner="Integrator", parent=ctx.root.id)
            self.ledger.handoff("Orchestrator", "Integrator", integ_task.id,
                                self.ledger.packet_for(integ_task.id,
                                                       files=conflicted))
            self.ledger.update(integ_task.id, status="in_progress")
            intents = "\n".join(f"- Subtask {s['id']}: {s['title']} — {s['acceptance']}"
                                for s in subs)
            integrator = self._agent("integrator", root=repo)
            integrator.run(
                f"{self._meta(issue=issue_id, sub='MERGE', mode=ctx.mode)}\n\n"
                f"Both branches are approved; git conflict on merging "
                f"`{r['branch']}` into `{integration_branch}`.\n\n"
                f"SUBTASK INTENTS (preserve ALL of them):\n{intents}\n\n"
                f"CONFLICTED FILES WITH MARKERS:\n"
                f"{self._embed_files(repo, conflicted, 6000)}",
                task_id=integ_task.id)
            g.conclude_merge(repo, f"merge: resolve conflicts in {', '.join(conflicted)}")
            self.ledger.update(integ_task.id, status="done")
            conflicts_resolved += len(conflicted)

        # ---- verify
        self._phase("Verification")
        test_info = self._test_and_repair(ctx, repo)

        # ---- publish
        self._phase("Publish")
        pr = self._publish(ctx, repo, integration_branch,
                           facts=(f"review rejections handled: {rejections}; "
                                  f"conflicted files resolved: {conflicts_resolved}; "
                                  f"tests: {test_info['summary']}"))
        return {"tests_passed": test_info["passed"],
                "review_rejections": rejections,
                "conflicts_resolved": conflicts_resolved,
                "repairs": test_info["repairs"],
                "subtasks": len(subs), "pr": pr,
                "branch": integration_branch}

    def _implement_subtask(self, ctx, issue_text: str, sub: dict,
                           branch: str, wt: Path) -> dict:
        sub_id = str(sub["id"])
        sub_task = self.ledger.new_task(f"[{sub_id}] {sub['title']}", "code",
                                        owner="Coder", parent=ctx.root.id,
                                        acceptance=sub.get("acceptance", ""))
        critique = ""
        rejections = 0
        for rnd in range(1, 4):
            self.ledger.handoff("Planner" if rnd == 1 else "Reviewer", "Coder",
                                sub_task.id,
                                self.ledger.packet_for(sub_task.id, round=rnd,
                                                       critique=critique))
            self.ledger.update(sub_task.id, status="in_progress",
                               note=f"coding round {rnd}")
            coder = self._agent("coder", root=wt)
            prompt = (
                f"{self._meta(issue=ctx.issue_id, sub=sub_id, round=rnd, mode=ctx.mode)}\n\n"
                f"ISSUE (context):\n{truncate(issue_text, 1500)}\n\n"
                f"YOUR SUBTASK [{sub_id}]: {sub['title']}\n"
                f"ACCEPTANCE CRITERIA: {sub.get('acceptance', '')}\n"
                f"LIKELY FILES: {', '.join(sub.get('files_hint', []))}\n\n"
                f"CURRENT CONTENT OF LIKELY FILES:\n"
                f"{self._embed_files(wt, sub.get('files_hint', []))}")
            if critique:
                prompt += (f"\n\nREVISION REQUIRED — the Reviewer rejected round "
                           f"{rnd - 1} with this critique. Address every point:\n{critique}")
            coder.run(prompt, task_id=sub_task.id)
            g.commit_all(wt, f"[{sub_id}] {sub['title']} (round {rnd})")

            review_task = self.ledger.new_task(f"Review [{sub_id}] round {rnd}",
                                               "review", owner="Reviewer",
                                               parent=sub_task.id)
            diff_text = g.diff(ctx.repo, "main", branch)
            self.ledger.handoff("Coder", "Reviewer", review_task.id,
                                self.ledger.packet_for(review_task.id,
                                                       sub=sub_id, round=rnd))
            self.ledger.update(review_task.id, status="in_progress")
            reviewer = self._agent("reviewer")
            rev = reviewer.run(
                f"{self._meta(issue=ctx.issue_id, sub=sub_id, round=rnd, mode=ctx.mode)}\n\n"
                f"SUBTASK: {sub['title']}\nACCEPTANCE: {sub.get('acceptance', '')}\n\n"
                f"UNIFIED DIFF (main..{branch}):\n{truncate(diff_text, 9000)}",
                task_id=review_task.id)
            verdict = ((rev.data or {}).get("verdict") or "approve").lower()
            critique = (rev.data or {}).get("critique", "")
            self.bus.publish("review_verdict", sub=sub_id, round=rnd,
                             verdict=verdict, critique=truncate(critique, 500))
            if verdict == "approve":
                self.ledger.update(review_task.id, status="done", note="approved")
                self.ledger.update(sub_task.id, status="done")
                return {"branch": branch, "sub": sub_id,
                        "rejections": rejections, "approved": True}
            rejections += 1
            self.ledger.update(review_task.id, status="rejected", note=critique)
        raise PipelineError(f"subtask {sub_id} still rejected after 3 rounds")

    # ================================================ adversarial mode

    def _run_adversarial(self, ctx) -> dict:
        issue_id, repo = ctx.issue_id, ctx.repo
        target_files = [f.strip() for f in ctx.front.get("files", "").split(",") if f.strip()]
        branch = f"fix/{issue_id.lower()}"
        g.checkout_new(repo, branch, "main")

        self._phase("Adversarial TDD")
        attacks = 0
        conceded = False
        for rnd in range(1, 5):
            break_task = self.ledger.new_task(f"Attack round {rnd}", "break",
                                              owner="Breaker", parent=ctx.root.id)
            self.ledger.handoff("Orchestrator", "Breaker", break_task.id,
                                self.ledger.packet_for(break_task.id, round=rnd))
            self.ledger.update(break_task.id, status="in_progress")
            breaker = self._agent("breaker", root=repo)
            res = breaker.run(
                f"{self._meta(issue=issue_id, sub='BREAK', round=rnd, mode=ctx.mode)}\n\n"
                f"ISSUE UNDER TEST:\n{truncate(ctx.issue_text, 1500)}\n\n"
                f"CODE UNDER ATTACK:\n{self._embed_files(repo, target_files)}",
                task_id=break_task.id)
            action = ((res.data or {}).get("action") or "concede").lower()
            self.bus.publish("breaker_result", round=rnd, action=action,
                             rationale=truncate((res.data or {}).get("rationale", ""), 400))
            if action == "concede":
                conceded = True
                self.ledger.update(break_task.id, status="done", note="conceded")
                break
            g.commit_all(repo, f"breaker: attack round {rnd}")
            red = run_unittests(repo)
            self.bus.publish("test_result", passed=red["passed"],
                             summary=red["summary"], context=f"attack round {rnd}")
            if red["passed"]:
                self.ledger.update(break_task.id, status="failed",
                                   note="attack test unexpectedly passed")
                conceded = True
                break
            attacks += 1
            self.ledger.update(break_task.id, status="done", note="code broken — red")

            fix_task = self.ledger.new_task(f"Fix breakage round {rnd}", "code",
                                            owner="Coder", parent=ctx.root.id)
            self.ledger.handoff("Breaker", "Coder", fix_task.id,
                                self.ledger.packet_for(fix_task.id, round=rnd))
            self.ledger.update(fix_task.id, status="in_progress")
            coder = self._agent("coder", root=repo)
            coder.run(
                f"{self._meta(issue=issue_id, sub='FIX', round=rnd, mode=ctx.mode)}\n\n"
                f"The Breaker planted a legitimate failing test. Make the whole "
                f"suite pass WITHOUT weakening or deleting any test.\n\n"
                f"FAILING TEST OUTPUT:\n{truncate(red['output'], 4000)}\n\n"
                f"CODE UNDER ATTACK:\n{self._embed_files(repo, target_files)}",
                task_id=fix_task.id)
            g.commit_all(repo, f"fix: survive breaker round {rnd}")
            green = run_unittests(repo)
            self.bus.publish("test_result", passed=green["passed"],
                             summary=green["summary"], context=f"after fix round {rnd}")
            if not green["passed"]:
                raise PipelineError(f"coder could not restore green in round {rnd}:\n"
                                    f"{green['output']}")
            self.ledger.update(fix_task.id, status="done")

        self._phase("Verification")
        final = run_unittests(repo)
        self.bus.publish("test_result", passed=final["passed"],
                         summary=final["summary"], context="final")

        self._phase("Publish")
        pr = self._publish(ctx, repo, branch,
                           facts=(f"breaker attack rounds survived: {attacks}; "
                                  f"breaker conceded: {conceded}; tests: {final['summary']}"))
        return {"tests_passed": final["passed"], "breaker_rounds": attacks,
                "conceded": conceded, "pr": pr, "branch": branch}

    # ===================================================== visual mode

    def _run_visual(self, ctx) -> dict:
        issue_id, repo, run_dir = ctx.issue_id, ctx.repo, ctx.run_dir
        page = ctx.front.get("page", "web/index.html")
        mockup = repo / ctx.front.get("mockup", f"issues/{issue_id}.mockup.png")
        branch = f"ui/{issue_id.lower()}"
        g.checkout_new(repo, branch, "main")

        self._phase("Implement & visually verify")
        critique = ""
        matched = False
        rounds = 0
        for rnd in range(1, 4):
            rounds = rnd
            ui_task = self.ledger.new_task(f"Implement mockup (round {rnd})", "code",
                                           owner="Coder", parent=ctx.root.id)
            self.ledger.handoff("Orchestrator" if rnd == 1 else "Verifier", "Coder",
                                ui_task.id,
                                self.ledger.packet_for(ui_task.id, round=rnd,
                                                       critique=critique))
            self.ledger.update(ui_task.id, status="in_progress")
            coder = self._agent("coder", root=repo)
            prompt = (
                f"{self._meta(issue=issue_id, sub='UI', round=rnd, mode=ctx.mode)}\n\n"
                f"ISSUE:\n{truncate(ctx.issue_text, 1500)}\n\n"
                f"Implement the attached design mockup in `{page}` "
                f"(self-contained HTML+CSS, no external assets).\n\n"
                f"CURRENT PAGE:\n{self._embed_files(repo, [page])}")
            if critique:
                prompt += f"\n\nVERIFIER FOUND THESE MISMATCHES — fix all:\n{critique}"
            coder.run(prompt, task_id=ui_task.id,
                      attachments=[mockup] if mockup.exists() else None)
            g.commit_all(repo, f"ui: mockup implementation round {rnd}")
            self.ledger.update(ui_task.id, status="done")

            verify_task = self.ledger.new_task(f"Visual verify (round {rnd})",
                                               "verify", owner="Verifier",
                                               parent=ctx.root.id)
            self.ledger.handoff("Coder", "Verifier", verify_task.id,
                                self.ledger.packet_for(verify_task.id, round=rnd))
            self.ledger.update(verify_task.id, status="in_progress")

            interactive = self._interactive_visual_verify(ctx, repo, page, mockup)
            if interactive is not None:
                verdict, issues = interactive["verdict"], interactive["issues"]
            else:
                shot = run_dir / f"shot-round{rnd}.png"
                ok, note = take_screenshot(repo / page, shot)
                attachments = [shot, mockup] if (ok and mockup.exists()) else (
                    [mockup] if mockup.exists() else None)
                vprompt = (
                    f"{self._meta(issue=issue_id, sub='UI', round=rnd, mode=ctx.mode)}\n\n"
                    f"Mockup attached. Rendering note: {note}\n")
                if not ok:
                    vprompt += (f"\nPAGE HTML SOURCE (fallback for screenshot):\n"
                                f"{self._embed_files(repo, [page], 6000)}")
                verifier = self._agent("verifier")
                ver = verifier.run(vprompt, task_id=verify_task.id,
                                   attachments=attachments)
                verdict = ((ver.data or {}).get("verdict") or "mismatch").lower()
                issues = (ver.data or {}).get("issues", [])
            self.bus.publish("verify_verdict", round=rnd, verdict=verdict,
                             issues=issues,
                             method="computer_use" if interactive else "screenshot")
            if verdict == "match":
                matched = True
                self.ledger.update(verify_task.id, status="done", note="match")
                break
            critique = "\n".join(f"- {i}" for i in issues)
            self.ledger.update(verify_task.id, status="rejected",
                               note=critique or "mismatch")

        self._phase("Verification")
        final = run_unittests(repo)
        self.bus.publish("test_result", passed=final["passed"],
                         summary=final["summary"], context="final")

        self._phase("Publish")
        pr = self._publish(ctx, repo, branch,
                           facts=(f"visual verification rounds: {rounds}; "
                                  f"matched mockup: {matched}; tests: {final['summary']}"))
        return {"tests_passed": final["passed"], "verify_rounds": rounds,
                "matched": matched, "pr": pr, "branch": branch}

    # ====================================================== voice mode

    def _run_voice(self, ctx) -> dict:
        issue_id, repo = ctx.issue_id, ctx.repo
        audio_rel = ctx.front.get("audio", f"issues/{issue_id}.wav")
        audio = repo / audio_rel

        self._phase("Voice intake")
        intake_task = self.ledger.new_task("Transcribe & structure voice report",
                                           "intake", owner="Intake",
                                           parent=ctx.root.id)
        self.ledger.handoff("Orchestrator", "Intake", intake_task.id,
                            self.ledger.packet_for(intake_task.id, audio=audio_rel))
        self.ledger.update(intake_task.id, status="in_progress")
        intake = self._agent("intake")
        res = intake.run(
            f"{self._meta(issue=issue_id, mode=ctx.mode)}\n\n"
            f"A voice recording of a bug report is attached "
            f"(file: {audio_rel}). Structure it into an actionable issue.\n\n"
            f"REPOSITORY FILES:\n{file_listing(repo)}",
            task_id=intake_task.id,
            attachments=[audio] if audio.exists() else None)
        data = res.data or {}
        if not data.get("title"):
            raise PipelineError("Intake produced no structured issue")
        self.bus.publish("intake_result",
                         title=data.get("title", ""),
                         detected_language=data.get("detected_language", ""),
                         confidence=data.get("confidence", 0))
        self.ledger.update(intake_task.id, status="done", structured=data)

        structured_issue = (
            f"# {data['title']}\n\n{data.get('body', '')}\n\n"
            f"Likely files: {', '.join(data.get('files_hint', []))}\n"
            f"(voice report — detected language: "
            f"{data.get('detected_language', 'unknown')})")
        summary = self._standard_core(ctx, structured_issue)
        summary.update({"intake_title": data.get("title", ""),
                        "detected_language": data.get("detected_language", "")})
        return summary

    # ========================================================= common

    def _test_and_repair(self, ctx, repo: Path, max_repairs: int = 2) -> dict:
        test_task = self.ledger.new_task("Run full test suite", "test",
                                         owner="Tester", parent=ctx.root.id)
        self.ledger.update(test_task.id, status="in_progress")
        result = run_unittests(repo)
        self.bus.publish("test_result", passed=result["passed"],
                         summary=result["summary"], context="integration")
        repairs = 0
        while not result["passed"] and repairs < max_repairs:
            repairs += 1
            fix_task = self.ledger.new_task(f"Repair failing suite (attempt {repairs})",
                                            "code", owner="Coder", parent=test_task.id)
            self.ledger.handoff("Tester", "Coder", fix_task.id,
                                self.ledger.packet_for(fix_task.id, attempt=repairs))
            coder = self._agent("coder", root=repo)
            coder.run(
                f"{self._meta(issue=ctx.issue_id, sub='REPAIR', round=repairs, mode=ctx.mode)}\n\n"
                f"The integrated branch fails its test suite. Repair the code "
                f"(never weaken tests).\n\nFAILING OUTPUT:\n"
                f"{truncate(result['output'], 5000)}",
                task_id=fix_task.id)
            g.commit_all(repo, f"repair: attempt {repairs}")
            result = run_unittests(repo)
            self.bus.publish("test_result", passed=result["passed"],
                             summary=result["summary"],
                             context=f"repair attempt {repairs}")
            self.ledger.update(fix_task.id,
                               status="done" if result["passed"] else "failed")
        self.ledger.update(test_task.id,
                           status="done" if result["passed"] else "failed",
                           note=result["summary"])
        return {"passed": result["passed"], "summary": result["summary"],
                "repairs": repairs}

    def _publish(self, ctx, repo: Path, branch: str, facts: str) -> dict:
        pub_task = self.ledger.new_task("Publish pull request", "publish",
                                        owner="Publisher", parent=ctx.root.id)
        self.ledger.handoff("Orchestrator", "Publisher", pub_task.id,
                            self.ledger.packet_for(pub_task.id))
        self.ledger.update(pub_task.id, status="in_progress")
        publisher = self._agent("publisher")
        res = publisher.run(
            f"{self._meta(issue=ctx.issue_id, mode=ctx.mode)}\n\n"
            f"RUN FACTS: {facts}\n\nTASK LEDGER:\n{self._ledger_digest()}",
            task_id=pub_task.id)
        body = res.text.strip()
        title = f"AgentGrid: {ctx.issue_id}"
        lines = body.splitlines()
        if lines and lines[0].startswith("# "):
            title = lines[0][2:].strip()
            body = "\n".join(lines[1:]).strip()
        pr = publish_pr(repo, branch, title, body, ctx.run_dir,
                        self.settings.github_repo)
        pr["title"] = title
        self.bus.publish("pr_created", **{k: v for k, v in pr.items()})
        self.ledger.update(pub_task.id, status="done", pr=pr)
        return pr
