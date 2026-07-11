"""Tool plumbing: specs (JSON-schema described) + a per-agent toolbox."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..errors import ToolError
from ..util import truncate


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict          # JSON schema: {"type":"object","properties":{...},"required":[...]}
    fn: Callable = field(repr=False, default=None)


class Toolbox:
    def __init__(self, specs: list[ToolSpec]) -> None:
        self._by_name = {s.name: s for s in specs}

    @property
    def specs(self) -> list[ToolSpec]:
        return list(self._by_name.values())

    def execute(self, name: str, args: dict) -> str:
        spec = self._by_name.get(name)
        if spec is None:
            return f"ERROR: unknown tool {name!r}. Available: {sorted(self._by_name)}"
        try:
            result = spec.fn(**(args or {}))
            return truncate(str(result), 12000)
        except ToolError as exc:
            return f"ERROR: {exc}"
        except TypeError as exc:
            return f"ERROR: bad arguments for {name}: {exc}"
        except Exception as exc:  # tool crashes must not kill the pipeline
            return f"ERROR: {type(exc).__name__}: {exc}"
