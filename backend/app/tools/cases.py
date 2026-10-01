"""Herramientas de casos de disputa (design.md 4.3). STUB en memoria; Fase 3: SQLite."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..confirmations import consume_token
from ..config import get_policy
from ..faults import inject
from ..schemas import CreateCaseResult, Decision, DisputeCase, DisputeType, Language, Session, ToolError
from ..store import store
from .transactions import get_transaction

# Esquema de complaints: category / subcategory
_COMPLAINT_CATEGORY = {
    "cargo_no_reconocido": ("Transactions", "Cargo no reconocido"),
    "cobro_incorrecto": ("Fees", "Cobro indebido"),
    "fraude": ("Transactions", "Cargo no reconocido"),
}
_OPEN = {"Open", "In Process", "Escalated"}


def get_open_cases(session: Session) -> list[DisputeCase]:
    inject("get_open_cases")
    return [c for c in store.cases.values() if c.customer_id == session.customer_id and c.status in _OPEN]


def get_recent_cases(session: Session, days: int) -> list[DisputeCase]:
    """Casos del cliente creados en los últimos `days` días, en CUALQUIER estado (R11)."""
    inject("get_recent_cases")
    desde = datetime.now(timezone.utc) - timedelta(days=days)
    return [c for c in store.cases.values() if c.customer_id == session.customer_id and c.created_at >= desde]


def get_case(session: Session, case_id: str) -> DisputeCase:
    inject("get_case")
    case = store.cases.get(case_id)
    if case is None or case.customer_id != session.customer_id:
        raise ToolError("NOT_FOUND", "Caso no encontrado.")
    return case


def create_dispute_case(session: Session, transaction_id: str, dispute_type: DisputeType, decision: Decision,
                        confirmation_token: str | None, language: Language = "es") -> CreateCaseResult:
    inject("create_dispute_case")
    tx = get_transaction(session, transaction_id)  # NOT_FOUND si no es del cliente
    for c in store.cases.values():  # idempotente por (transaction_id, dispute_type)
        if c.transaction_id == transaction_id and c.dispute_type == dispute_type:
            return CreateCaseResult(case=c, created=False)

    consume_token(session, confirmation_token, "create_dispute_case", transaction_id)
    priority = decision.priority or "medium"
    now = datetime.now(timezone.utc)
    category, subcategory = _COMPLAINT_CATEGORY[dispute_type]
    case = DisputeCase(
        case_id=store.next_id("DSP"), customer_id=session.customer_id, transaction_id=transaction_id,
        product_id=tx.product_id, dispute_type=dispute_type, category=category, subcategory=subcategory,
        priority=priority, status="Escalated" if decision.action in {"FRAUD", "ESCALATE"} else "Open",
        rule_id=decision.rule_id, policy_version=decision.policy_version, language=language,
        created_at=now, sla_due_at=now + timedelta(days=get_policy()["sla_days_by_priority"][priority]),
    )
    store.cases[case.case_id] = case
    return CreateCaseResult(case=case, created=True)
