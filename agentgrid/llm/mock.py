"""MockBackend — a deterministic, scripted 'LLM' for offline runs.

Only the intelligence is canned; every tool call it emits executes for
real (files are written, git worktrees branch and conflict, unittest
runs). That means smoke tests exercise the true pipeline end-to-end with
zero API keys.

The orchestrator embeds a machine-readable header in every prompt:
    [TASK-META] issue=ISSUE-1 sub=A round=2 mode=standard
The mock parses it and replays fixtures from demo/fixtures/<issue>/.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from ..config import FIXTURES_DIR
from ..errors import PipelineError
from ..util import new_id
from .base import LLMBackend, LLMTurn, ToolCall

_META_RE = re.compile(r"\[TASK-META\]([^\n]*)")


def _parse_meta(messages: list[dict]) -> dict:
    meta: dict = {}
    for msg in messages:
        if msg.get("role") != "user":
            continue
        for m in _META_RE.finditer(msg.get("content", "")):
            for pair in m.group(1).split():
                if "=" in pair:
                    k, _, v = pair.partition("=")
                    meta[k.strip()] = v.strip()
    return meta


def _walk_fixture_files(root: Path) -> list[tuple[str, str]]:
    files = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and not p.name.startswith("_"):
            files.append((str(p.relative_to(root)), p.read_text(encoding="utf-8")))
    return files


def _final_json(payload: dict, lead: str = "") -> LLMTurn:
    body = json.dumps(payload, indent=2)
    return LLMTurn(text=f"{lead}\n```json\n{body}\n```".strip())


class MockBackend(LLMBackend):
    name = "mock"

    def __init__(self, settings=None, fixtures_dir: Path | None = None) -> None:
        self.fixtures = Path(fixtures_dir or FIXTURES_DIR)
        self.delay = float(getattr(settings, "mock_delay", 0) or 0)

    # ------------------------------------------------------------------

    def chat(self, role: str, system: str, messages: list[dict],
             tools: list, conv_id: str | None = None) -> LLMTurn:
        if self.delay:
            time.sleep(self.delay)
        meta = _parse_meta(messages)
        turn_no = sum(1 for m in messages if m.get("role") == "assistant")
        handler = getattr(self, f"_{role}", None)
        if handler is None:
            raise PipelineError(f"MockBackend has no script for role {role!r}")
        return handler(meta, turn_no, messages)

    # ------------------------------------------------------------ roles

    def _fixture(self, meta: dict, *parts: str) -> Path:
        issue = meta.get("issue", "UNKNOWN")
        return self.fixtures / issue / Path(*parts)

    def _write_calls(self, root: Path) -> LLMTurn:
        calls = [ToolCall(id=new_id("call-"), name="write_file",
                          args={"path": rel, "content": content})
                 for rel, content in _walk_fixture_files(root)]
        if not calls:
            raise PipelineError(f"mock fixture dir empty or missing: {root}")
        return LLMTurn(text="Applying my changes now.", tool_calls=calls)

    def planner(self, meta, turn_no, messages):
        plan = json.loads(self._fixture(meta, "plan.json").read_text(encoding="utf-8"))
        return _final_json(plan, "Here is my decomposition of the issue.")

    _planner = planner

    def _coder(self, meta, turn_no, messages):
        rnd = meta.get("round", "1")
        root = self._fixture(meta, "code", meta.get("sub", "A"), f"round{rnd}")
        if turn_no == 0:
            return self._write_calls(root)
        summary_file = root / "_summary.txt"
        summary = (summary_file.read_text(encoding="utf-8").strip()
                   if summary_file.exists()
                   else f"Implemented {meta.get('sub')} (round {rnd}).")
        files = [rel for rel, _ in _walk_fixture_files(root)]
        return _final_json({"summary": summary, "files": files}, "Done.")

    def _reviewer(self, meta, turn_no, messages):
        cfg_path = self._fixture(meta, "review", f"{meta.get('sub', 'A')}.json")
        cfg = (json.loads(cfg_path.read_text(encoding="utf-8"))
               if cfg_path.exists() else {"reject_rounds": []})
        rnd = int(meta.get("round", "1"))
        if rnd in cfg.get("reject_rounds", []):
            return _final_json({"verdict": "changes_requested",
                                "critique": cfg.get("critique", "Needs work.")},
                               "I cannot approve this yet.")
        return _final_json({"verdict": "approve",
                            "critique": cfg.get("approval", "Clean, tested, approved.")},
                           "Reviewed.")

    def _integrator(self, meta, turn_no, messages):
        root = self._fixture(meta, "resolved")
        if turn_no == 0:
            return self._write_calls(root)
        return _final_json({"summary": "Merged both branches: kept the Decimal-exact "
                                       "money math AND the settlement summary feature."},
                           "Conflict resolved.")

    def _breaker(self, meta, turn_no, messages):
        rnd = meta.get("round", "1")
        root = self._fixture(meta, "breaker", f"round{rnd}")
        if not root.exists():
            return _final_json(
                {"action": "concede",
                 "rationale": "I attacked remainder handling and input validation; "
                              "both now hold. No further legitimate breakage found."},
                "I concede.")
        if turn_no == 0:
            return self._write_calls(root)
        note_file = root / "_rationale.txt"
        rationale = (note_file.read_text(encoding="utf-8").strip()
                     if note_file.exists() else "This test encodes a spec guarantee "
                                                "the current code violates.")
        return _final_json({"action": "attack", "rationale": rationale}, "New failing test planted.")

    def _verifier(self, meta, turn_no, messages):
        rnd = meta.get("round", "1")
        verdict_path = self._fixture(meta, "verify", f"round{rnd}.json")
        verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
        return _final_json(verdict, "Compared the rendered page against the mockup.")

    def _intake(self, meta, turn_no, messages):
        data = json.loads(self._fixture(meta, "transcript.json").read_text(encoding="utf-8"))
        return _final_json(data, "Transcribed and structured the voice report.")

    def _publisher(self, meta, turn_no, messages):
        pr_path = self._fixture(meta, "pr.md")
        if pr_path.exists():
            return LLMTurn(text=pr_path.read_text(encoding="utf-8"))
        return LLMTurn(text=f"# Fix {meta.get('issue')}\n\nAutomated change by AgentGrid.")
