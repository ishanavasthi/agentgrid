"""The thin LLM backend interface — the pipeline's swappable brain socket.

Message format (provider-neutral):
  {"role": "user",      "content": str, "attachments": [path, ...]?}
  {"role": "assistant", "content": str, "tool_calls": [{"id","name","args"}]?}
  {"role": "tool",      "tool_call_id": str, "name": str, "content": str}

Backends: MockBackend (offline, deterministic), GeminiBackend (function
calling on gemini-3.5-flash), ManagedAgentsBackend (Antigravity managed
agents via the Interactions API), HybridBackend (managed for reasoning
roles, gemini for local-tool roles).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict


@dataclass
class LLMTurn:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)

    @property
    def is_final(self) -> bool:
        return not self.tool_calls


class LLMBackend:
    name = "base"

    def chat(self, role: str, system: str, messages: list[dict],
             tools: list, conv_id: str | None = None) -> LLMTurn:
        raise NotImplementedError

    def describe(self) -> str:
        return self.name
