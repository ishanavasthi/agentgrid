"""GeminiBackend — real function-calling agents on gemini-3.5-flash.

Uses google-genai (>= 2.0.0). Lazy imports keep the offline/mock path
free of the dependency. Per Gemini 3.5 guidance: no temperature/top_p
overrides, and function responses echo both `id` and `name`.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from ..errors import BackendUnavailable, ConfigError
from ..util import new_id
from .base import LLMBackend, LLMTurn, ToolCall, call_with_retry


def _load_sdk():
    try:
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore
        return genai, types
    except ImportError as exc:
        raise BackendUnavailable(
            "google-genai is not installed. Run: pip install 'google-genai>=2.0.0'"
        ) from exc


class GeminiBackend(LLMBackend):
    name = "gemini"

    def __init__(self, settings) -> None:
        if not settings.api_key:
            raise ConfigError("GEMINI_API_KEY is not set — export it or add it to .env "
                              "(offline alternative: --backend mock)")
        self._genai, self._types = _load_sdk()
        self.client = self._genai.Client(api_key=settings.api_key)
        self.model = settings.model

    # ----------------------------------------------------- conversions

    def _part_text(self, text: str):
        return self._types.Part(text=text)

    def _attachment_parts(self, paths: list) -> list:
        parts = []
        for p in paths or []:
            p = Path(p)
            mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
            if p.suffix == ".wav":
                mime = "audio/wav"
            parts.append(self._types.Part(
                inline_data=self._types.Blob(mime_type=mime, data=p.read_bytes())))
        return parts

    def _to_contents(self, messages: list[dict]) -> list:
        types = self._types
        contents = []
        for msg in messages:
            role = msg["role"]
            if role == "user":
                parts = [self._part_text(msg.get("content", ""))]
                parts += self._attachment_parts(msg.get("attachments", []))
                contents.append(types.Content(role="user", parts=parts))
            elif role == "assistant":
                parts = []
                if msg.get("content"):
                    parts.append(self._part_text(msg["content"]))
                for call in msg.get("tool_calls", []):
                    parts.append(types.Part(function_call=types.FunctionCall(
                        id=call.get("id"), name=call["name"], args=call.get("args", {}))))
                contents.append(types.Content(role="model", parts=parts or [self._part_text("")]))
            elif role == "tool":
                # Gemini 3.5: function responses must carry matching id AND name.
                contents.append(types.Content(role="user", parts=[
                    types.Part(function_response=types.FunctionResponse(
                        id=msg.get("tool_call_id"), name=msg.get("name"),
                        response={"result": msg.get("content", "")}))]))
        return contents

    def _tool_config(self, tools: list):
        if not tools:
            return None
        types = self._types
        decls = [types.FunctionDeclaration(name=t.name, description=t.description,
                                           parameters=t.parameters)
                 for t in tools]
        return [types.Tool(function_declarations=decls)]

    # ------------------------------------------------------------ chat

    def chat(self, role: str, system: str, messages: list[dict],
             tools: list, conv_id: str | None = None) -> LLMTurn:
        types = self._types
        config = types.GenerateContentConfig(
            system_instruction=system,
            tools=self._tool_config(tools),
        )
        contents = self._to_contents(messages)
        response = call_with_retry(
            lambda: self.client.models.generate_content(
                model=self.model, contents=contents, config=config),
            what=f"gemini/{role}")
        turn = LLMTurn()
        candidate = response.candidates[0] if response.candidates else None
        if candidate and candidate.content and candidate.content.parts:
            for part in candidate.content.parts:
                fc = getattr(part, "function_call", None)
                if fc is not None and getattr(fc, "name", None):
                    turn.tool_calls.append(ToolCall(
                        id=getattr(fc, "id", None) or new_id("call-"),
                        name=fc.name, args=dict(fc.args or {})))
                elif getattr(part, "text", None):
                    turn.text += part.text
        return turn


def probe_live(settings) -> list[tuple[str, bool, str]]:
    """Two minimal live calls (~200 tokens total) that exercise the exact
    code paths the pipeline uses: plain generation, then a full
    function-calling round trip through the message-conversion layer.
    Cheap enough for a severely rate-limited key."""
    from ..tools.base import ToolSpec
    results = []
    backend = GeminiBackend(settings)

    # 1. plain text turn
    try:
        turn = backend.chat("probe", "You are a health check. Obey exactly.",
                            [{"role": "user", "content": "Reply with exactly: OK"}],
                            tools=[])
        ok = "OK" in (turn.text or "").upper()
        results.append(("text generation", ok, (turn.text or "").strip()[:60]))
    except Exception as exc:
        results.append(("text generation", False, f"{type(exc).__name__}: {exc}"))
        return results  # no point probing further

    # 2. function-calling round trip (call -> tool result -> final)
    ping = ToolSpec(name="ping",
                    description="Return the service status. Call this exactly once.",
                    parameters={"type": "object",
                                "properties": {"target": {"type": "string"}},
                                "required": ["target"]},
                    fn=None)
    messages = [{"role": "user",
                 "content": "Call the ping tool with target='demo', then after "
                            "you see its result reply with exactly: DONE"}]
    try:
        turn = backend.chat("probe", "You are a tool-use health check.",
                            messages, tools=[ping])
        if not turn.tool_calls:
            results.append(("function calling", False,
                            f"no tool call returned (text: {(turn.text or '')[:60]})"))
            return results
        call = turn.tool_calls[0]
        messages.append({"role": "assistant", "content": turn.text or "",
                         "tool_calls": [{"id": call.id, "name": call.name,
                                         "args": call.args}]})
        messages.append({"role": "tool", "tool_call_id": call.id,
                         "name": call.name, "content": "pong"})
        final = backend.chat("probe", "You are a tool-use health check.",
                             messages, tools=[ping])
        results.append(("function calling round-trip", final.is_final,
                        (final.text or "").strip()[:60]))
    except Exception as exc:
        results.append(("function calling round-trip", False,
                        f"{type(exc).__name__}: {exc}"))
    return results
