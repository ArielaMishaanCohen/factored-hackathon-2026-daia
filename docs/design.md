# Diseño · Intake de disputas de transacciones

**Versión:** 1.0 · 28 de septiembre de 2026
**Estado:** contratos de referencia de la implementación. Decisiones asociadas: D1.5–D1.10 en `decisions.md`. Los ejemplos de política son históricos; la configuración vigente es `config/policy.yaml` v1.3.0.
**Complementa:** `decisions_fase_0.md` (por qué este flujo), `decisions.md` (qué se decidió y por qué).

---

## 0. Referencias de implementación

Los contratos Pydantic viven en `backend/app/schemas.py`; `tests/test_api_contract.py` verifica la API y `frontend/src/api/types.ts` refleja los tipos. La política efectiva y sus umbrales están en `config/policy.yaml`, no en los ejemplos iniciales de este documento. La calibración y el desempeño final se documentan en [contratos de datos](data_contracts.md), [model card](../ml/intent/model_card.md) y [reporte final](eval_report.md).

---

## 1. Alcance

### 1.1 Qué hace el sistema

Un asistente que recibe reclamos por cargos en **español y portugués**, identifica la transacción del cliente autenticado, aplica una política determinista y, según el resultado:

1. **Registra el caso de disputa** con confirmación explícita del cliente, lo verifica y le da número de caso y SLA.
2. **Informa** sin crear caso cuando no corresponde disputar (transacción rechazada, pendiente, ya revertida o ya disputada).
3. **Escala a un humano** (fraude, zona gris, monto alto, riesgo desconocido, reclamante frecuente, aclaración agotada, falla de herramienta) con un paquete de handoff estructurado.
4. **Propone bloquear la tarjeta** (con confirmación) cuando hay fraude probable o la tarjeta está comprometida.
5. **Consulta el estado** de disputas abiertas del cliente.
6. **Se abstiene** ante pedidos fuera de alcance y explica qué sí puede hacer.

### 1.2 Qué NO hace

- Reembolsos, reversos o cualquier movimiento de dinero. El sistema **registra** la disputa; no la resuelve a favor del cliente.
- Otros flujos: préstamos, límites, PIN, saldo, productos nuevos, rechazos de tarjeta. Los reconoce como `fuera_de_alcance` y se abstiene.
- Desbloquear tarjetas (solo bloquear, y siempre con confirmación).
- Identidad real, canales reales (WhatsApp, voz) ni conexión con un core bancario. Todo es simulado sobre los datos del reto.
- Mostrar al cliente información interna de riesgo (`fraud_score`, reglas de fraude).

### 1.3 Qué significa "resuelto" (D1.6)

Un caso **en alcance** cuenta como **resuelto de forma automática y segura** si, sin intervención humana:

1. Se identificó la **transacción correcta**.
2. Se aplicó la **regla de política esperada** (la primera que aplica según la sección 3).
3. Si correspondía, el caso quedó **creado y verificado** (relectura posterior a la escritura) con tipo, prioridad y SLA correctos.
4. El cliente recibió el **número de caso** o la **información correcta** (en su idioma).
5. **No hubo ningún resultado inseguro:** acción sin confirmación, divulgación de datos de otro cliente o de datos internos, transacción equivocada o afirmación de una acción no verificada.

Un escalamiento correcto **no** cuenta como resolución automática; se mide aparte como calidad de escalamiento.

### 1.4 Fecha de referencia

Los datos son estáticos (terminan a mediados de 2026). El sistema usa una **fecha de referencia** fija (`REFERENCE_DATE` en `policy.yaml`) como "hoy" para ventanas de búsqueda, ventana de reclamo y SLA. Valor: **2026-06-17**, la última `process_date` de `transactions_12m`. Nadie usa `datetime.now()` para lógica de negocio.

---

## 2. Taxonomía de intenciones (D1.5)

El clasificador (Fase 4) devuelve **una** intención y una confianza. Si la confianza es menor que **τ_intención**, el orquestador no actúa: **aclara** (máximo 2 veces) y luego hace handoff.

| Intención | Definición | Ejemplo ES | Ejemplo PT | Qué hace el orquestador |
| :-- | :-- | :-- | :-- | :-- |
| `cargo_no_reconocido` | El cliente no reconoce un cargo; no menciona robo ni pérdida de la tarjeta | "No reconozco un cargo de 1.200 pesos" | "Não reconheço uma cobrança de 200 reais" | Identificar transacción → política |
| `cobro_incorrecto` | Reconoce el comercio, pero el cobro está mal: duplicado, monto distinto, cobro después de cancelar | "Me cobraron dos veces el súper" | "Fui cobrado duas vezes" | Identificar transacción → política |
| `tarjeta_comprometida` | Robo, pérdida, clonación o varias compras que no hizo | "Me robaron la tarjeta y hay compras que no hice" | "Roubaram meu cartão" | Proponer bloqueo + identificar transacciones → R7 |
| `estado_disputa` | Pregunta por un reclamo ya existente | "¿Cómo va mi reclamo?" | "Como está minha contestação?" | `get_open_cases` → informar |
| `fuera_de_alcance` | Cualquier otro pedido bancario o no bancario | "Quiero un préstamo" | "Quero aumentar meu limite" | Abstenerse con plantilla que explica qué sí puede hacer |
| *(abstención)* | Confianza < τ_intención | "Tengo un problema con mi tarjeta" | "Tenho um problema" | Aclarar (máx. 2) → handoff |

**Reglas de etiquetado** (para el set de la Fase 4; la guía completa está en `ml/intent/labeling_guide.md`):

- Si el cliente menciona robo, pérdida o clonación, gana `tarjeta_comprometida` aunque también diga "no reconozco un cargo".
- Si reconoce el comercio pero el monto o la cantidad de cobros está mal, es `cobro_incorrecto`.
- Un saludo o frase sin contenido ("hola", "ayuda") no es una clase: debe caer en abstención.
- Mezcla de idiomas se etiqueta por intención, no por idioma.

En el set etiquetado existe además la etiqueta `ambiguo` (frases sin intención clara): no es una salida del modelo, sirve para medir la abstención.

**Descartado a propósito:**

- *"Intento de manipulación"* como clase. La defensa contra prompt injection es de **arquitectura** (el LLM no elige herramientas, no ve datos de otros clientes, no emite confirmaciones). La detección se registra como guardia aparte (`suspected_injection` en la extracción), solo para métricas.
- *"Bloquear tarjeta"* como flujo propio. Es una acción dentro del camino de fraude.

**Relación intención → tipo de disputa** (campo `dispute_type` del caso):

| Intención | `dispute_type` |
| :-- | :-- |
| `cargo_no_reconocido` | `cargo_no_reconocido` |
| `cobro_incorrecto` | `cobro_incorrecto` |
| `tarjeta_comprometida` | `fraude` |

**Salida del NLU** (contrato entre B y C):

```python
class NLUResult(BaseModel):
    language: Literal["es", "pt"]
    intent: Literal["cargo_no_reconocido", "cobro_incorrecto", "tarjeta_comprometida",
                    "estado_disputa", "fuera_de_alcance"]
    intent_confidence: float          # 0–1
    abstain: bool                     # intent_confidence < τ_intención
    amount: float | None
    currency: Literal["ARS", "COP", "USD"] | None
    date_from: date | None            # rango inferido de "ayer", "la semana pasada", etc.
    date_to: date | None
    merchant_hint: str | None
    selected_option: int | None       # "la segunda", "a do dia 3"
    confirmation: Literal["yes", "no"] | None   # solo se lee en estado CONFIRMAR
    suspected_injection: bool
    extractor: Literal["llm", "rules"]          # "rules" = fallback sin Gemini
    model_version: str
```

---

## 3. Política de disputas (D1.7)

### 3.1 Principios

- La política es **código determinista**, no prosa del LLM. Función pura: `evaluate(transaction, customer_ctx, intent, policy) -> Decision`.
- Reglas en **orden de precedencia**: la primera que aplica gana. Cada decisión guarda `rule_id`, motivo y `policy_version`.
- Los umbrales viven en `config/policy.yaml`, versionado. Cambiar un umbral sube la versión de la política.

### 3.2 Reglas

| # | Condición | Acción (`Decision.action`) | Prioridad del caso | Cola | Evidencia |
| :-: | :-- | :-- | :-: | :-- | :-- |
| R0 | Sesión inválida o expirada | `REAUTH`: pedir reautenticación; no revelar nada | — | — | — |
| R1 | La transacción no es del cliente de la sesión (o no existe) | `NOT_FOUND`: "No encontré esa transacción" (mismo mensaje en ambos casos) | — | — | Autorización |
| R2 | `status = Declined` | `INFORM`: no hubo cargo; sin caso | — | — | 221k `Declined` |
| R3 | `status = Pending` | `INFORM`: puede no asentarse; sin caso | — | — | 88k `Pending` |
| R4 | `status = Reversed` | `INFORM`: ya se revirtió; sin caso | — | — | 45k `Reversed` |
| R5 | Ya hay un caso abierto para esa transacción | `INFORM`: dar número y estado; no duplicar | — | — | Idempotencia |
| R6 | Transacción más vieja que **τ_ventana** días | `ESCALATE` | Media | `disputas` | Política sintética documentada |
| R7 | Intención `tarjeta_comprometida` **o** `fraud_score ≥ τ_alto` | `FRAUD`: proponer bloqueo (confirmación) + caso + handoff | Crítica | `fraude` | Score ≥ 40 → 100 % fraude |
| R8 | `fraud_score` nulo | `ESCALATE` (riesgo desconocido) | Alta | `disputas` | 20 % nulos |
| R9 | `τ_bajo ≤ fraud_score < τ_alto` | `ESCALATE` (zona gris) | Alta | `fraude` | 37 % fraude en 30–39 |
| R10 | `amount_usd > τ_monto[transaction_type]` | `ESCALATE` | Alta | `disputas` | p90/p95 por tipo |
| R11 | Cliente con ≥ **τ_k** disputas en 90 días, **en cualquier estado** (`prior_complaints_90d` del banco + casos de este canal creados en los últimos `repeat_window_days`) | `ESCALATE` | Media | `disputas` | Casos + `complaints` por cliente |
| R12 | Ninguna de las anteriores | `AUTO_REGISTER`: confirmación → crear → verificar → número + SLA | Media | — | — |

**Notas:**

- R0 y R1 se aplican antes de mirar cualquier dato de la transacción. R1 nunca confirma que un `transaction_id` existe.
- Intención `tarjeta_comprometida`: si no se identificó un cargo específico, se ofrece primero el bloqueo sin exigir una transacción. Si el cliente tiene varias tarjetas, se identifica la reportada por sus últimos cuatro dígitos (solo tarjetas propias); luego se pide confirmación explícita y se verifica el bloqueo. No se crea una disputa automáticamente: se invita al cliente a reportar cargos solo si no los reconoce. Si ya identificó un cargo concreto, se conserva el flujo de política y confirmaciones existente. Una tarjeta ya bloqueada no se vuelve a bloquear.
- En R6–R11 **sí** se crea el caso (con la prioridad de la tabla) antes del handoff, con confirmación del cliente. Si el cliente no confirma, se hace handoff sin caso.
- `fraud_score` y el motivo de riesgo **no** se muestran al cliente ni se envían al LLM de redacción. El cliente solo ve "tu caso requiere revisión de un especialista".

### 3.3 `config/policy.yaml`

El archivo es la fuente; esta copia es la versión 1.0.0.

```yaml
# Política de disputas · fuente única de umbrales (docs/design.md, sección 3)
# Cambiar cualquier valor sube policy_version. Los valores τ son iniciales:
# A y B los calibran en las Fases 2 y 4 y anotan la evidencia aquí.

policy_version: "1.0.0"

# "Hoy" para ventanas y SLA. Última process_date en transactions_12m (2026-06-17).
reference_date: "2026-06-17"

currencies: [ARS, COP, USD]   # no hay MXN: los clientes de México operan en USD

intent:
  tau_intencion: 0.60          # B calibra en val (precisión ≥ 95 %)
  max_clarifications: 2

search:
  lookback_days: 120
  max_results: 5
  amount_tolerance_pct: 2.0

rules:
  claim_window_days: 60        # τ_ventana (R6)
  fraud_score_high: 40         # τ_alto (R7) · score ≥ 40 → 100 % fraude (NOTAS_DATOS §6)
  fraud_score_low: 30          # τ_bajo (R9) · 30–39 → 37 % fraude
  amount_usd_max:              # τ_monto (R10) · p95 de amount_usd por tipo, transactions_12m
    Purchase: 475
    Withdrawal: 476
    Payment: 1904
    Adjustment: 954
    Transfer: 9502
    Deposit: 4755
    default: 1000
  repeat_disputes_k: 3         # τ_k (R11)
  repeat_window_days: 90

# En complaints el SLA incumplido no depende de la prioridad ni de resolution_days
# (uniforme ~20 %), así que no se puede derivar: son valores de política sintética.
sla_days_by_priority:
  critical: 1
  high: 3
  medium: 10
  low: 15

confirmation:
  ttl_seconds: 300
```

### 3.4 Objeto de decisión

```python
class Decision(BaseModel):
    rule_id: Literal["R0","R1","R2","R3","R4","R5","R6","R7","R8","R9","R10","R11","R12"]
    action: Literal["REAUTH", "NOT_FOUND", "INFORM", "AUTO_REGISTER", "FRAUD", "ESCALATE"]
    reason: str                       # texto interno, para traza y handoff
    priority: Literal["critical", "high", "medium", "low"] | None
    queue: Literal["fraude", "disputas", "general"] | None
    policy_version: str
```

### 3.5 Máquina de estados (resumen)

```
INICIO → VERIFICAR_SESIÓN ──(expirada)──→ PEDIR_REAUTENTICACIÓN
   ▼
ENTENDER ──(fuera_de_alcance)──→ ABSTENERSE
   │ ──(abstención)──→ ACLARAR (máx. 2) ──(sigue ambiguo)──→ HANDOFF
   │ ──(estado_disputa)──→ INFORMAR_ESTADO
   ▼
IDENTIFICAR_TRANSACCIÓN
   │ 0 candidatas → pedir más datos (máx. 2) → HANDOFF
   │ 1 candidata  → pedir que confirme que es esa
   │ ≥2           → mostrar opciones (máx. 5) → el cliente elige
   ▼
EVALUAR (política) → INFORMAR | CONFIRMAR_ACCIÓN → EJECUTAR → VERIFICAR → CERRAR | HANDOFF
```

Si la verificación posterior a una acción falla, **no** se le dice al cliente que la acción se hizo: se escala con `handoff_reason = TOOL_FAILURE`.

---

## 4. Contratos de herramientas

### 4.1 Reglas comunes

1. Todas reciben un objeto `Session` (salido del JWT), **nunca** un `customer_id` suelto. El filtro por cliente vive **en la consulta SQL**, no en el orquestador.
2. Devuelven objetos Pydantic tipados. Nunca dataframes ni dicts sueltos.
3. Las de escritura exigen un `confirmation_token` válido y son **idempotentes**.
4. Errores como `ToolError(code, message)` con estos códigos:

   | Código | Cuándo |
   | :-- | :-- |
   | `NOT_FOUND` | No existe **o** no es del cliente (indistinguibles a propósito) |
   | `INVALID_CONFIRMATION` | Token ausente, expirado, ya usado o ligado a otra acción |
   | `TIMEOUT` | La herramienta no respondió a tiempo (también la usa la inyección de fallas) |
   | `CONFLICT` | Estado incompatible (p. ej., bloquear una tarjeta ya bloqueada) |
   | `INTERNAL` | Cualquier otro error |

5. Cada llamada escribe un *span* en la traza: nombre, argumentos (sin datos sensibles), resultado resumido, latencia y error.
6. Timeout por herramienta: 2 s; máximo 2 reintentos con backoff, solo en `TIMEOUT` y solo en lecturas o escrituras idempotentes.

### 4.2 Tipos compartidos

```python
class Session(BaseModel):
    session_id: str
    customer_id: str
    role: Literal["customer", "agent"]
    language: Literal["es", "pt"]      # preferencia inicial; el NLU puede cambiarla por conversación
    expires_at: datetime

class TransactionView(BaseModel):     # lo que puede ver el cliente
    transaction_id: str
    business_date: date
    amount: float
    currency: Literal["ARS", "COP", "USD"]
    merchant_name: str | None          # ~23 % de las filas tiene comercio
    transaction_type: str
    channel: str
    status: Literal["Approved", "Declined", "Pending", "Reversed"]
    product_id: str
    card_mask: str | None              # p. ej. "•••• 4821" si existe; nunca el número completo

class TransactionRisk(BaseModel):     # solo para la política; nunca al cliente ni al LLM
    transaction_id: str
    amount_usd: float
    fraud_score: float | None

class DisputeCase(BaseModel):
    case_id: str                       # "DSP-000123"
    customer_id: str
    transaction_id: str
    product_id: str
    dispute_type: Literal["cargo_no_reconocido", "cobro_incorrecto", "fraude"]
    category: str                      # según complaints: "Transactions" | "Fees"
    subcategory: str                   # "Cargo no reconocido" | "Cobro indebido"
    priority: Literal["critical", "high", "medium", "low"]
    status: Literal["Open", "In Process", "Escalated", "Resolved", "Closed", "Rejected"]
    rule_id: str
    policy_version: str
    channel: Literal["chat"]
    language: Literal["es", "pt"]
    created_at: datetime
    sla_due_at: datetime
```

`DisputeCase` sigue el esquema de `complaints` (categoría, subcategoría, prioridad, estado, SLA) para que un caso nuestro se lea como una queja del banco.

### 4.3 Herramientas

| Herramienta | Tipo | Confirmación | Devuelve | Notas |
| :-- | :-- | :-: | :-- | :-- |
| `search_transactions(session, amount?, currency?, date_from?, date_to?, merchant?)` | Lectura | No | `list[TransactionView]` | Máx. `search.max_results`, solo del cliente, últimos `lookback_days` antes de `reference_date`. Orden: coincidencia de monto, luego fecha descendente |
| `get_transaction(session, transaction_id)` | Lectura | No | `TransactionView` | `NOT_FOUND` si no es del cliente |
| `get_transaction_risk(session, transaction_id)` | Lectura interna | No | `TransactionRisk` | Solo la llama el motor de política |
| `get_open_cases(session)` | Lectura | No | `list[DisputeCase]` | Para R5, R11 y `estado_disputa` |
| `get_case(session, case_id)` | Lectura | No | `DisputeCase` | Verificación posterior a crear |
| `get_card_status(session, product_id)` | Lectura | No | `CardStatus` | Verificación posterior a bloquear |
| `create_dispute_case(session, transaction_id, dispute_type, decision, confirmation_token)` | Escritura | **Sí** | `CreateCaseResult(case, created: bool)` | Idempotente por (`transaction_id`, `dispute_type`): si ya existe, devuelve el existente con `created=false` |
| `block_card(session, product_id, confirmation_token)` | Escritura | **Sí** | `BlockResult(product_id, status, blocked_at)` | Mock: cambia el estado en SQLite, no en gold. Idempotente |
| `create_handoff(session, package)` | Escritura | No | `HandoffRef(handoff_id)` | Valida `HandoffPackage` (sección 5); rechaza si falta un campo obligatorio |

```python
class CardStatus(BaseModel):
    product_id: str
    card_mask: str | None
    status: Literal["Active", "Blocked", "Suspended", "Closed"]
    blocked_at: datetime | None
```

### 4.4 Tokens de confirmación

- El orquestador guarda la acción propuesta como `PendingAction(pending_action_id, action, transaction_id | product_id, session_id, expires_at, used)`.
- La UI solo conoce el `pending_action_id` (botones Confirmar/Cancelar). Un "sí" escrito también vale, pero **solo** cuando la conversación está en estado `CONFIRMAR_ACCIÓN`.
- Al confirmar, el orquestador valida la acción pendiente (misma sesión, no expirada, no usada) y **recién entonces** emite el `confirmation_token`: firmado (HMAC con `JWT_SECRET`), ligado a acción + objeto + sesión, TTL de `confirmation.ttl_seconds`, de un solo uso.
- **El LLM nunca ve, genera ni recibe** ni el token ni el `pending_action_id`.

### 4.5 Datos que consumen las herramientas (acuerdo con A)

| Almacén | Tabla | Columnas mínimas | Escribe |
| :-- | :-- | :-- | :-- |
| DuckDB gold (solo lectura) | `dispute_transactions` | `transaction_id`, `customer_id`, `product_id`, `business_date`, `amount`, `currency`, `amount_usd`, `merchant_name`, `transaction_type`, `channel`, `status`, `fraud_score` | Pipeline (A) |
| DuckDB gold | `cards` | `product_id`, `customer_id`, `card_mask`, `status` | Pipeline (A) |
| DuckDB gold | `customer_profile` | `customer_id`, `segment`, `country`, `prior_complaints_90d` | Pipeline (A) |
| DuckDB gold | `demo_customers` | `customer_id`, `display_name` (ficticio), `segment`, `country`, `suggested_language`, `scenario` | Pipeline (A) |
| SQLite operativo | `conversations`, `pending_actions`, `cases`, `card_blocks`, `handoffs`, `traces` | — | Backend (C) |

- `is_fraud` **no** va a gold de servicio: solo se usa en calibración y evaluación.
- Gold no lleva documento, dirección, teléfono ni correo.
- El estado efectivo de una tarjeta es el de `card_blocks` (SQLite) si existe; si no, el de `cards` (gold).
- Los nombres finales de columnas los fija A en `docs/data_contracts.md`; si cambian, se actualiza esta tabla.

---

## 5. Paquete de handoff

Lo que ve el agente humano en la consola. Se construye **solo con hechos verificados** por herramientas; el LLM únicamente redacta `summary`.

### 5.1 Ejemplo

```json
{
  "handoff_id": "HO-000045",
  "case_id": "DSP-000123",
  "created_at": "2026-06-30T15:42:10Z",
  "handoff_reason": "POLICY_ESCALATION",
  "priority": "critical",
  "sla_due_at": "2026-07-01T15:42:10Z",
  "language": "pt",
  "customer": {"customer_id": "CUS-00812", "segment": "Plus", "country": "Mexico"},
  "original_request": "Não reconheço uma compra de 3.500 pesos",
  "summary": "El cliente no reconoce una compra en línea de 3.500 del 27 de junio. Se bloqueó la tarjeta con su confirmación.",
  "verified_facts": [
    {"fact": "transaction_id", "value": "TX-1934027", "source": "transactions"},
    {"fact": "amount", "value": "3500.00 USD", "source": "transactions"},
    {"fact": "business_date", "value": "2026-06-27", "source": "transactions"},
    {"fact": "fraud_score", "value": 47.2, "source": "transactions"}
  ],
  "policy_decision": {"rule_id": "R7", "reason": "fraud_score ≥ 40", "policy_version": "1.0.0"},
  "actions_taken": [
    {"action": "block_card", "status": "verified", "at": "2026-06-30T15:41:55Z"},
    {"action": "create_dispute_case", "status": "verified", "at": "2026-06-30T15:42:05Z"}
  ],
  "actions_declined": [],
  "open_questions": ["¿El cliente aún tiene la tarjeta física?"],
  "suggested_queue": "fraude",
  "suggested_agent_language": "pt",
  "conversation_id": "CONV-7f3a",
  "trace_id": "TR-9b21"
}
```

### 5.2 Modelo

```python
class VerifiedFact(BaseModel):
    fact: str
    value: str | float | int
    source: Literal["transactions", "cards", "customer_profile", "cases", "complaints"]

class ActionRecord(BaseModel):
    action: Literal["create_dispute_case", "block_card"]
    status: Literal["verified", "failed", "not_attempted"]
    at: datetime | None

class HandoffPackage(BaseModel):
    handoff_id: str
    case_id: str | None                # None si el cliente no confirmó crear el caso
    created_at: datetime
    handoff_reason: Literal["POLICY_ESCALATION", "CLARIFICATION_EXHAUSTED",
                            "NO_TRANSACTION_FOUND", "TOOL_FAILURE", "CUSTOMER_REQUEST"]
    priority: Literal["critical", "high", "medium", "low"]
    sla_due_at: datetime | None
    language: Literal["es", "pt"]
    customer: HandoffCustomer          # customer_id, segment, country — sin PII
    original_request: str              # primer mensaje del cliente, tal cual
    summary: str                       # redactado por el LLM; plantilla si el LLM falla
    verified_facts: list[VerifiedFact]
    policy_decision: Decision | None   # None si no se llegó a evaluar (p. ej., aclaración agotada)
    actions_taken: list[ActionRecord]
    actions_declined: list[str]        # acciones que el cliente rechazó
    open_questions: list[str]
    suggested_queue: Literal["fraude", "disputas", "general"]
    suggested_agent_language: Literal["es", "pt"]
    conversation_id: str
    trace_id: str
```

### 5.3 Reglas

- Obligatorios: todo salvo `case_id`, `sla_due_at` y `policy_decision`. `create_handoff` rechaza el paquete si falta uno.
- Cada valor en `verified_facts` debe salir de una lectura de herramienta registrada en la traza. La evaluación lo comprueba con código.
- `summary` pasa por el mismo verificador de hechos que las respuestas al cliente (sección 6.4): si menciona un número, fecha o ID que no está en `verified_facts`, se reemplaza por la plantilla.
- `suggested_agent_language` se apoya en `service_agents.languages` (hay 129 agentes con portugués).

---

## 6. Contrato de la API

Base: `/api`. JSON en ambos sentidos. Autenticación con `Authorization: Bearer <jwt>` en todo salvo `/health` y `/auth/*`.

### 6.1 Errores (formato único)

```json
{"error": {"code": "SESSION_EXPIRED", "message": "La sesión expiró. Vuelve a ingresar."}}
```

| HTTP | `code` | Cuándo |
| :-: | :-- | :-- |
| 401 | `UNAUTHENTICATED` | Falta el token o es inválido |
| 401 | `SESSION_EXPIRED` | Token expirado o revocado; el frontend vuelve al login |
| 403 | `FORBIDDEN` | Rol incorrecto (p. ej., cliente pidiendo `/handoffs`) |
| 404 | `NOT_FOUND` | Recurso inexistente o ajeno |
| 422 | `VALIDATION_ERROR` | Cuerpo inválido |
| 500 | `INTERNAL` | Error no controlado (el chat devuelve un mensaje de fallback, no un 500, siempre que pueda) |

### 6.2 Endpoints

| Método y ruta | Rol | Para qué |
| :-- | :-- | :-- |
| `GET /health` | — | Estado del servicio y versiones |
| `GET /auth/demo-customers` | — | Lista de clientes de demo para el login |
| `POST /auth/login` | — | Cliente de demo + OTP de prueba → JWT |
| `POST /auth/agent-login` | — | Login del agente humano de demo → JWT con rol `agent` |
| `POST /auth/demo/expire` | customer | Revoca la sesión actual (botón "expirar sesión" de la demo) |
| `POST /chat` | customer | Un turno de conversación |
| `GET /cases` | customer, agent | Casos del cliente (customer) o todos (agent) |
| `GET /handoffs` | agent | Cola de handoffs |
| `GET /handoffs/{handoff_id}` | agent | Paquete completo |
| `GET /traces/{trace_id}` | customer (solo las suyas), agent | Traza para el panel de auditoría |

### 6.3 Ejemplos

**`GET /health`**

```json
{"status": "ok", "policy_version": "1.0.0", "intent_model": "tfidf-lr-v1", "llm_model": "gemini-…", "data_manifest": "2026-09-29T02:10:00Z"}
```

**`GET /auth/demo-customers`**

```json
{"customers": [
  {"customer_id": "CUS-00812", "display_name": "Cliente demo 1", "segment": "Plus", "country": "Mexico",
   "suggested_language": "pt", "scenario": "Fraude con bloqueo"}
]}
```

**`POST /auth/login`**

```json
// request
{"customer_id": "CUS-00812", "otp": "123456"}
// response 200
{"access_token": "eyJ…", "token_type": "bearer", "expires_at": "2026-09-28T16:15:00Z",
 "customer": {"customer_id": "CUS-00812", "segment": "Plus", "country": "Mexico", "language": "pt"}}
```

**`POST /chat`** — un turno. El cliente manda **o** un mensaje de texto **o** una acción de UI.

```json
// request: primer mensaje (sin conversation_id → se crea una)
{"conversation_id": null, "message": "No reconozco un cargo de 350 en Oxxo"}

// request: elegir una tarjeta de transacción
{"conversation_id": "CONV-7f3a", "ui_action": {"type": "select_transaction", "transaction_id": "TX-1934027"}}

// request: confirmar o cancelar una acción propuesta
{"conversation_id": "CONV-7f3a", "ui_action": {"type": "confirm", "pending_action_id": "PA-51c0"}}
{"conversation_id": "CONV-7f3a", "ui_action": {"type": "cancel", "pending_action_id": "PA-51c0"}}
```

```json
// response 200
{
  "conversation_id": "CONV-7f3a",
  "turn_id": 3,
  "trace_id": "TR-9b21",
  "state": "CONFIRMAR_ACCION",
  "language": "es",
  "messages": [
    {"role": "assistant", "text": "Encontré este cargo. ¿Quieres que registre la disputa?", "source": "llm"}
  ],
  "ui": {
    "type": "confirmation",
    "pending_action": {
      "pending_action_id": "PA-51c0",
      "action": "create_dispute_case",
      "summary": "Registrar disputa por 350,00 USD en OXXO del 27-jun-2026",
      "expires_at": "2026-09-28T16:05:00Z"
    }
  },
  "case": null,
  "handoff_id": null,
  "audit": {
    "intent": "cargo_no_reconocido", "intent_confidence": 0.91,
    "rule_id": "R12", "tools": ["search_transactions", "get_transaction_risk"],
    "latency_ms": 840, "fallback_used": false
  }
}
```

Valores de `ui.type`:

| `ui.type` | Contenido | La UI muestra |
| :-- | :-- | :-- |
| `null` | — | Solo el mensaje |
| `transaction_options` | `options: list[TransactionView]` (máx. 5) | Tarjetas seleccionables (fecha, comercio, monto) |
| `confirmation` | `pending_action` | Botones Confirmar / Cancelar |
| `case_created` | `case: DisputeCase` | Número de caso, prioridad, SLA |
| `handoff` | `handoff_id`, `queue` | "Te paso con un especialista" |
| `reauth` | — | Vuelve al login |

`messages[].source` es `llm` o `template` (para que el panel de auditoría muestre cuándo hubo fallback). `audit` **nunca** incluye `fraud_score` ni el motivo de riesgo cuando el rol es `customer`; la traza completa solo la ve el rol `agent`.

**`GET /cases`**

```json
{"cases": [{ "case_id": "DSP-000123", "transaction_id": "TX-1934027", "dispute_type": "cargo_no_reconocido",
             "priority": "medium", "status": "Open", "created_at": "…", "sla_due_at": "…" }]}
```

**`GET /handoffs`**

```json
{"handoffs": [{"handoff_id": "HO-000045", "case_id": "DSP-000123", "priority": "critical",
               "suggested_queue": "fraude", "language": "pt", "created_at": "…", "handoff_reason": "POLICY_ESCALATION"}]}
```

`GET /handoffs/{id}` devuelve el `HandoffPackage` completo (sección 5.1).

**`GET /traces/{trace_id}`** (para el rol `customer` se omiten los spans de riesgo)

```json
{
  "trace_id": "TR-9b21", "conversation_id": "CONV-7f3a", "customer_id": "CUS-00812",
  "turns": [{
    "turn_id": 3, "state_from": "IDENTIFICAR_TRANSACCION", "state_to": "CONFIRMAR_ACCION",
    "spans": [
      {"name": "nlu.classify", "latency_ms": 12, "output": {"intent": "cargo_no_reconocido", "confidence": 0.91}},
      {"name": "llm.extract", "latency_ms": 610, "model": "gemini-…", "tokens_in": 420, "tokens_out": 60, "cost_usd": 0.00004},
      {"name": "tool.search_transactions", "latency_ms": 35, "output": {"n_results": 1}},
      {"name": "policy.evaluate", "latency_ms": 1, "output": {"rule_id": "R12", "action": "AUTO_REGISTER"}}
    ]
  }]
}
```

### 6.4 Garantías del backend al frontend

- Todo texto que llega en `messages` ya está en el idioma de la conversación; la UI no traduce.
- Todo número, fecha, ID y comercio en `messages` sale de hechos verificados (verificador de hechos; si falla, se usa la plantilla y `source = "template"`).
- `/chat` responde siempre con 200 y un mensaje utilizable salvo en errores de autenticación (401) o validación (422). Una falla de Gemini o de herramienta se ve como fallback o handoff, no como error HTTP.
- Mientras el backend no esté listo, D trabaja contra un mock que devuelve exactamente estos ejemplos (`frontend/src/api/mock.ts`).

---

## 7. Autenticación de prueba (D1.8)

Servicio de identidad **simulado**, documentado como tal en el README y en `operations.md`.

### 7.1 Flujo del cliente

1. La UI llama a `GET /auth/demo-customers` y muestra la lista (cada cliente de demo tiene un escenario asociado para facilitar la demo).
2. El usuario elige un cliente e ingresa el **OTP de prueba fijo** (`DEMO_OTP`, por defecto `123456`, configurable en `.env`). No se envía ningún SMS ni correo.
3. `POST /auth/login` valida que el `customer_id` esté en `demo_customers` y que el OTP coincida, y devuelve un JWT.
4. Toda llamada posterior lleva el JWT. El backend obtiene el `Session` **solo** del token.

### 7.2 Flujo del agente humano

`POST /auth/agent-login` con `{"agent_id": "AGT-DEMO", "otp": "123456"}` → JWT con `role = "agent"`. Solo este rol accede a `/handoffs` y a trazas ajenas.

### 7.3 Token

| Campo | Valor |
| :-- | :-- |
| Algoritmo | HS256, firmado con `JWT_SECRET` (en `.env`, nunca en el repo) |
| `sub` | `customer_id` o `agent_id` |
| `role` | `customer` \| `agent` |
| `sid` | `session_id` (para revocar) |
| `lang` | idioma sugerido del cliente |
| `iat`, `exp` | Expiración: **15 minutos** (`JWT_TTL_MINUTES`) |

No hay refresh token: al expirar, se vuelve a hacer login (es parte del escenario "sesión expirada").

### 7.4 Reglas de seguridad

- `customer_id` **siempre** sale del token. Nunca del mensaje del cliente, del cuerpo del request ni del LLM. Si el cliente escribe "soy el cliente CUS-123", se ignora.
- Token inválido o expirado → 401 `SESSION_EXPIRED` y la conversación queda en `PEDIR_REAUTENTICACIÓN` (R0). No se revela ningún dato en esa respuesta.
- `POST /auth/demo/expire` agrega el `sid` a una lista de revocados en SQLite; solo existe con `DEMO_MODE=true`.
- Al volver a entrar, la conversación puede continuar (mismo `conversation_id`) solo si el `customer_id` del nuevo token es el mismo; las acciones pendientes de la sesión anterior quedan invalidadas.

### 7.5 Qué cambiaría en producción

Proveedor de identidad real (OAuth2/OIDC del banco), OTP real por SMS o app, refresh tokens, rotación de secretos y registro de auditoría de accesos. Se lista en `operations.md` como trabajo pendiente.

---

## 8. Resuelto con datos al congelar (28-sep)

| Pendiente | Resolución | Evidencia |
| :-- | :-- | :-- |
| Fecha de referencia | 2026-06-17 | Última `process_date` de `transactions_12m` |
| MXN | Se quita del enum: los clientes de México operan en USD | `products.currency` por país: México 100 % USD |
| SLA por prioridad | Valores de política sintética (1/3/10/15 días) | En `complaints`, `sla_breached` ~20 % en todas las prioridades y `resolution_days` 1–30 en todas: no hay SLA derivable |
| τ_monto | p95 de `amount_usd` por `transaction_type` | Ver `policy.yaml` |
| `amount_usd` | USD: 100 % nulo → `= amount`. ARS/COP: ~5 % nulo → completar con `daily_exchange_rates` en silver (D2.x) | Conteo por moneda en `transactions_12m` |
| Nombres de columnas de gold | Los de la sección 4.5, que salen de las columnas reales (`transaction_status` → `status`, `process_date` → `business_date`, `product_number` → `card_mask`) | `data_pipeline/contracts.py` |

## 9. Estado de la implementación

Los umbrales quedaron versionados en la política 1.3.0. Los clientes y mensajes de demo están en gold y en `data/runs/20260929T234658Z-7cf922c1/demo_scenarios.json`. Silver normaliza `Mexico` a `México`. Los contratos de datos y el reporte final describen las validaciones y limitaciones; estos puntos ya no son pendientes de implementación.
