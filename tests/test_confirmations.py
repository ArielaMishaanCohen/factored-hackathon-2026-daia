from datetime import datetime, timedelta, timezone

import pytest

from app import confirmations
from app.schemas import Session, ToolError
from app.store import reset_store


def _session(sid="s1"):
    return Session(session_id=sid, customer_id="CUS-DEMO-01", role="customer", language="es",
                   expires_at=datetime.now(timezone.utc) + timedelta(minutes=15))


def test_token_is_single_use_and_bound_to_action():
    reset_store()
    s = _session()
    pa = confirmations.propose(s, "create_dispute_case", "TX-1", "x")
    _, token = confirmations.confirm(s, pa.pending_action_id)
    with pytest.raises(ToolError):
        confirmations.consume_token(s, token, "block_card", "TX-1")  # otra acción
    confirmations.consume_token(s, token, "create_dispute_case", "TX-1")
    with pytest.raises(ToolError):
        confirmations.consume_token(s, token, "create_dispute_case", "TX-1")  # reutilizado


def test_other_session_cannot_confirm():
    reset_store()
    pa = confirmations.propose(_session("s1"), "block_card", "PRD-1", "x")
    with pytest.raises(ToolError):
        confirmations.confirm(_session("s2"), pa.pending_action_id)
