"""Motor de política (design.md, sección 3).

Contrato: función PURA evaluate(transaction, risk, customer_ctx, intent, policy) -> Decision.
"Pura" = no lee bases de datos ni llama al LLM: recibe todo como parámetro y siempre
devuelve lo mismo para la misma entrada. Por eso es fácil de probar y de auditar.

Las reglas van en ORDEN DE PRECEDENCIA: la primera que aplica gana.
R0 (sesión) y R1 (transacción ajena) se aplican antes, en auth.py y en las tools.
Todos los números (τ) salen de config/policy.yaml, nunca van escritos aquí.
"""
from __future__ import annotations

from datetime import date

from ..schemas import Decision, TransactionRisk, TransactionView


def evaluate(transaction: TransactionView, risk: TransactionRisk, customer_ctx: dict,
             intent: str, policy: dict) -> Decision:
    v = policy["policy_version"]
    rules = policy["rules"]

    def decide(rule_id, action, reason, priority=None, queue=None) -> Decision:
        return Decision(rule_id=rule_id, action=action, reason=reason,
                        priority=priority, queue=queue, policy_version=v)

    # --- R2–R4: el estado de la transacción dice que no hay nada que disputar ------------
    if transaction.status == "Declined":
        return decide("R2", "INFORM", "Transacción rechazada: no hubo cargo")
    if transaction.status == "Pending":
        return decide("R3", "INFORM", "Transacción pendiente: puede no asentarse")
    if transaction.status == "Reversed":
        return decide("R4", "INFORM", "Transacción ya revertida")

    # --- R5: ya hay un caso abierto por esta transacción → no duplicar ------------------
    open_cases = customer_ctx.get("open_cases_by_tx", {})
    if open_case := open_cases.get(transaction.transaction_id):
        return decide("R5", "INFORM", f"Ya existe el caso {open_case['case_id']} ({open_case['status']})")

    # --- R6: fuera de la ventana de reclamo ----------------------------------------------
    reference = date.fromisoformat(policy["reference_date"])
    age_days = (reference - transaction.business_date).days
    window = rules["claim_window_days"]
    if age_days > window:
        return decide("R6", "ESCALATE", f"Transacción de hace {age_days} días (ventana: {window})",
                      priority="medium", queue="disputas")

    # --- R7: fraude casi seguro o tarjeta comprometida ----------------------------------
    score = risk.fraud_score
    high, low = rules["fraud_score_high"], rules["fraud_score_low"]
    if intent == "tarjeta_comprometida":
        return decide("R7", "FRAUD", "El cliente reporta la tarjeta comprometida",
                      priority="critical", queue="fraude")
    if score is not None and score >= high:
        return decide("R7", "FRAUD", f"fraud_score {score} ≥ {high}", priority="critical", queue="fraude")

    # --- R8: riesgo desconocido (score nulo) ---------------------------------------------
    if score is None:
        return decide("R8", "ESCALATE", "fraud_score nulo: riesgo desconocido",
                      priority="high", queue="disputas")

    # --- R9: zona gris de fraude ----------------------------------------------------------
    if low <= score < high:
        return decide("R9", "ESCALATE", f"fraud_score {score} en zona gris [{low}, {high})",
                      priority="high", queue="fraude")

    # --- R10: monto alto para su tipo de transacción -------------------------------------
    limits = rules["amount_usd_max"]
    limit = limits.get(transaction.transaction_type, limits["default"])
    if risk.amount_usd > limit:
        return decide("R10", "ESCALATE",
                      f"amount_usd {risk.amount_usd:.2f} > {limit} ({transaction.transaction_type})",
                      priority="high", queue="disputas")

    # --- R11: cliente con muchas disputas recientes --------------------------------------
    k = rules["repeat_disputes_k"]
    recent = customer_ctx.get("prior_complaints_90d", 0) + len(open_cases)
    if recent >= k:
        return decide("R11", "ESCALATE", f"{recent} disputas en {rules['repeat_window_days']} días (k={k})",
                      priority="medium", queue="disputas")

    # --- R12: nada de lo anterior → se puede registrar solo -----------------------------
    return decide("R12", "AUTO_REGISTER", "Sin reglas de escalamiento", priority="medium")
