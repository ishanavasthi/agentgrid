"""Agent runtime: one class drives every role through the backend tool loop."""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import PipelineError
from ..util import extract_json, new_id, truncate


@dataclass
class FinalResult:
    text: str
    data: dict | list | None


class Agent:
    def __init__(self, role, backend, ledger, bus, toolbox=None) -> None:
        self.role = role
        self.backend = backend
        self.ledger = ledger
        self.bus = bus
        self.toolbox = toolbox

    def run(self, prompt: str, task_id: str | None = None,
            attachments: list | None = None, max_steps: int = 12) -> FinalResult:
        conv_id = new_id("conv-")
        messages: list[dict] = [{"role": "user", "content": prompt}]
        if attachments:
            messages[0]["attachments"] = [str(p) for p in attachments]
        specs = self.toolbox.specs if self.toolbox else []

        self.bus.publish("agent_state", agent=self.role.title, state="active",
                         task_id=task_id)
        try:
            for _ in range(max_steps):
                turn = self.backend.chat(self.role.name, self.role.system_prompt,
                                         messages, specs, conv_id=conv_id)
                if turn.tool_calls:
                    if turn.text:
                        self.ledger.message(self.role.title, turn.text, task_id=task_id)
                    messages.append({
                        "role": "assistant", "content": turn.text or "",
                        "tool_calls": [{"id": c.id, "name": c.name, "args": c.args}
                                       for c in turn.tool_calls]})
                    for call in turn.tool_calls:
                        self.bus.publish("tool_call", agent=self.role.title,
                                         tool=call.name,
                                         args=_arg_preview(call.args), task_id=task_id)
                        result = (self.toolbox.execute(call.name, call.args)
                                  if self.toolbox else "ERROR: no tools available")
                        self.bus.publish("tool_result", agent=self.role.title,
                                         tool=call.name,
                                         result=truncate(result, 400), task_id=task_id)
                        messages.append({"role": "tool", "tool_call_id": call.id,
                                         "name": call.name, "content": result})
                    continue
                self.ledger.message(self.role.title, turn.text, task_id=task_id)
                return FinalResult(text=turn.text, data=extract_json(turn.text))
            raise PipelineError(
                f"{self.role.title} exceeded {max_steps} steps without finishing")
        finally:
            self.bus.publish("agent_state", agent=self.role.title, state="idle",
                             task_id=task_id)


def _arg_preview(args: dict) -> dict:
    preview = {}
    for k, v in (args or {}).items():
        preview[k] = truncate(str(v), 160) if isinstance(v, str) else v
    return preview
