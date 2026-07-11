"""Backend factory: mock | gemini | managed(hybrid) | auto."""

from __future__ import annotations

from ..errors import BackendUnavailable, ConfigError
from .base import LLMBackend, LLMTurn, ToolCall
from .mock import MockBackend

__all__ = ["LLMBackend", "LLMTurn", "ToolCall", "MockBackend", "get_backend"]


def get_backend(name: str, settings) -> tuple[LLMBackend, str]:
    """Returns (backend, banner_note)."""
    name = (name or settings.backend_pref or "auto").lower()

    if name == "mock":
        return MockBackend(settings), "MOCK backend — deterministic offline fixtures"

    if name == "gemini":
        from .gemini import GeminiBackend
        return GeminiBackend(settings), f"Gemini function-calling on {settings.model}"

    if name == "managed":
        from .managed import HybridBackend
        return (HybridBackend(settings),
                f"Managed Agents ({settings.base_agent}) + {settings.model} for tool roles")

    if name == "auto":
        if not settings.has_key:
            return (MockBackend(settings),
                    "MOCK backend (no GEMINI_API_KEY found) — plug the key in .env "
                    "to go live")
        try:
            from .managed import HybridBackend
            return (HybridBackend(settings),
                    f"Managed Agents ({settings.base_agent}) + {settings.model}")
        except (BackendUnavailable, ConfigError):
            from .gemini import GeminiBackend
            return (GeminiBackend(settings),
                    f"Gemini function-calling on {settings.model} "
                    "(managed agents surface unavailable)")

    raise ConfigError(f"unknown backend {name!r} (use mock|gemini|managed|auto)")
