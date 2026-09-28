"""Acciones pendientes y tokens de confirmación (design.md 4.4).

El LLM nunca ve el pending_action_id ni el token. La UI solo conoce el
pending_action_id; el token se emite aquí cuando el cliente confirma.
"""
from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from datetime import datetime, timedelta, timezone

from .config import get_policy, get_settings
from .schemas import PendingAction, Session, ToolError
from .store import store


def propose(session: Session, action: str, target_id: str, summary: str) -> PendingAction:
    ttl = get_policy()["confirmation"]["ttl_seconds"]
    pa = PendingAction(pending_action_id=f"PA-{uuid.uuid4().hex[:8]}", action=action, target_id=target_id,
                       session_id=session.session_id, summary=summary,
                       expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl))
    store.pending_actions[pa.pending_action_id] = pa
    return pa


def _sign(payload: str) -> str:
    return hmac.new(get_settings().jwt_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def confirm(session: Session, pending_action_id: str) -> tuple[PendingAction, str]:
    """Valida la acción pendiente y emite un token de un solo uso ligado a acción + objeto + sesión."""
    pa = store.pending_actions.get(pending_action_id)
    if (pa is None or pa.used or pa.session_id != session.session_id
            or pa.expires_at < datetime.now(timezone.utc)):
        raise ToolError("INVALID_CONFIRMATION", "Acción pendiente inválida o expirada.")
    pa.used = True
    payload = f"{pa.action}|{pa.target_id}|{session.session_id}|{int(pa.expires_at.timestamp())}"
    return pa, f"{payload}|{_sign(payload)}"


def consume_token(session: Session, token: str | None, action: str, target_id: str) -> None:
    """Lo llaman las herramientas de escritura. Falla si el token no corresponde."""
    if not token:
        raise ToolError("INVALID_CONFIRMATION", "Falta el token de confirmación.")
    try:
        t_action, t_target, t_sid, t_exp, sig = token.split("|")
    except ValueError:
        raise ToolError("INVALID_CONFIRMATION", "Token mal formado.")
    payload = f"{t_action}|{t_target}|{t_sid}|{t_exp}"
    if (not hmac.compare_digest(sig, _sign(payload)) or t_action != action or t_target != target_id
            or t_sid != session.session_id or int(t_exp) < time.time()
            or token in store.used_confirmation_tokens):
        raise ToolError("INVALID_CONFIRMATION", "Token inválido, expirado o ya usado.")
    store.used_confirmation_tokens.add(token)
