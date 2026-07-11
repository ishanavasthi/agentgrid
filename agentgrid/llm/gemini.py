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
from .base import LLMBackend, LLMTurn, ToolCall


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
        response = self.client.models.generate_content(
            model=self.model,
            contents=self._to_contents(messages),
            config=config,
        )
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
