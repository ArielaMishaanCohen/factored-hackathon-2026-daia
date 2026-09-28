"""Estado operativo. STUB de Fase 1: en memoria.

Fase 3 (C): reemplazar por SQLite (tablas conversations, pending_actions, cases,
card_blocks, handoffs, traces, revoked_sessions) manteniendo esta interfaz.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .schemas import CardStatus, DisputeCase, HandoffPackage, PendingAction, Trace


@dataclass
class Conversation:
    conversation_id: str
    customer_id: str
    session_id: str
    state: str = "INICIO"
    language: str = "es"
    turn_id: int = 0
    original_request: str | None = None
    trace_id: str = ""
    data: dict = field(default_factory=dict)


@dataclass
class MemoryStore:
    conversations: dict[str, Conversation] = field(default_factory=dict)
    pending_actions: dict[str, PendingAction] = field(default_factory=dict)
    cases: dict[str, DisputeCase] = field(default_factory=dict)
    card_blocks: dict[str, CardStatus] = field(default_factory=dict)
    handoffs: dict[str, HandoffPackage] = field(default_factory=dict)
    traces: dict[str, Trace] = field(default_factory=dict)
    revoked_sessions: set[str] = field(default_factory=set)
    used_confirmation_tokens: set[str] = field(default_factory=set)
    _seq: dict[str, int] = field(default_factory=dict)

    def next_id(self, prefix: str, width: int = 6) -> str:
        self._seq[prefix] = self._seq.get(prefix, 0) + 1
        return f"{prefix}-{self._seq[prefix]:0{width}d}"


store = MemoryStore()


def reset_store() -> None:
    """Para tests."""
    global store
    store.__init__()
