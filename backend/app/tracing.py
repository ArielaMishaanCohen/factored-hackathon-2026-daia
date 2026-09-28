"""Traza por conversación (design.md 6.3). STUB en memoria; Fase 7 la persiste y enriquece."""
from __future__ import annotations

import time
from contextlib import contextmanager

from .schemas import Span, Trace, TraceTurn
from .store import store


class TurnTracer:
    def __init__(self, trace_id: str, conversation_id: str, customer_id: str, turn_id: int, state_from: str):
        self.trace_id, self.conversation_id, self.customer_id = trace_id, conversation_id, customer_id
        self.turn_id, self.state_from = turn_id, state_from
        self.spans: list[Span] = []
        self.t0 = time.perf_counter()

    @contextmanager
    def span(self, name: str, **extra):
        start, error, out = time.perf_counter(), None, {}
        try:
            yield out
        except Exception as e:
            error = type(e).__name__ + (f": {e.code}" if hasattr(e, "code") else "")
            raise
        finally:
            self.spans.append(Span(name=name, latency_ms=int((time.perf_counter() - start) * 1000),
                                   output=out or None, error=error, **extra))

    @property
    def latency_ms(self) -> int:
        return int((time.perf_counter() - self.t0) * 1000)

    def tools(self) -> list[str]:
        return [s.name.removeprefix("tool.") for s in self.spans if s.name.startswith("tool.")]

    def close(self, state_to: str) -> None:
        trace = store.traces.setdefault(self.trace_id, Trace(
            trace_id=self.trace_id, conversation_id=self.conversation_id, customer_id=self.customer_id, turns=[]))
        trace.turns.append(TraceTurn(turn_id=self.turn_id, state_from=self.state_from,
                                     state_to=state_to, spans=self.spans))
