"""Herramientas de tarjeta (design.md 4.3). Bloqueo MOCK: se guarda en el store, no en gold."""
from __future__ import annotations

from datetime import datetime, timezone

from ..confirmations import consume_token
from ..faults import inject
from ..schemas import BlockResult, CardStatus, Session, ToolError
from ..store import store
from . import data_source


def get_card_status(session: Session, product_id: str) -> CardStatus:
    inject("get_card_status")
    c = data_source.card(session.customer_id, product_id)  # None si no existe o no es del cliente
    if c is not None:
        # El estado efectivo es el del bloqueo operativo si existe; si no, el de gold.
        return store.card_blocks.get(product_id) or CardStatus(
            product_id=product_id, card_mask=c["card_mask"], status=c["status"])
    raise ToolError("NOT_FOUND", "Tarjeta no encontrada.")


def block_card(session: Session, product_id: str, confirmation_token: str | None) -> BlockResult:
    inject("block_card")
    current = get_card_status(session, product_id)
    if current.status == "Blocked":  # idempotente
        return BlockResult(product_id=product_id, status="Blocked", blocked_at=current.blocked_at)
    consume_token(session, confirmation_token, "block_card", product_id)
    now = datetime.now(timezone.utc)
    store.card_blocks[product_id] = CardStatus(product_id=product_id, card_mask=current.card_mask,
                                               status="Blocked", blocked_at=now)
    return BlockResult(product_id=product_id, status="Blocked", blocked_at=now)
