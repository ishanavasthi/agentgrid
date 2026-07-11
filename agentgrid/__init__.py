"""AgentGrid — an autonomous multi-agent coding pipeline on the Gemini API.

Agents (Planner, Coders, Reviewer, Integrator, Breaker, Verifier, Intake,
Publisher) collaborate through a structured task ledger to take an issue
from report to merged, tested, PR-ready code — including parallel coding
in git worktrees, adversarial review, merge-conflict resolution, visual
verification against a mockup, and voice-issue intake.

Every LLM call goes through a thin backend interface, so the whole
pipeline runs deterministically offline (MockBackend) and switches to
Gemini 3.5 Flash / Managed Agents by setting GEMINI_API_KEY.
"""

__version__ = "0.1.0"
