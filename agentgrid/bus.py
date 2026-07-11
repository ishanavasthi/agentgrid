"""EventBus: every pipeline happening is published here.

Consumers: the live dashboard (SSE), the CLI printer, and the smoke tests.
Thread-safe; subscribers get their own queue; history enables replay for
late-joining dashboard clients.
"""

from __future__ import annotations

import queue
import threading
from .util import now_ms


class EventBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subs: list[queue.Queue] = []
        self._seq = 0
        self.history: list[dict] = []

    def publish(self, type: str, **data) -> dict:
        with self._lock:
            self._seq += 1
            event = {"seq": self._seq, "ts": now_ms(), "type": type, **data}
            self.history.append(event)
            subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait(event)
            except queue.Full:
                pass
        return event

    def subscribe(self, replay: bool = True) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=10000)
        with self._lock:
            if replay:
                for event in self.history:
                    try:
                        q.put_nowait(event)
                    except queue.Full:
                        break
            self._subs.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subs:
                self._subs.remove(q)

    def reset(self) -> None:
        """Clear history at the start of a fresh run (dashboard clears too)."""
        with self._lock:
            self.history.clear()


BUS = EventBus()
