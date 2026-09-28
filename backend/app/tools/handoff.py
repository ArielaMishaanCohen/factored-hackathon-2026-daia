"""Herramienta de handoff (design.md 4.3 y 5). Pydantic rechaza paquetes incompletos."""
from __future__ import annotations

from ..schemas import HandoffPackage, HandoffRef, Session
from ..store import store


def create_handoff(session: Session, package: HandoffPackage) -> HandoffRef:
    package = HandoffPackage.model_validate(package.model_dump())  # revalida por si se mutó
    store.handoffs[package.handoff_id] = package
    return HandoffRef(handoff_id=package.handoff_id)
