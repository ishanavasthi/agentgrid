"""Managed Agents (Antigravity) backend via the Gemini Interactions API.

Per the Managed Agents quickstart:

    agent = client.agents.create(
        id="...", base_agent="antigravity-preview-05-2026",
        system_instruction="...")
    interaction = client.interactions.create(
        agent="...", input="...", environment="remote")
    # continuation: previous_interaction_id=interaction.id,
    #               environment=interaction.environment_id

Design: managed agents run in a REMOTE sandbox, so they carry the
*reasoning* roles (planner, reviewer, intake, verifier, publisher).
Roles that must touch the local repo (coder, integrator, breaker) need
client-side function calling → HybridBackend routes those to
GeminiBackend. That split — managed agents for judgment, function-calling
agents for hands-on-disk work — is the architecture story for judges.

NOTE: `client.agents`/`client.interactions` require google-genai >= 2.0,
which itself requires Python >= 3.10 (PyPI's requires_python metadata;
verified live 2026-07-11 on google-genai 2.11.0 under Python 3.12).
Under Python 3.9, pip silently resolves to the last 3.9-compatible
release (1.47.0), which lacks this surface entirely — `agentgrid doctor`
will show "managed agents surface" as absent with no further explanation
in that case. Run agentgrid from a Python >= 3.10 venv to get the real
surface; HybridBackend transparently falls back to pure Gemini
function-calling for every role if it's unavailable either way.
"""

from __future__ import annotations

from ..errors import BackendUnavailable, ConfigError
from .base import LLMBackend, LLMTurn, call_with_retry
from .gemini import GeminiBackend, _load_sdk


class ManagedAgentsBackend(LLMBackend):
    name = "managed"

    def __init__(self, settings) -> None:
        if not settings.api_key:
            raise ConfigError("GEMINI_API_KEY is not set")
        genai, _ = _load_sdk()
        self.client = genai.Client(api_key=settings.api_key)
        if not (hasattr(self.client, "agents") and hasattr(self.client, "interactions")):
            raise BackendUnavailable(
                "installed google-genai has no agents/interactions surface — "
                "HybridBackend falls back to pure Gemini function-calling for "
                "every role. This is almost always a Python version issue: "
                "google-genai >= 2.0 (required for this surface) needs Python "
                ">= 3.10, and pip silently installs the last 3.9-compatible "
                "release (1.47.0, no agents/interactions) on older Python. "
                "Run agentgrid from a Python >= 3.10 venv with "
                "`pip install -U google-genai`, then re-check with "
                "`python3 -m agentgrid doctor`.")
        self.base_agent = settings.base_agent
        self._agent_ids: dict[str, str] = {}
        # conv_id -> (previous_interaction_id, environment_id)
        self._conversations: dict[str, tuple[str, str | None]] = {}

    def _ensure_agent(self, role: str, system: str) -> str:
        if role in self._agent_ids:
            return self._agent_ids[role]
        agent_id = f"agentgrid-{role}"
        try:
            self.client.agents.create(
                id=agent_id, base_agent=self.base_agent, system_instruction=system)
        except Exception as exc:
            if "exist" not in str(exc).lower() and "409" not in str(exc):
                raise BackendUnavailable(f"agents.create failed: {exc}") from exc
            # Agent id already exists server-side from an earlier process —
            # client.agents has no update(), and reusing it as-is would
            # silently keep serving whatever system_instruction it was
            # FIRST created with, even after roster.py's prompt changes.
            # Recreate so the live agent always matches the code.
            try:
                self.client.agents.delete(id=agent_id)
                self.client.agents.create(
                    id=agent_id, base_agent=self.base_agent, system_instruction=system)
            except Exception as exc2:
                raise BackendUnavailable(f"agents recreate failed: {exc2}") from exc2
        self._agent_ids[role] = agent_id
        return agent_id

    def chat(self, role: str, system: str, messages: list[dict],
             tools: list, conv_id: str | None = None) -> LLMTurn:
        if tools:
            raise BackendUnavailable(
                f"role {role!r} needs local tools — route via HybridBackend")
        agent_id = self._ensure_agent(role, system)

        prior = self._conversations.get(conv_id) if conv_id else None
        if prior:
            # continuation: send only the newest user content
            new_input = next((m.get("content", "") for m in reversed(messages)
                              if m.get("role") == "user"), "")
            kwargs = {"agent": agent_id, "input": new_input,
                      "previous_interaction_id": prior[0]}
            if prior[1]:
                kwargs["environment"] = prior[1]
        else:
            transcript = "\n\n".join(
                f"[{m['role'].upper()}]\n{m.get('content', '')}" for m in messages)
            kwargs = {"agent": agent_id, "input": transcript, "environment": "remote"}

        interaction = call_with_retry(
            lambda: self.client.interactions.create(**kwargs),
            what=f"managed/{role}")
        if conv_id:
            self._conversations[conv_id] = (
                interaction.id, getattr(interaction, "environment_id", None))
        return LLMTurn(text=getattr(interaction, "output_text", "") or "")


class HybridBackend(LLMBackend):
    """Managed agents for reasoning roles; Gemini function-calling for
    roles that edit the local repository."""

    name = "managed+gemini"

    def __init__(self, settings) -> None:
        self.managed = ManagedAgentsBackend(settings)
        self.gemini = GeminiBackend(settings)

    def chat(self, role: str, system: str, messages: list[dict],
             tools: list, conv_id: str | None = None) -> LLMTurn:
        if tools:
            return self.gemini.chat(role, system, messages, tools, conv_id)
        try:
            return self.managed.chat(role, system, messages, tools, conv_id)
        except BackendUnavailable:
            return self.gemini.chat(role, system, messages, tools, conv_id)
