"""Small shared helpers: JSON extraction from LLM text, ids, console color."""

from __future__ import annotations

import json
import re
import sys
import time
import uuid


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def now_ms() -> int:
    return int(time.time() * 1000)


def truncate(text: str, limit: int = 4000, marker: str = "\n...[truncated]...") -> str:
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + marker


_FENCE_RE = re.compile(r"```(?:json)?\s*\n(.*?)```", re.DOTALL)


def extract_json(text: str):
    """Best-effort: pull the first JSON object/array out of an LLM reply.

    Tries fenced ```json blocks first, then the first balanced {...} or
    [...] region. Returns None when nothing parses.
    """
    if not text:
        return None
    for match in _FENCE_RE.finditer(text):
        candidate = match.group(1).strip()
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        while start != -1:
            depth = 0
            in_str = False
            escape = False
            for i in range(start, len(text)):
                ch = text[i]
                if escape:
                    escape = False
                    continue
                if ch == "\\":
                    escape = True
                    continue
                if ch == '"':
                    in_str = not in_str
                    continue
                if in_str:
                    continue
                if ch == opener:
                    depth += 1
                elif ch == closer:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start : i + 1])
                        except (json.JSONDecodeError, ValueError):
                            break
            start = text.find(opener, start + 1)
    return None


# ---------------------------------------------------------------- console

_USE_COLOR = sys.stdout.isatty()

_CODES = {
    "red": "31", "green": "32", "yellow": "33", "blue": "34",
    "magenta": "35", "cyan": "36", "bold": "1", "dim": "2",
}


def color(text: str, name: str) -> str:
    if not _USE_COLOR or name not in _CODES:
        return text
    return f"\033[{_CODES[name]}m{text}\033[0m"


def banner(text: str) -> str:
    line = "─" * max(12, len(text) + 2)
    return f"{line}\n {text}\n{line}"
