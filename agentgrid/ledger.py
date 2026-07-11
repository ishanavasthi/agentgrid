"""The structured handoff ledger — Functionality #2, the heart of AgentGrid.

Instead of passing raw chat transcripts between agents, every delegation
is a Task record plus a Handoff packet (task, acceptance criteria,
context summary, prior critiques). Agents read and write the ledger; the
ledger persists to runs/<id>/ledger.json after every mutation and mirrors
everything onto the EventBus for the live dashboard.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .util import new_id

STATUSES = ("pending", "in_progress", "done", "failed", "rejected")


@dataclass
class Task:
    id: str
    title: str
    kind: str                      # issue|plan|code|review|integrate|test|publish|break|verify|intake
    owner: str = ""
    parent: str | None = None
    status: str = "pending"
    acceptance: str = ""
    detail: str = ""
    artifacts: dict = field(default_factory=dict)
    history: list = field(default_factory=list)
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)


class Ledger:
    def __init__(self, run_dir: Path, bus) -> None:
        self.run_dir = Path(run_dir)
        self.bus = bus
        self._lock = threading.RLock()
        self.tasks: dict[str, Task] = {}
        self.order: list[str] = []
        self.handoffs: list[dict] = []
        self.messages: list[dict] = []
        self.meta: dict = {}

    # ------------------------------------------------------------- tasks

    def new_task(self, title: str, kind: str, owner: str = "", parent: str | None = None,
                 acceptance: str = "", detail: str = "") -> Task:
        with self._lock:
            task = Task(id=new_id("t-"), title=title, kind=kind, owner=owner,
                        parent=parent, acceptance=acceptance, detail=detail)
            self.tasks[task.id] = task
            self.order.append(task.id)
            self._save_locked()
        self.bus.publish("task_created", task=asdict(task))
        return task

    def update(self, task_id: str, status: str | None = None, note: str = "",
               owner: str | None = None, **artifacts) -> Task:
        with self._lock:
            task = self.tasks[task_id]
            if status:
                if status not in STATUSES:
                    raise ValueError(f"bad status {status!r}")
                task.status = status
            if owner is not None:
                task.owner = owner
            if artifacts:
                task.artifacts.update(artifacts)
            if note:
                task.history.append({"ts": time.time(), "note": note})
            task.updated = time.time()
            self._save_locked()
        self.bus.publish("task_updated", task=asdict(task), note=note)
        return task

    # ----------------------------------------------------------- handoff

    def handoff(self, frm: str, to: str, task_id: str, packet: dict) -> dict:
        record = {"ts": time.time(), "from": frm, "to": to,
                  "task_id": task_id, "packet": packet}
        with self._lock:
            self.handoffs.append(record)
            self._save_locked()
        task = self.tasks.get(task_id)
        self.bus.publish("handoff", frm=frm, to=to, task_id=task_id,
                         task_title=task.title if task else "",
                         packet_keys=sorted(packet.keys()))
        return record

    def packet_for(self, task_id: str, **extra) -> dict:
        """Build the structured context blob an agent receives with a task."""
        with self._lock:
            task = self.tasks[task_id]
            parent = self.tasks.get(task.parent) if task.parent else None
            packet = {
                "task_id": task.id,
                "title": task.title,
                "kind": task.kind,
                "acceptance": task.acceptance,
                "detail": task.detail,
                "parent_title": parent.title if parent else "",
                "prior_notes": [h["note"] for h in task.history][-5:],
            }
        packet.update(extra)
        return packet

    # ---------------------------------------------------------- messages

    def message(self, agent: str, content: str, kind: str = "say",
                task_id: str | None = None) -> None:
        record = {"ts": time.time(), "agent": agent, "kind": kind,
                  "content": content, "task_id": task_id}
        with self._lock:
            self.messages.append(record)
        self.bus.publish("agent_message", agent=agent, kind=kind,
                         content=content, task_id=task_id)

    # ------------------------------------------------------- persistence

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "meta": dict(self.meta),
                "tasks": [asdict(self.tasks[i]) for i in self.order],
                "handoffs": list(self.handoffs),
                "messages": list(self.messages[-500:]),
            }

    def save(self) -> None:
        with self._lock:
            self._save_locked()

    def _save_locked(self) -> None:
        try:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            path = self.run_dir / "ledger.json"
            data = {
                "meta": dict(self.meta),
                "tasks": [asdict(self.tasks[i]) for i in self.order],
                "handoffs": self.handoffs,
                "messages": self.messages,
            }
            path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        except OSError:
            pass  # persistence is best-effort; the bus still has everything
