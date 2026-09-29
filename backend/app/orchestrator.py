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

from . import confirmations, faults
from .config import get_policy
from .errors import APIError
from .nlu.stub import understand
from .policy.engine import evaluate
from .responder.templates import render
from .schemas import (INTENT_TO_DISPUTE_TYPE, ActionRecord, ChatMessage, ChatRequest, ChatResponse, ChatUI,
                      Decision, HandoffCustomer, HandoffPackage, PendingActionView, Session, ToolError,
                      TurnAudit, VerifiedFact)
from .store import Conversation, store
from .tools import cards, cases, data_source, handoff, transactions
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
            _cancel(session, turn, a.pending_action_id)
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


def _tool(turn: Turn, name: str, fn, *args, **kwargs):
    """Llama una herramienta dentro de su span de traza, con reintentos acotados en TIMEOUT."""
    with turn.tracer.span(f"tool.{name}") as out:
        return faults.with_retries(fn, *args, attempts_out=out, **kwargs)


def _message(session: Session, turn: Turn, text: str) -> None:
    conv = turn.conv
    with turn.tracer.span("nlu.understand") as out:
        nlu = understand(text)
        out.update(intent=nlu.intent, confidence=nlu.intent_confidence)

    pending_id = conv.data.get("pending_action_id")
    if conv.state == "CONFIRMAR_ACCION" and pending_id and nlu.confirmation:
        if nlu.confirmation == "yes":
            return _confirm(session, turn, pending_id)
        return _cancel(session, turn, pending_id)

    conv.language = nlu.language
    conv.original_request = conv.original_request or text
    turn.intent, turn.intent_confidence = nlu.intent, nlu.intent_confidence
    conv.data["intent"] = nlu.intent
    policy = get_policy()

    if nlu.intent == "fuera_de_alcance" and not nlu.abstain:
        conv.state = "ABSTENERSE"
        return turn.say("abstain")
    if nlu.abstain:
        # Máximo `max_clarifications` preguntas; a la siguiente, pasa a un humano.
        conv.data["clarifications"] = conv.data.get("clarifications", 0) + 1
        if conv.data["clarifications"] > policy["intent"]["max_clarifications"]:
            return _handoff(session, turn, "CLARIFICATION_EXHAUSTED",
                            open_questions=["¿Qué transacción quiere disputar el cliente y por qué?"])
        conv.state = "ACLARAR"
        return turn.say("clarify")

    try:
        if nlu.intent == "estado_disputa":
            open_cases = _tool(turn, "get_open_cases", cases.get_open_cases, session)
            conv.state = "INFORMAR_ESTADO"
            if not open_cases:
                return turn.say("status_none")
            return turn.say("status_list", cases=", ".join(f"{c.case_id} ({c.status})" for c in open_cases))

        options = _tool(turn, "search_transactions", transactions.search_transactions,
                        session, amount=nlu.amount, merchant=nlu.merchant_hint)
    except ToolError as e:
        return _tool_failure(session, turn, e, "No se pudo consultar la información del cliente.")

    conv.state = "IDENTIFICAR_TRANSACCION"
    if not options:
        # Máximo 2 búsquedas vacías (misma cuota que las aclaraciones); luego, humano.
        conv.data["empty_searches"] = conv.data.get("empty_searches", 0) + 1
        if conv.data["empty_searches"] > policy["intent"]["max_clarifications"]:
            return _handoff(session, turn, "NO_TRANSACTION_FOUND",
                            open_questions=["El cliente describe un cargo que no aparece en sus "
                                            "transacciones de los últimos días: confirmar monto, fecha y comercio."])
        return turn.say("no_candidates")
    if len(options) == 1:
        return _select_transaction(session, turn, options[0].transaction_id)
    turn.say("options")
    turn.ui = ChatUI(type="transaction_options", options=options)


def _select_transaction(session: Session, turn: Turn, transaction_id: str) -> None:
    conv = turn.conv
    try:
        tx = _tool(turn, "get_transaction", transactions.get_transaction, session, transaction_id)
        risk = _tool(turn, "get_transaction_risk", transactions.get_transaction_risk, session, transaction_id)
        open_cases = _tool(turn, "get_open_cases", cases.get_open_cases, session)
    except ToolError as e:
        if e.code == "NOT_FOUND":            # R1: no existe o no es del cliente (mismo mensaje)
            turn.rule_id = "R1"
            return turn.say("not_found")
        return _tool_failure(session, turn, e, "No se pudo leer la transacción elegida.")

    customer_ctx = {**data_source.customer_profile(session.customer_id),
                    "open_cases_by_tx": {c.transaction_id: {"case_id": c.case_id, "status": c.status}
                                         for c in open_cases}}
    with turn.tracer.span("policy.evaluate") as out:
        decision = evaluate(tx, risk, customer_ctx, conv.data.get("intent", "cargo_no_reconocido"), get_policy())
        out.update(rule_id=decision.rule_id, action=decision.action)
    turn.rule_id = decision.rule_id
    conv.state = "EVALUAR"
    conv.data.update(transaction_id=tx.transaction_id, decision=decision.model_dump())

    if decision.action == "INFORM":
        conv.state = "CERRAR"
        existing = customer_ctx["open_cases_by_tx"].get(tx.transaction_id, {})
        return turn.say(f"inform_{decision.rule_id}", case_id=existing.get("case_id", ""),
                        status=existing.get("status", ""))
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


def _decision(conv: Conversation) -> Decision | None:
    return Decision.model_validate(conv.data["decision"]) if conv.data.get("decision") else None


def _cancel(session: Session, turn: Turn, pending_action_id: str) -> None:
    conv = turn.conv
    pa = store.pending_actions.get(pending_action_id)
    if pa:
        pa.used = True
    conv.data.pop("pending_action_id", None)
    decision = _decision(conv)
    # Si la política ya había dicho "esto necesita un humano", que el cliente diga
    # que no a una acción no cambia eso: se hace handoff (sin caso) y se anota qué rechazó.
    if pa and decision and decision.action in {"FRAUD", "ESCALATE"}:
        turn.rule_id = decision.rule_id
        conv.data.setdefault("declined", []).append(pa.action)
        tx = _try(lambda: transactions.get_transaction(session, conv.data["transaction_id"]))
        return _handoff(session, turn, "POLICY_ESCALATION", tx=tx, decision=decision,
                        case=_existing_case(session, conv), cancelled=True)
    conv.state = "CERRAR"
    turn.say("cancelled")


def _confirm(session: Session, turn: Turn, pending_action_id: str) -> None:
    conv = turn.conv
    try:
        pa, token = confirmations.confirm(session, pending_action_id)
    except ToolError:
        conv.state = "CERRAR"
        return turn.say("confirmation_expired")
    conv.data.pop("pending_action_id", None)
    decision = _decision(conv)
    turn.rule_id = decision.rule_id
    conv.state = "EJECUTAR"
    try:
        tx = _tool(turn, "get_transaction", transactions.get_transaction, session, conv.data["transaction_id"])
        if pa.action == "block_card":
            return _execute_block(session, turn, pa, token, tx, decision)
        return _execute_case(session, turn, token, tx, decision)
    except ToolError as e:
        _record(conv, pa.action, "failed")
        return _tool_failure(session, turn, e, f"Verificar si la acción '{pa.action}' quedó aplicada "
                                               f"y completarla manualmente si no.")


def _execute_block(session: Session, turn: Turn, pa, token: str, tx, decision: Decision) -> None:
    conv = turn.conv
    _tool(turn, "block_card", cards.block_card, session, pa.target_id, token)
    with turn.tracer.span("verify.card_blocked") as out:
        verified = cards.get_card_status(session, pa.target_id).status == "Blocked"
        out["verified"] = verified
    _record(conv, "block_card", "verified" if verified else "failed")
    if not verified:
        raise ToolError("INTERNAL", "El bloqueo no se reflejó al volver a leer la tarjeta.")
    next_pa = confirmations.propose(session, "create_dispute_case", tx.transaction_id,
                                    f"Registrar disputa por {tx.amount:,.2f} {tx.currency}")
    turn.say("blocked_then_case", card=tx.card_mask, amount=f"{tx.amount:,.2f}", currency=tx.currency)
    _show_confirmation(turn, next_pa)


def _execute_case(session: Session, turn: Turn, token: str, tx, decision: Decision) -> None:
    conv = turn.conv
    dispute_type = INTENT_TO_DISPUTE_TYPE.get(conv.data.get("intent"), "cargo_no_reconocido")
    if decision.action == "FRAUD":
        dispute_type = "fraude"
    # create_dispute_case es idempotente, así que reintentarlo es seguro.
    result = _tool(turn, "create_dispute_case", cases.create_dispute_case,
                   session, tx.transaction_id, dispute_type, decision, token, conv.language)
    conv.state = "VERIFICAR"
    with turn.tracer.span("verify.case_exists") as out:
        verified = _tool(turn, "get_case", cases.get_case, session, result.case.case_id) == result.case
        out["verified"] = verified
    _record(conv, "create_dispute_case", "verified" if verified else "failed")
    if not verified:
        raise ToolError("INTERNAL", "El caso no se encontró al volver a leerlo.")

    turn.case = result.case
    conv.data["case_id"] = result.case.case_id
    if not result.created:  # la tool devolvió un caso que ya existía: no decir "Registré"
        conv.state = "CERRAR"
        return turn.say("inform_R5", case_id=result.case.case_id, status=result.case.status)
    if decision.action in {"FRAUD", "ESCALATE"}:
        return _handoff(session, turn, "POLICY_ESCALATION", tx=tx, decision=decision, case=result.case)
    conv.state = "CERRAR"
    turn.say("case_created", case_id=result.case.case_id, sla=result.case.sla_due_at.date().isoformat())
    turn.ui = ChatUI(type="case_created", case=result.case)


# --- Auxiliares ------------------------------------------------------------------------

def _record(conv: Conversation, action: str, status: str) -> None:
    conv.data.setdefault("actions", []).append(
        {"action": action, "status": status, "at": datetime.now(timezone.utc).isoformat()})


def _try(fn):
    """Para datos 'de adorno' del handoff: si fallan, seguimos sin ellos."""
    try:
        return fn()
    except Exception:
        return None


def _existing_case(session: Session, conv: Conversation):
    case_id = conv.data.get("case_id")
    return _try(lambda: cases.get_case(session, case_id)) if case_id else None


def _tool_failure(session: Session, turn: Turn, error: ToolError, question: str) -> None:
    """Una herramienta falló aun con reintentos: nunca decir 'listo'; pasar a un humano."""
    conv = turn.conv
    tx = _try(lambda: transactions.get_transaction(session, conv.data["transaction_id"])) \
        if conv.data.get("transaction_id") else None
    _handoff(session, turn, "TOOL_FAILURE", tx=tx, decision=_decision(conv),
             case=_existing_case(session, conv), open_questions=[f"{question} (error: {error.code})"])


def _handoff(session: Session, turn: Turn, reason: str, tx=None, decision: Decision | None = None,
             case=None, open_questions: list[str] | None = None, cancelled: bool = False) -> None:
    conv = turn.conv
    profile = data_source.customer_profile(session.customer_id)
    facts: list[VerifiedFact] = []
    if tx is not None:
        risk = _try(lambda: transactions.get_transaction_risk(session, tx.transaction_id))
        facts = [
            VerifiedFact(fact="transaction_id", value=tx.transaction_id, source="transactions"),
            VerifiedFact(fact="amount", value=f"{tx.amount:.2f} {tx.currency}", source="transactions"),
            VerifiedFact(fact="business_date", value=tx.business_date.isoformat(), source="transactions"),
        ]
        if risk is not None:
            facts.append(VerifiedFact(fact="fraud_score", source="transactions",
                                      value=risk.fraud_score if risk.fraud_score is not None else "nulo"))
        summary = f"Disputa sobre {tx.transaction_id} ({tx.amount:,.2f} {tx.currency}, {tx.business_date})."
    else:
        summary = "El cliente quiere disputar un cargo, pero no se identificó la transacción."
    if case is not None:
        facts.append(VerifiedFact(fact="case_id", value=case.case_id, source="cases"))

    priority = (decision.priority if decision and decision.priority
                else "high" if reason == "TOOL_FAILURE" else "medium")
    package = HandoffPackage(
        handoff_id=store.next_id("HO"), case_id=case.case_id if case else None,
        created_at=datetime.now(timezone.utc), handoff_reason=reason,
        priority=priority, sla_due_at=case.sla_due_at if case else None,
        language=conv.language,
        customer=HandoffCustomer(customer_id=session.customer_id, segment=profile["segment"],
                                 country=profile["country"]),
        original_request=conv.original_request or "",
        summary=summary, verified_facts=facts, policy_decision=decision,
        actions_taken=[ActionRecord.model_validate(a) for a in conv.data.get("actions", [])],
        actions_declined=list(conv.data.get("declined", [])),
        open_questions=open_questions or [],
        suggested_queue=(decision.queue if decision and decision.queue else "disputas"),
        suggested_agent_language=conv.language,
        conversation_id=conv.conversation_id, trace_id=conv.trace_id,
    )
    try:
        with turn.tracer.span("tool.create_handoff"):
            ref = handoff.create_handoff(session, package)
    except Exception:
        # Último recurso: ni el handoff se pudo guardar. No inventar nada; pedir que reintente.
        conv.state = "CERRAR"
        return turn.say("tool_failure")
    conv.state = "HANDOFF"
    turn.handoff_id = ref.handoff_id
    if reason == "TOOL_FAILURE":
        turn.say("tool_failure")
    elif cancelled:
        turn.say("cancelled_handoff")
    elif case is not None:
        turn.say("handoff", case_id=case.case_id)
    else:
        turn.say("handoff_no_case")
    turn.ui = ChatUI(type="handoff", handoff_id=ref.handoff_id, queue=package.suggested_queue)
