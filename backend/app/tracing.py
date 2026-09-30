"""Traza por conversación (design.md 6.3, roadmap Fase 7).

Cada turno guarda: los spans (cada paso: NLU, herramienta, política…) y un RESUMEN del turno
(intención, regla, acciones verificadas, latencia, tokens, costo y versiones).

Además, al cerrar cada turno se escribe UNA línea JSON en el log ("latam.trace").
En Render se ve en la pestaña Logs. Nunca incluye lo que escribió el cliente.
"""
from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from datetime import datetime, timezone

from .schemas import Span, Trace, TraceTurn
from .store import store

log = logging.getLogger("latam.trace")
if not log.handlers:                      # que se vea en la consola / logs de Render
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(_h)
log.setLevel(logging.INFO)


class TurnTracer:
    def __init__(self, trace_id: str, conversation_id: str, customer_id: str, turn_id: int, state_from: str):
        self.trace_id, self.conversation_id, self.customer_id = trace_id, conversation_id, customer_id
        self.turn_id, self.state_from = turn_id, state_from
        self.spans: list[Span] = []
        self.t0 = time.perf_counter()
        self.started_at = datetime.now(timezone.utc)

    @contextmanager
    def span(self, name: str, **extra):
        start, error, out = time.perf_counter(), None, {}
        try:
            yield out
        except Exception as e:
            error = type(e).__name__ + (f": {e.code}" if hasattr(e, "code") else "")
            raise
        finally:
            usage = out.pop("_usage", None)   # LLMUsage de Gemini, si el paso lo usó
            if usage is not None:
                extra = {**extra, "model": usage.model, "tokens_in": usage.tokens_in,
                         "tokens_out": usage.tokens_out, "cost_usd": usage.cost_usd}
            self.spans.append(Span(name=name, latency_ms=int((time.perf_counter() - start) * 1000),
                                   output=out or None, error=error, **extra))

    @property
    def latency_ms(self) -> int:
        return int((time.perf_counter() - self.t0) * 1000)

    def tools(self) -> list[str]:
        return [s.name.removeprefix("tool.") for s in self.spans if s.name.startswith("tool.")]

    def close(self, state_to: str, **summary) -> TraceTurn:
        """Cierra el turno: lo agrega a la traza y escribe la línea de log."""
        trace = store.traces.setdefault(self.trace_id, Trace(
            trace_id=self.trace_id, conversation_id=self.conversation_id, customer_id=self.customer_id, turns=[]))
        turn = TraceTurn(
            turn_id=self.turn_id, state_from=self.state_from, state_to=state_to, spans=self.spans,
            started_at=self.started_at, latency_ms=self.latency_ms,
            tokens_in=sum(s.tokens_in or 0 for s in self.spans),
            tokens_out=sum(s.tokens_out or 0 for s in self.spans),
            cost_usd=round(sum(s.cost_usd or 0.0 for s in self.spans), 6),
            **summary)
        trace.turns.append(turn)
        log.info(json.dumps({
            "event": "turn", "trace_id": self.trace_id, "turn_id": self.turn_id,
            "state_from": self.state_from, "state_to": state_to, "input_kind": turn.input_kind,
            "language": turn.language, "intent": turn.intent, "rule_id": turn.rule_id,
            "actions": [f"{a.action}:{a.status}" for a in turn.actions],
            "handoff": turn.handoff_id is not None, "latency_ms": turn.latency_ms,
            "tool_errors": [s.name for s in self.spans if s.error],
            "cost_usd": turn.cost_usd,
        }, ensure_ascii=False))
        return turn
