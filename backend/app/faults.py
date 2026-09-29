"""Fallas simuladas y reintentos acotados (design.md 4.1, roadmap Fase 7).

- inject(tool): cada herramienta lo llama al empezar. Si la prueba pidió que esa
  herramienta falle, lanza ToolError("TIMEOUT"). Solo funciona con FAULT_INJECTION=true
  (en producción el header se ignora, así nadie puede forzar fallas desde afuera).
- with_retries(fn): reintenta SOLO en TIMEOUT, máximo 2 veces, con espera creciente.
"""
from __future__ import annotations

import time
from contextvars import ContextVar

from .schemas import ToolError

MAX_RETRIES = 2
BACKOFF_SECONDS = 0.05          # 0.05 s, luego 0.1 s (corto a propósito para la demo)

# Herramientas que deben fallar en ESTA petición (lo llena main.py desde el header).
_forced: ContextVar[frozenset[str]] = ContextVar("forced_faults", default=frozenset())


def set_forced(tools: set[str]):
    return _forced.set(frozenset(tools))


def reset_forced(token) -> None:
    _forced.reset(token)


def inject(tool: str) -> None:
    if tool in _forced.get():
        raise ToolError("TIMEOUT", f"Falla simulada en {tool}")


def with_retries(fn, *args, attempts_out: dict | None = None, **kwargs):
    """Llama fn(*args, **kwargs). Si da TIMEOUT, reintenta; cualquier otro error sube de una."""
    for attempt in range(1, MAX_RETRIES + 2):
        if attempts_out is not None:
            attempts_out["attempts"] = attempt
        try:
            return fn(*args, **kwargs)
        except ToolError as e:
            if e.code != "TIMEOUT" or attempt > MAX_RETRIES:
                raise
            time.sleep(BACKOFF_SECONDS * 2 ** (attempt - 1))
