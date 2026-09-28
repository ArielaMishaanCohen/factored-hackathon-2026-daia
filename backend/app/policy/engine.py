"""Motor de política (design.md, sección 3).

Contrato: función pura evaluate(transaction, risk, customer_ctx, intent, policy) -> Decision.
STUB de Fase 1: solo R2–R4, R7 y R12 para que el flujo de demo funcione.
Fase 3 (C): implementar R0–R12 completas en orden de precedencia, con un test por
regla y por borde (score == τ exacto, score nulo, monto == τ_monto).
"""
from __future__ import annotations

from ..schemas import Decision, TransactionRisk, TransactionView


def evaluate(transaction: TransactionView, risk: TransactionRisk, customer_ctx: dict,
             intent: str, policy: dict) -> Decision:
    v = policy["policy_version"]
    if transaction.status == "Declined":
        return Decision(rule_id="R2", action="INFORM", reason="Transacción rechazada: no hubo cargo", policy_version=v)
    if transaction.status == "Pending":
        return Decision(rule_id="R3", action="INFORM", reason="Transacción pendiente", policy_version=v)
    if transaction.status == "Reversed":
        return Decision(rule_id="R4", action="INFORM", reason="Transacción ya revertida", policy_version=v)
    high = policy["rules"]["fraud_score_high"]
    if intent == "tarjeta_comprometida" or (risk.fraud_score is not None and risk.fraud_score >= high):
        return Decision(rule_id="R7", action="FRAUD", reason=f"fraud_score ≥ {high} o tarjeta comprometida",
                        priority="critical", queue="fraude", policy_version=v)
    # TODO Fase 3: R5, R6, R8, R9, R10, R11
    return Decision(rule_id="R12", action="AUTO_REGISTER", reason="Sin reglas de escalamiento",
                    priority="medium", policy_version=v)
