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

import os
import sys
import time
from dataclasses import dataclass, field

_RETRYABLE_MARKERS = ("429", "RESOURCE_EXHAUSTED", "rate limit", "quota",
                      "503", "UNAVAILABLE", "overloaded", "Deadline")


def call_with_retry(fn, what: str = "LLM call"):
    """Run fn(), retrying on rate-limit/transient errors with backoff.

    Free-tier and shared hackathon keys throttle hard; the pipeline should
    slow down, not die. Tune via AGENTGRID_RETRY_ATTEMPTS (default 5) and
    AGENTGRID_RETRY_BASE seconds (default 4).
    """
    attempts = int(os.environ.get("AGENTGRID_RETRY_ATTEMPTS", "5") or 5)
    base = float(os.environ.get("AGENTGRID_RETRY_BASE", "4") or 4)
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:
            text = f"{type(exc).__name__}: {exc}"
            retryable = any(marker in text for marker in _RETRYABLE_MARKERS)
            if i >= attempts - 1 or not retryable:
                raise
            delay = base * (2 ** i)
            print(f"  ⏳ {what} throttled ({text[:120]}) — retry {i + 1}/"
                  f"{attempts - 1} in {delay:.0f}s", file=sys.stderr)
            time.sleep(delay)


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
