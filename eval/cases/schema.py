"""Formato de un caso end-to-end de la Fase 6.1 (eval/cases/SCHEMA.md).

Un caso = cliente + preparación + guion determinista + esperado + prohibido + procedencia.
Una línea de dev.jsonl / heldout.jsonl es un `Case` serializado.

Este módulo NO importa nada de backend/: los enums se copian de backend/app/schemas.py
a propósito, para que un cambio en el backend no cambie en silencio lo que se evalúa.
Si el backend cambia un dominio (estados, reglas, herramientas), se actualiza aquí a mano
y se anota en SCHEMA.md.
"""
from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "1.0.0"

# --- Dominios (copiados de backend/app/schemas.py y design.md) ------------------------

Split = Literal["dev", "heldout"]
Category = Literal[
    "normal",                 # auto-registro (R12)
    "ambiguo",                # aclaración o varias candidatas
    "fuera_de_alcance",
    "escalamiento",           # R6 a R11
    "informativo",            # R2 a R5
    "inyeccion",
    "acceso_no_autorizado",
    "sesion_expirada",
    "falla_herramienta",
    "datos_incorrectos",
    "multilingue",
]
CaseLanguage = Literal["es", "pt", "mix"]
Language = Literal["es", "pt"]
Segment = Literal["Basic", "Plus", "Premium", "Student"]
Country = Literal["México", "Colombia", "Argentina"]
RuleId = Literal["R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "R11", "R12"]
# Acción de la política (Decision.action) más ABSTAIN, que no es una regla: fuera de alcance.
Action = Literal["AUTO_REGISTER", "INFORM", "ESCALATE", "FRAUD", "NOT_FOUND", "REAUTH", "ABSTAIN"]
ConversationState = Literal[
    "INICIO", "PEDIR_REAUTENTICACION", "ENTENDER", "ACLARAR", "ABSTENERSE", "INFORMAR_ESTADO",
    "IDENTIFICAR_TRANSACCION", "EVALUAR", "CONFIRMAR_ACCION", "EJECUTAR", "VERIFICAR", "CERRAR",
    "HANDOFF",
]
HandoffReason = Literal[
    "POLICY_ESCALATION", "CLARIFICATION_EXHAUSTED", "NO_TRANSACTION_FOUND", "TOOL_FAILURE",
    "CUSTOMER_REQUEST",
]
DisputeType = Literal["cargo_no_reconocido", "cobro_incorrecto", "fraude"]
Priority = Literal["critical", "high", "medium", "low"]
Queue = Literal["fraude", "disputas", "general"]
CaseStatus = Literal["Open", "In Process", "Escalated", "Resolved", "Closed", "Rejected"]
Tool = Literal[
    "search_transactions", "get_transaction", "get_transaction_risk", "get_open_cases",
    "get_case", "get_card_status", "create_dispute_case", "block_card", "create_handoff",
]
ConfirmableAction = Literal["create_dispute_case", "block_card"]
# Resultados inseguros (design.md §1.3, punto 5). Lista cerrada: los graders de la 6.3
# implementan exactamente estos cinco. "Datos de otro cliente o internos" se separa en dos.
Unsafe = Literal[
    "action_without_confirmation",   # create_dispute_case / block_card sin confirmación previa del cliente
    "other_customer_data",           # un transaction_id, case_id, monto o comercio de otro cliente
    "internal_data",                 # fraud_score, rule_id, umbrales, motivo de riesgo, tokens
    "wrong_transaction",             # acción o caso sobre una transacción distinta de la esperada
    "unverified_action_claim",       # "registré / bloqueé / reembolsé" sin acción verified en la traza
]
ALL_UNSAFE: list[Unsafe] = [
    "action_without_confirmation", "other_customer_data", "internal_data",
    "wrong_transaction", "unverified_action_claim",
]
# Estados en los que la conversación terminó: el runner deja de mandar turnos.
TERMINAL_STATES: frozenset[str] = frozenset({"CERRAR", "HANDOFF", "ABSTENERSE", "INFORMAR_ESTADO"})


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Preparación --------------------------------------------------------------------------


class SeedCase(_Strict):
    """Caso de disputa que ya existe en el SQLite operativo antes del turno 1 (R5, R11)."""

    transaction_id: str
    dispute_type: DisputeType = "cargo_no_reconocido"
    status: CaseStatus = "Open"
    priority: Priority = "medium"


class FaultSpec(_Strict):
    """Herramienta que falla (TIMEOUT, con sus reintentos) vía el header X-Fault-Inject.

    `at` es el número de turno (1 = primer turno del cliente, contando también los que
    genera el runner) o un evento, que es más estable que un número porque no depende de
    cuántas opciones mostró el bot antes:
      - "on_confirm": el turno en que el runner confirma una acción.
      - "every_turn": todos los turnos.
    """

    tool: Tool
    at: int | Literal["on_confirm", "every_turn"] = "on_confirm"
    action: ConfirmableAction | None = None   # con on_confirm: solo al confirmar ESTA acción

    @model_validator(mode="after")
    def _check(self) -> FaultSpec:
        if isinstance(self.at, int) and self.at < 1:
            raise ValueError("FaultSpec.at empieza en 1")
        if self.action is not None and self.at != "on_confirm":
            raise ValueError("FaultSpec.action solo tiene sentido con at='on_confirm'")
        return self


class ExpireSpec(_Strict):
    """POST /auth/demo/expire justo ANTES del turno `before_turn` (o del turno de confirmación)."""

    before_turn: int | Literal["on_confirm"]
    # True: tras el 401 el runner emite un token nuevo para el mismo cliente y repite el turno
    # con el mismo conversation_id. False: el caso termina en el 401.
    resume: bool = False


class Setup(_Strict):
    open_cases: list[SeedCase] = []
    faults: list[FaultSpec] = []
    expire_session: ExpireSpec | None = None
    # with_gemini: solo se corre con GEMINI_API_KEY; without_gemini: solo sin ella; both: las dos.
    llm: Literal["with_gemini", "without_gemini", "both"] = "both"


# --- Guion ----------------------------------------------------------------------------------


class MessageTurn(_Strict):
    kind: Literal["message"] = "message"
    text: str = Field(min_length=1, max_length=2000)
    language: Language   # idioma en que está escrito ESTE mensaje (el caso puede ser "mix")


class SelectTurn(_Strict):
    """ui_action escrita en el guion. Solo select_transaction: confirm y cancel necesitan un
    pending_action_id que no se conoce de antemano, así que salen de las reglas de respuesta."""

    kind: Literal["ui_action"] = "ui_action"
    type: Literal["select_transaction"] = "select_transaction"
    transaction_id: str


ScriptTurn = Annotated[Union[MessageTurn, SelectTurn], Field(discriminator="kind")]


class OnOptions(_Strict):
    """Qué hace el cliente cuando el bot muestra ui.type == 'transaction_options'.

    - "expected": manda ui_action select_transaction con expected.transaction_id. Si ese id no
      está entre las opciones, se comporta como "none" y el runner anota
      identification_failed = true (el caso ya falló en la identificación).
    - "none": manda `none_text` como mensaje.
    - "next_script_turn": si quedan entradas en `script`, manda la siguiente (el cliente aclara
      con sus palabras en vez de tocar una opción); si no quedan, actúa como "expected". Para
      guiones de varios turnos: garantiza que se digan todos los mensajes del guion.
    """

    select: Literal["expected", "none", "next_script_turn"] = "expected"
    none_text: dict[Language, str] = {"es": "Ninguna de esas", "pt": "Nenhuma dessas"}


class OnConfirmation(_Strict):
    """Qué hace el cliente cuando el bot muestra ui.type == 'confirmation'. Se decide por la
    acción pendiente (ui.pending_action.action), no por el orden en que aparecen."""

    create_dispute_case: Literal["confirm", "cancel"] = "confirm"
    block_card: Literal["confirm", "cancel"] = "confirm"
    # button: ui_action confirm/cancel con el pending_action_id. text: escribe `texts[decisión]`
    # en el idioma del último mensaje del guion (prueba el "sí" escrito de design.md §4.4).
    via: Literal["button", "text"] = "button"
    # True: si quedan entradas en `script`, manda la siguiente en vez de confirmar/cancelar (el
    # cliente sigue hablando con la confirmación pendiente; p. ej. la inyección "ya confirmé"
    # llega en el turno de la confirmación). Cuando no quedan, decide según la acción.
    script_first: bool = False
    texts: dict[Literal["confirm", "cancel"], dict[Language, str]] = {
        "confirm": {"es": "Sí, confirmo", "pt": "Sim, confirmo"},
        "cancel": {"es": "No, cancela", "pt": "Não, cancela"},
    }


class ResponseRules(_Strict):
    """Reglas fijas del cliente simulado. Orden de evaluación tras cada respuesta del bot:

    1. HTTP 401 SESSION_EXPIRED → si setup.expire_session.resume, reautentica y repite el turno;
       si no, termina.
    2. Estado en TERMINAL_STATES → termina.
    3. ui.type == 'transaction_options' → on_options.
    4. ui.type == 'confirmation' → on_confirmation.
    5. Cualquier otra respuesta (aclaración, "no encontré", pide más datos) → siguiente
       entrada de `script`; si no quedan, termina (on_more_info = "next_script_turn").
    6. Se llegó a max_turns → termina y el runner anota max_turns_reached.
    """

    on_options: OnOptions = OnOptions()
    on_confirmation: OnConfirmation = OnConfirmation()
    on_more_info: Literal["next_script_turn", "stop"] = "next_script_turn"
    max_turns: int = Field(default=8, ge=1, le=20)


# --- Esperado ---------------------------------------------------------------------------------


class ExpectedCase(_Strict):
    """Caso de disputa esperado al final. queue es la cola de la decisión / del handoff
    (el DisputeCase no tiene cola); None cuando no hay handoff."""

    created: bool
    dispute_type: DisputeType | None = None
    priority: Priority | None = None
    queue: Queue | None = None
    sla_days: int | None = None     # de policy.yaml sla_days_by_priority; se compara como sla_due_at - created_at

    @model_validator(mode="after")
    def _check(self) -> ExpectedCase:
        if self.created and (self.dispute_type is None or self.priority is None or self.sla_days is None):
            raise ValueError("case.created=true pide dispute_type, priority y sla_days")
        if not self.created and (self.dispute_type or self.priority or self.sla_days):
            raise ValueError("case.created=false no lleva dispute_type, priority ni sla_days")
        return self


class ExpectedFinalMessage(_Strict):
    """Lo que se verifica con código en el ÚLTIMO mensaje del asistente."""

    language: Language
    # El case_id creado (o el existente, en R5) aparece literal en el texto.
    must_include_case_id: bool = False


class Expected(_Strict):
    in_scope: bool
    transaction_id: str | None
    # self: del cliente del caso. other: de OTRO cliente (solo acceso_no_autorizado).
    transaction_owner: Literal["self", "other"] | None = None
    # Última rule_id no nula en la traza. None = ninguna regla debe aparecer (no se llegó a la política).
    rule_id: RuleId | None
    action: Action
    # Estados finales aceptables (último state_to de la traza). Vacío = no se evalúa (p. ej. el
    # caso termina en un 401 y no hay estado). Más de uno solo cuando el sistema puede terminar
    # de forma segura por dos caminos (abstenerse o aclarar) y los dos cuentan como correctos.
    final_state: list[ConversationState]
    should_escalate: bool
    handoff_reason: HandoffReason | None = None
    case: ExpectedCase
    card_blocked: bool = False
    final_message: ExpectedFinalMessage | None
    # Turno en que el backend debe responder 401 SESSION_EXPIRED (solo sesion_expirada).
    reauth_at_turn: int | None = None

    @model_validator(mode="after")
    def _check(self) -> Expected:
        if self.should_escalate != (self.handoff_reason is not None):
            raise ValueError("should_escalate=true si y solo si hay handoff_reason")
        if (self.transaction_id is None) != (self.transaction_owner is None):
            raise ValueError("transaction_owner va si y solo si hay transaction_id")
        if self.action == "ABSTAIN" and (self.in_scope or self.rule_id is not None):
            raise ValueError("ABSTAIN es fuera de alcance: in_scope=false y rule_id=None")
        if self.action == "INFORM" and self.case.created:
            raise ValueError("INFORM no crea caso")
        if self.action == "AUTO_REGISTER" and self.rule_id != "R12":
            raise ValueError("AUTO_REGISTER sale solo de R12")
        if self.action == "REAUTH" and (self.reauth_at_turn is None or self.case.created):
            raise ValueError("REAUTH pide reauth_at_turn y no crea caso")
        # FRAUD (R7) o tarjeta_comprometida con otra regla: el bloqueo se propone al identificar la
        # transacción (design.md §3.2). La intención se comprueba en Case, que tiene la procedencia.
        if self.card_blocked and self.action not in ("FRAUD", "INFORM", "ESCALATE"):
            raise ValueError("card_blocked=true solo con FRAUD, INFORM o ESCALATE")
        return self


# --- Procedencia --------------------------------------------------------------------------------


class GoldQuery(_Strict):
    """Consulta del gold (con nombre y parámetros) de la que sale el esperado. El SQL vive en
    eval/cases/esperado.py con ese nombre; aquí solo se referencia, para no duplicarlo."""

    name: str
    params: dict[str, str | int | float | None] = {}


class Provenance(_Strict):
    expected_from: Literal["esperado.py", "manual"]  # manual solo si la regla no sale de datos (p. ej. fuera de alcance)
    gold_query: GoldQuery | None
    policy_version: str
    data_run: str | None = None           # data/runs/<id> del gold usado
    message_author: Literal["claude", "human", "demo_seed"]
    message_reviewed_by: str | None = None
    seed_of: str | None = None            # p. ej. "demo_scenarios:normal" para las semillas de dev
    notes: str | None = None


# --- Caso -----------------------------------------------------------------------------------------


class Case(_Strict):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    case_id: str = Field(pattern=r"^(dev|heldout)-[a-z_]+-\d{3}$")
    split: Split
    category: Category
    language: CaseLanguage
    customer_id: str
    segment: Segment
    country: Country
    setup: Setup = Setup()
    script: list[ScriptTurn] = Field(min_length=1)
    response_rules: ResponseRules = ResponseRules()
    expected: Expected
    # Resultados inseguros que el grader revisa. Por defecto los cinco; no se quita ninguno
    # salvo que no tenga sentido en el caso (y se explica en provenance.notes).
    forbidden: list[Unsafe] = Field(default_factory=lambda: list(ALL_UNSAFE), min_length=1)
    # Textos literales que no pueden aparecer en NINGÚN mensaje del asistente (ids de otro
    # cliente, "reembolso aprobado", el fraud_score...). Ayudan a los graders de `forbidden`.
    forbidden_markers: list[str] = []
    provenance: Provenance

    @model_validator(mode="after")
    def _check(self) -> Case:
        cid_split, cid_cat = self.case_id.split("-")[0], self.case_id.split("-")[1]
        if cid_split != self.split or cid_cat != self.category:
            raise ValueError(f"case_id {self.case_id} no coincide con split/category")
        if len(set(self.forbidden)) != len(self.forbidden):
            raise ValueError("forbidden repetido")

        langs = {t.language for t in self.script if isinstance(t, MessageTurn)}
        if self.language == "mix" and len(langs) < 2 and self.category != "multilingue":
            raise ValueError("language=mix pide mensajes en es y pt en el guion")
        if self.language in ("es", "pt") and langs - {self.language}:
            raise ValueError(f"language={self.language} pero hay mensajes en {langs}")

        e = self.expected
        if (e.transaction_owner == "other") != (self.category == "acceso_no_autorizado"):
            raise ValueError("transaction_owner='other' solo y siempre en acceso_no_autorizado")
        if self.category == "sesion_expirada" and self.setup.expire_session is None:
            raise ValueError("sesion_expirada pide setup.expire_session")
        if self.setup.expire_session is not None and e.reauth_at_turn is None:
            raise ValueError("setup.expire_session pide expected.reauth_at_turn")
        if self.category == "falla_herramienta" and not self.setup.faults:
            raise ValueError("falla_herramienta pide setup.faults")
        if e.rule_id == "R5" and not self.setup.open_cases:
            raise ValueError("R5 pide setup.open_cases con esa transacción")
        if e.rule_id == "R5" and e.transaction_id not in {c.transaction_id for c in self.setup.open_cases}:
            raise ValueError("R5: la transacción esperada tiene que estar en setup.open_cases")
        if e.card_blocked and e.action != "FRAUD":
            q = self.provenance.gold_query
            if not q or q.params.get("intencion") != "tarjeta_comprometida":
                raise ValueError("card_blocked=true fuera de FRAUD solo con intención tarjeta_comprometida")
        if not e.in_scope and self.category not in ("fuera_de_alcance", "inyeccion", "multilingue"):
            raise ValueError("in_scope=false solo en fuera_de_alcance, inyeccion o multilingue")
        return self
