"""Contratos compartidos (docs/design.md, secciones 2 a 6).

Fuente única en código de los modelos del diseño. El frontend los refleja en
frontend/src/api/types.ts. Si cambias algo aquí, actualiza design.md y types.ts
en el mismo PR.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

# --- Dominios -----------------------------------------------------------------

Language = Literal["es", "pt"]
Currency = Literal["ARS", "COP", "USD"]
Intent = Literal[
    "cargo_no_reconocido",
    "cobro_incorrecto",
    "tarjeta_comprometida",
    "estado_disputa",
    "fuera_de_alcance",
]
DisputeType = Literal["cargo_no_reconocido", "cobro_incorrecto", "fraude"]
Priority = Literal["critical", "high", "medium", "low"]
Queue = Literal["fraude", "disputas", "general"]
Role = Literal["customer", "agent"]
TransactionStatus = Literal["Approved", "Declined", "Pending", "Reversed"]
CaseStatus = Literal["Open", "In Process", "Escalated", "Resolved", "Closed", "Rejected"]
CardState = Literal["Active", "Blocked", "Suspended", "Closed"]
RuleId = Literal["R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "R11", "R12"]
PolicyAction = Literal["REAUTH", "NOT_FOUND", "INFORM", "AUTO_REGISTER", "FRAUD", "ESCALATE"]
ConversationState = Literal[
    "INICIO",
    "PEDIR_REAUTENTICACION",
    "ENTENDER",
    "ACLARAR",
    "ABSTENERSE",
    "INFORMAR_ESTADO",
    "IDENTIFICAR_TRANSACCION",
    "EVALUAR",
    "CONFIRMAR_ACCION",
    "EJECUTAR",
    "VERIFICAR",
    "CERRAR",
    "HANDOFF",
]

INTENT_TO_DISPUTE_TYPE: dict[str, DisputeType] = {
    "cargo_no_reconocido": "cargo_no_reconocido",
    "cobro_incorrecto": "cobro_incorrecto",
    "tarjeta_comprometida": "fraude",
}

# --- Sesión (sección 7) ---------------------------------------------------------


class Session(BaseModel):
    session_id: str
    customer_id: str  # o agent_id cuando role == "agent"
    role: Role
    language: Language
    expires_at: datetime


# --- NLU (sección 2) --------------------------------------------------------------


class NLUResult(BaseModel):
    language: Language
    intent: Intent
    intent_confidence: float = Field(ge=0, le=1)
    abstain: bool
    amount: float | None = None
    currency: Currency | None = None
    date_from: date | None = None
    date_to: date | None = None
    merchant_hint: str | None = None
    selected_option: int | None = None
    confirmation: Literal["yes", "no"] | None = None
    suspected_injection: bool = False
    extractor: Literal["llm", "rules"]
    model_version: str


# --- Política (sección 3) -----------------------------------------------------------


class Decision(BaseModel):
    rule_id: RuleId
    action: PolicyAction
    reason: str
    priority: Priority | None = None
    queue: Queue | None = None
    policy_version: str


# --- Herramientas (sección 4) ---------------------------------------------------------


class TransactionView(BaseModel):
    """Lo que puede ver el cliente."""

    transaction_id: str
    business_date: date
    amount: float
    currency: Currency
    merchant_name: str | None
    transaction_type: str
    channel: str
    status: TransactionStatus
    product_id: str
    card_mask: str | None


class TransactionRisk(BaseModel):
    """Solo para el motor de política. Nunca al cliente ni al LLM."""

    transaction_id: str
    amount_usd: float
    fraud_score: float | None


class DisputeCase(BaseModel):
    case_id: str
    customer_id: str
    transaction_id: str
    product_id: str
    dispute_type: DisputeType
    category: str
    subcategory: str
    priority: Priority
    status: CaseStatus
    rule_id: RuleId
    policy_version: str
    channel: Literal["chat"] = "chat"
    language: Language
    created_at: datetime
    sla_due_at: datetime


class CreateCaseResult(BaseModel):
    case: DisputeCase
    created: bool


class CardStatus(BaseModel):
    product_id: str
    card_mask: str | None
    status: CardState
    blocked_at: datetime | None = None


class BlockResult(BaseModel):
    product_id: str
    status: CardState
    blocked_at: datetime


class HandoffRef(BaseModel):
    handoff_id: str


class ToolError(Exception):
    """Error tipado de herramienta. NOT_FOUND cubre 'no existe' y 'no es tuyo'."""

    def __init__(
        self,
        code: Literal["NOT_FOUND", "INVALID_CONFIRMATION", "TIMEOUT", "CONFLICT", "INTERNAL"],
        message: str = "",
    ):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class PendingAction(BaseModel):
    pending_action_id: str
    action: Literal["create_dispute_case", "block_card"]
    target_id: str  # transaction_id o product_id
    session_id: str
    summary: str
    expires_at: datetime
    used: bool = False


# --- Handoff (sección 5) ---------------------------------------------------------------


class VerifiedFact(BaseModel):
    fact: str
    value: str | float | int
    source: Literal["transactions", "cards", "customer_profile", "cases", "complaints"]


class ActionRecord(BaseModel):
    action: Literal["create_dispute_case", "block_card"]
    status: Literal["verified", "failed", "not_attempted"]
    at: datetime | None = None


class HandoffCustomer(BaseModel):
    customer_id: str
    segment: str
    country: str


class HandoffPackage(BaseModel):
    handoff_id: str
    case_id: str | None
    created_at: datetime
    handoff_reason: Literal[
        "POLICY_ESCALATION",
        "CLARIFICATION_EXHAUSTED",
        "NO_TRANSACTION_FOUND",
        "TOOL_FAILURE",
        "CUSTOMER_REQUEST",
    ]
    priority: Priority
    sla_due_at: datetime | None
    language: Language
    customer: HandoffCustomer
    original_request: str
    summary: str
    verified_facts: list[VerifiedFact]
    policy_decision: Decision | None
    actions_taken: list[ActionRecord]
    actions_declined: list[str]
    open_questions: list[str]
    suggested_queue: Queue
    suggested_agent_language: Language
    conversation_id: str
    trace_id: str


class HandoffSummary(BaseModel):
    handoff_id: str
    case_id: str | None
    priority: Priority
    suggested_queue: Queue
    language: Language
    created_at: datetime
    handoff_reason: str


# --- API (sección 6) --------------------------------------------------------------------


class DemoCustomer(BaseModel):
    customer_id: str
    display_name: str
    segment: str
    country: str
    suggested_language: Language
    scenario: str


class DemoCustomersResponse(BaseModel):
    customers: list[DemoCustomer]


class LoginRequest(BaseModel):
    customer_id: str
    otp: str


class AgentLoginRequest(BaseModel):
    agent_id: str
    otp: str


class LoginCustomer(BaseModel):
    customer_id: str
    segment: str
    country: str
    language: Language


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    customer: LoginCustomer | None = None  # None en el login del agente


class UIAction(BaseModel):
    type: Literal["select_transaction", "confirm", "cancel"]
    transaction_id: str | None = None
    pending_action_id: str | None = None


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str | None = Field(default=None, max_length=2000)
    ui_action: UIAction | None = None


class ChatMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    text: str
    source: Literal["llm", "template"]


class PendingActionView(BaseModel):
    pending_action_id: str
    action: Literal["create_dispute_case", "block_card"]
    summary: str
    expires_at: datetime


class ChatUI(BaseModel):
    type: Literal["transaction_options", "confirmation", "case_created", "handoff", "reauth"]
    options: list[TransactionView] | None = None
    pending_action: PendingActionView | None = None
    case: DisputeCase | None = None
    handoff_id: str | None = None
    queue: Queue | None = None


class TurnAudit(BaseModel):
    """Vista del turno para el panel de auditoría. Sin fraud_score para el rol customer."""

    intent: Intent | None
    intent_confidence: float | None
    rule_id: RuleId | None
    tools: list[str]
    latency_ms: int
    fallback_used: bool


class ChatResponse(BaseModel):
    conversation_id: str
    turn_id: int
    trace_id: str
    state: ConversationState
    language: Language
    messages: list[ChatMessage]
    ui: ChatUI | None = None
    case: DisputeCase | None = None
    handoff_id: str | None = None
    audit: TurnAudit


class CasesResponse(BaseModel):
    cases: list[DisputeCase]


class HandoffsResponse(BaseModel):
    handoffs: list[HandoffSummary]


class Span(BaseModel):
    name: str
    latency_ms: int
    output: dict | None = None
    model: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None
    error: str | None = None


class TraceTurn(BaseModel):
    turn_id: int
    state_from: ConversationState
    state_to: ConversationState
    spans: list[Span]
    # Resumen del turno (Fase 7). Lo leen los graders de la evaluación: no cambiar sin avisar.
    started_at: datetime | None = None
    latency_ms: int | None = None
    input_kind: Literal["message", "ui_action"] | None = None
    language: Language | None = None
    intent: Intent | None = None
    intent_confidence: float | None = None
    rule_id: RuleId | None = None
    transaction_id: str | None = None      # la transacción en juego en este turno (si ya se identificó)
    actions: list[ActionRecord] = []          # acciones de ESTE turno, con verified/failed
    case_id: str | None = None
    handoff_id: str | None = None
    tokens_in: int = 0                         # suma de los spans de LLM
    tokens_out: int = 0
    cost_usd: float = 0.0
    versions: dict[str, str] | None = None     # policy_version, intent_model, llm_model, data_source


class Trace(BaseModel):
    trace_id: str
    conversation_id: str
    customer_id: str
    turns: list[TraceTurn]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    policy_version: str
    intent_model: str
    llm_model: str
    data_manifest: str | None


class ErrorBody(BaseModel):
    code: Literal[
        "UNAUTHENTICATED",
        "SESSION_EXPIRED",
        "FORBIDDEN",
        "NOT_FOUND",
        "VALIDATION_ERROR",
        "INTERNAL",
    ]
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
