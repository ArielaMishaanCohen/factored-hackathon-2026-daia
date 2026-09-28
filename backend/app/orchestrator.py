"""Orquestador (design.md 3.5).

STUB de Fase 1: recorre el camino feliz, opciones múltiples, fuera de alcance,
estado de disputa y fraude con bloqueo + handoff, para que el frontend tenga todos
los `ui.type` contra el backend real.

Fase 3 (C) completa: aclaraciones con contador y handoff por aclaración agotada,
0 candidatas → handoff tras 2 intentos, R5/R6/R8–R11, fallas de herramienta con
reintentos, "sí"/"no" escrito solo en CONFIRMAR_ACCION, persistencia en SQLite.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from . import confirmations
from .config import get_policy
from .errors import APIError
from .nlu.stub import understand
from .policy.engine import evaluate
from .responder.templates import render
from .schemas import (INTENT_TO_DISPUTE_TYPE, ActionRecord, ChatMessage, ChatRequest, ChatResponse, ChatUI,
                      Decision, HandoffCustomer, HandoffPackage, PendingActionView, Session, ToolError,
                      TurnAudit, VerifiedFact)
from .store import Conversation, store
from .tools import cards, cases, handoff, stub_data, transactions
from .tracing import TurnTracer


class Turn:
    """Acumula la respuesta de un turno."""

    def __init__(self, conv: Conversation, tracer: TurnTracer):
        self.conv, self.tracer = conv, tracer
        self.messages: list[ChatMessage] = []
        self.ui: ChatUI | None = None
        self.case = None
        self.handoff_id: str | None = None
        self.intent = None
        self.intent_confidence = None
        self.rule_id = None

    def say(self, key: str, **facts) -> None:
        self.messages.append(ChatMessage(text=render(key, self.conv.language, **facts), source="template"))


def _get_conversation(session: Session, conversation_id: str | None) -> Conversation:
    if conversation_id:
        conv = store.conversations.get(conversation_id)
        if conv is None or conv.customer_id != session.customer_id:
            raise APIError("NOT_FOUND", "Conversación no encontrada.")
        conv.session_id = session.session_id  # continuar tras reautenticación (mismo cliente)
        return conv
    conv = Conversation(conversation_id=f"CONV-{uuid.uuid4().hex[:6]}", customer_id=session.customer_id,
                        session_id=session.session_id, language=session.language,
                        trace_id=f"TR-{uuid.uuid4().hex[:6]}")
    store.conversations[conv.conversation_id] = conv
    return conv


def handle_chat(session: Session, req: ChatRequest) -> ChatResponse:
    conv = _get_conversation(session, req.conversation_id)
    conv.turn_id += 1
    tracer = TurnTracer(conv.trace_id, conv.conversation_id, conv.customer_id, conv.turn_id, conv.state)
    turn = Turn(conv, tracer)

    if req.ui_action:
        a = req.ui_action
        if a.type == "select_transaction" and a.transaction_id:
            _select_transaction(session, turn, a.transaction_id)
        elif a.type == "confirm" and a.pending_action_id:
            _confirm(session, turn, a.pending_action_id)
        elif a.type == "cancel" and a.pending_action_id:
            _cancel(turn, a.pending_action_id)
        else:
            raise APIError("VALIDATION_ERROR", "ui_action incompleta.")
    elif req.message:
        _message(session, turn, req.message)
    else:
        raise APIError("VALIDATION_ERROR", "Envía message o ui_action.")

    tracer.close(conv.state)
    return ChatResponse(
        conversation_id=conv.conversation_id, turn_id=conv.turn_id, trace_id=conv.trace_id, state=conv.state,
        language=conv.language, messages=turn.messages, ui=turn.ui, case=turn.case, handoff_id=turn.handoff_id,
        audit=TurnAudit(intent=turn.intent, intent_confidence=turn.intent_confidence, rule_id=turn.rule_id,
                        tools=tracer.tools(), latency_ms=tracer.latency_ms, fallback_used=True),
    )


def _message(session: Session, turn: Turn, text: str) -> None:
    conv = turn.conv
    with turn.tracer.span("nlu.understand") as out:
        nlu = understand(text)
        out.update(intent=nlu.intent, confidence=nlu.intent_confidence)

    pending_id = conv.data.get("pending_action_id")
    if conv.state == "CONFIRMAR_ACCION" and pending_id and nlu.confirmation:
        return _confirm(session, turn, pending_id) if nlu.confirmation == "yes" else _cancel(turn, pending_id)

    conv.language = nlu.language
    conv.original_request = conv.original_request or text
    turn.intent, turn.intent_confidence = nlu.intent, nlu.intent_confidence
    conv.data["intent"] = nlu.intent

    if nlu.intent == "fuera_de_alcance" and not nlu.abstain:
        conv.state = "ABSTENERSE"
        return turn.say("abstain")
    if nlu.abstain:
        conv.state = "ACLARAR"
        return turn.say("clarify")
    if nlu.intent == "estado_disputa":
        with turn.tracer.span("tool.get_open_cases") as out:
            open_cases = cases.get_open_cases(session)
            out["n_results"] = len(open_cases)
        conv.state = "INFORMAR_ESTADO"
        if not open_cases:
            return turn.say("status_none")
        return turn.say("status_list", cases=", ".join(f"{c.case_id} ({c.status})" for c in open_cases))

    with turn.tracer.span("tool.search_transactions") as out:
        options = transactions.search_transactions(session, amount=nlu.amount, merchant=nlu.merchant_hint)
        out["n_results"] = len(options)
    conv.state = "IDENTIFICAR_TRANSACCION"
    if not options:
        return turn.say("no_candidates")
    if len(options) == 1:
        return _select_transaction(session, turn, options[0].transaction_id)
    turn.say("options")
    turn.ui = ChatUI(type="transaction_options", options=options)


def _select_transaction(session: Session, turn: Turn, transaction_id: str) -> None:
    conv = turn.conv
    try:
        with turn.tracer.span("tool.get_transaction"):
            tx = transactions.get_transaction(session, transaction_id)
        with turn.tracer.span("tool.get_transaction_risk"):
            risk = transactions.get_transaction_risk(session, transaction_id)
    except ToolError:
        turn.rule_id = "R1"
        return turn.say("not_found")

    with turn.tracer.span("policy.evaluate") as out:
        decision = evaluate(tx, risk, stub_data.CUSTOMER_PROFILE.get(session.customer_id, {}),
                            conv.data.get("intent", "cargo_no_reconocido"), get_policy())
        out.update(rule_id=decision.rule_id, action=decision.action)
    turn.rule_id = decision.rule_id
    conv.state = "EVALUAR"
    conv.data.update(transaction_id=tx.transaction_id, decision=decision.model_dump())

    if decision.action == "INFORM":
        conv.state = "CERRAR"
        return turn.say(f"inform_{decision.rule_id}")
    if decision.action == "FRAUD":
        pa = confirmations.propose(session, "block_card", tx.product_id, f"Bloquear la tarjeta {tx.card_mask}")
        turn.say("confirm_block", card=tx.card_mask)
    else:
        pa = confirmations.propose(session, "create_dispute_case", tx.transaction_id,
                                   f"Registrar disputa por {tx.amount:,.2f} {tx.currency} del {tx.business_date}")
        turn.say("confirm_case", amount=f"{tx.amount:,.2f}", currency=tx.currency, date=tx.business_date)
    _show_confirmation(turn, pa)


def _show_confirmation(turn: Turn, pa) -> None:
    turn.conv.state = "CONFIRMAR_ACCION"
    turn.conv.data["pending_action_id"] = pa.pending_action_id
    turn.ui = ChatUI(type="confirmation", pending_action=PendingActionView(
        pending_action_id=pa.pending_action_id, action=pa.action, summary=pa.summary, expires_at=pa.expires_at))


def _cancel(turn: Turn, pending_action_id: str) -> None:
    if pa := store.pending_actions.get(pending_action_id):
        pa.used = True
    turn.conv.data.pop("pending_action_id", None)
    turn.conv.state = "CERRAR"
    turn.say("cancelled")


def _confirm(session: Session, turn: Turn, pending_action_id: str) -> None:
    conv = turn.conv
    try:
        pa, token = confirmations.confirm(session, pending_action_id)
    except ToolError:
        conv.state = "CERRAR"
        return turn.say("confirmation_expired")
    conv.data.pop("pending_action_id", None)
    decision = Decision.model_validate(conv.data["decision"])
    turn.rule_id = decision.rule_id
    tx = transactions.get_transaction(session, conv.data["transaction_id"])
    conv.state = "EJECUTAR"

    if pa.action == "block_card":
        with turn.tracer.span("tool.block_card"):
            cards.block_card(session, pa.target_id, token)
        with turn.tracer.span("tool.get_card_status") as out:
            verified = cards.get_card_status(session, pa.target_id).status == "Blocked"
            out["verified"] = verified
        conv.data.setdefault("actions", []).append(
            {"action": "block_card", "status": "verified" if verified else "failed",
             "at": datetime.now(timezone.utc).isoformat()})
        if not verified:
            return _handoff(session, turn, tx, decision, None, "TOOL_FAILURE")
        next_pa = confirmations.propose(session, "create_dispute_case", tx.transaction_id,
                                        f"Registrar disputa por {tx.amount:,.2f} {tx.currency}")
        turn.say("blocked_then_case", card=tx.card_mask, amount=f"{tx.amount:,.2f}", currency=tx.currency)
        return _show_confirmation(turn, next_pa)

    dispute_type = INTENT_TO_DISPUTE_TYPE.get(conv.data.get("intent"), "cargo_no_reconocido")
    if decision.action == "FRAUD":
        dispute_type = "fraude"
    with turn.tracer.span("tool.create_dispute_case") as out:
        result = cases.create_dispute_case(session, tx.transaction_id, dispute_type, decision, token, conv.language)
        out.update(case_id=result.case.case_id, created=result.created)
    conv.state = "VERIFICAR"
    with turn.tracer.span("tool.get_case") as out:
        verified = cases.get_case(session, result.case.case_id) == result.case
        out["verified"] = verified
    conv.data.setdefault("actions", []).append(
        {"action": "create_dispute_case", "status": "verified" if verified else "failed",
         "at": datetime.now(timezone.utc).isoformat()})
    if not verified:
        return _handoff(session, turn, tx, decision, None, "TOOL_FAILURE")

    turn.case = result.case
    if decision.action in {"FRAUD", "ESCALATE"}:
        return _handoff(session, turn, tx, decision, result.case, "POLICY_ESCALATION")
    conv.state = "CERRAR"
    turn.say("case_created", case_id=result.case.case_id, sla=result.case.sla_due_at.date().isoformat())
    turn.ui = ChatUI(type="case_created", case=result.case)


def _handoff(session: Session, turn: Turn, tx, decision: Decision, case, reason: str) -> None:
    conv = turn.conv
    risk = transactions.get_transaction_risk(session, tx.transaction_id)
    profile = stub_data.CUSTOMER_PROFILE.get(session.customer_id, {"segment": "?", "country": "?"})
    package = HandoffPackage(
        handoff_id=store.next_id("HO"), case_id=case.case_id if case else None,
        created_at=datetime.now(timezone.utc), handoff_reason=reason,
        priority=decision.priority or "high", sla_due_at=case.sla_due_at if case else None,
        language=conv.language,
        customer=HandoffCustomer(customer_id=session.customer_id, segment=profile["segment"],
                                 country=profile["country"]),
        original_request=conv.original_request or "",
        summary=f"Disputa sobre {tx.transaction_id} ({tx.amount:,.2f} {tx.currency}, {tx.business_date}).",
        verified_facts=[
            VerifiedFact(fact="transaction_id", value=tx.transaction_id, source="transactions"),
            VerifiedFact(fact="amount", value=f"{tx.amount:.2f} {tx.currency}", source="transactions"),
            VerifiedFact(fact="business_date", value=tx.business_date.isoformat(), source="transactions"),
            VerifiedFact(fact="fraud_score", value=risk.fraud_score if risk.fraud_score is not None else "nulo",
                         source="transactions"),
        ],
        policy_decision=decision,
        actions_taken=[ActionRecord.model_validate(a) for a in conv.data.get("actions", [])],
        actions_declined=[], open_questions=[],
        suggested_queue=decision.queue or "disputas", suggested_agent_language=conv.language,
        conversation_id=conv.conversation_id, trace_id=conv.trace_id,
    )
    with turn.tracer.span("tool.create_handoff"):
        ref = handoff.create_handoff(session, package)
    conv.state = "HANDOFF"
    turn.handoff_id = ref.handoff_id
    turn.say("handoff" if reason != "TOOL_FAILURE" else "tool_failure", case_id=case.case_id if case else "")
    turn.ui = ChatUI(type="handoff", handoff_id=ref.handoff_id, queue=package.suggested_queue)
