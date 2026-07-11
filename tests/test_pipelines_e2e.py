"""End-to-end pipeline tests on the mock backend (no API key needed).

These wrap the same checkers as `python3 -m agentgrid smoke`, so
`python3 -m unittest discover -s tests` covers everything too.
"""

import os
import unittest

from agentgrid import smoke
from agentgrid.pipeline import Orchestrator


class TestPipelinesEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["AGENTGRID_MOCK_DELAY"] = "0"
        cls.orch = Orchestrator(backend_name="mock")
        cls.orch.setup_demo(force=True)

    def test_1_standard_parallel_review_conflict(self):
        self.assertTrue(smoke.smoke_standard(self.orch, verbose=False))

    def test_2_adversarial_breaker_fixer(self):
        self.assertTrue(smoke.smoke_adversarial(self.orch, verbose=False))

    def test_3_visual_verify_loop(self):
        self.assertTrue(smoke.smoke_visual(self.orch, verbose=False))

    def test_4_voice_intake(self):
        self.assertTrue(smoke.smoke_voice(self.orch, verbose=False))


if __name__ == "__main__":
    unittest.main()
