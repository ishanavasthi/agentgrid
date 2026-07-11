"""Unit tests for AgentGrid's own plumbing (stdlib only, no API key)."""

import tempfile
import unittest
from pathlib import Path

from agentgrid.bus import EventBus
from agentgrid.errors import ToolError
from agentgrid.ledger import Ledger
from agentgrid.tools import gitops as g
from agentgrid.tools.fs import make_fs_tools, safe_path
from agentgrid.util import extract_json


class TestExtractJson(unittest.TestCase):
    def test_fenced_block(self):
        text = 'Sure!\n```json\n{"verdict": "approve"}\n```\ndone'
        self.assertEqual(extract_json(text), {"verdict": "approve"})

    def test_bare_object(self):
        self.assertEqual(extract_json('noise {"a": [1, 2]} trailing'),
                         {"a": [1, 2]})

    def test_nested_and_strings_with_braces(self):
        text = '{"msg": "keep } this", "inner": {"n": 1}}'
        self.assertEqual(extract_json(text),
                         {"msg": "keep } this", "inner": {"n": 1}})

    def test_no_json(self):
        self.assertIsNone(extract_json("plain prose only"))


class TestFsGuard(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)

    def tearDown(self):
        self.dir.cleanup()

    def test_escape_rejected(self):
        with self.assertRaises(ToolError):
            safe_path(self.root, "../outside.txt")
        with self.assertRaises(ToolError):
            safe_path(self.root, "a/../../outside.txt")

    def test_write_then_read(self):
        tools = {t.name: t for t in make_fs_tools(self.root)}
        tools["write_file"].fn(path="pkg/mod.py", content="x = 1\n")
        self.assertEqual(tools["read_file"].fn(path="pkg/mod.py"), "x = 1\n")
        self.assertIn("pkg/mod.py", tools["list_files"].fn())


class TestLedgerAndBus(unittest.TestCase):
    def test_task_lifecycle_events_and_persistence(self):
        bus = EventBus()
        events = bus.subscribe(replay=False)
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Ledger(Path(tmp), bus)
            task = ledger.new_task("Fix bug", "code", owner="Coder")
            ledger.handoff("Orchestrator", "Coder", task.id, {"k": "v"})
            ledger.update(task.id, status="done", note="finished")
            snap = ledger.snapshot()
            self.assertEqual(snap["tasks"][0]["status"], "done")
            self.assertEqual(len(snap["handoffs"]), 1)
            self.assertTrue((Path(tmp) / "ledger.json").exists())
        types = [events.get_nowait()["type"] for _ in range(3)]
        self.assertEqual(types, ["task_created", "handoff", "task_updated"])

    def test_bus_replay(self):
        bus = EventBus()
        bus.publish("phase", name="one")
        q = bus.subscribe(replay=True)
        self.assertEqual(q.get_nowait()["name"], "one")


class TestGitOps(unittest.TestCase):
    def test_worktree_branches_and_merge_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            (repo / "shared.txt").write_text("base\n")
            g.init_repo(repo)
            g.commit_all(repo, "base")

            wt_a, wt_b = Path(tmp) / "wa", Path(tmp) / "wb"
            g.add_worktree(repo, wt_a, "side-a")
            g.add_worktree(repo, wt_b, "side-b")
            (wt_a / "shared.txt").write_text("version A\n")
            g.commit_all(wt_a, "A")
            (wt_b / "shared.txt").write_text("version B\n")
            g.commit_all(wt_b, "B")
            g.remove_worktree(repo, wt_a)
            g.remove_worktree(repo, wt_b)

            g.checkout_new(repo, "integration", "main")
            clean, conflicts = g.merge(repo, "side-a")
            self.assertTrue(clean)
            clean, conflicts = g.merge(repo, "side-b")
            self.assertFalse(clean)
            self.assertEqual(conflicts, ["shared.txt"])
            content = (repo / "shared.txt").read_text()
            self.assertIn("<<<<<<<", content)
            (repo / "shared.txt").write_text("version A+B\n")
            g.conclude_merge(repo, "resolved")
            self.assertIn("resolved", g.log_oneline(repo))


if __name__ == "__main__":
    unittest.main()
