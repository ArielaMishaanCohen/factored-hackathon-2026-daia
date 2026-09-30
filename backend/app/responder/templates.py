"""Plantillas ES/PT: la red de seguridad cuando el LLM falla (design.md 6.4).

Fase 3 (C) completa todos los mensajes del flujo; Fase 4 (B) agrega la redacción con
Gemini + verificador de hechos, que cae a estas plantillas si algo no cuadra.
"""
from __future__ import annotations

TEMPLATES: dict[str, dict[str, str]] = {
    "abstain": {
        "es": "Por ahora solo puedo ayudarte con cargos que no reconoces, cobros incorrectos, tarjetas robadas o el estado de un reclamo.",
        "pt": "No momento só posso ajudar com cobranças que você não reconhece, cobranças incorretas, cartões roubados ou o status de uma contestação.",
    },
    "clarify": {
        "es": "Puedo ayudarte con cargos que no reconoces, cobros incorrectos, tarjetas robadas o el estado de un reclamo. ¿Me cuentas el monto, la fecha o el comercio del cargo?",
        "pt": "Posso ajudar com cobranças que você não reconhece, cobranças incorretas, cartões roubados ou o status de uma contestação. Pode me contar o valor, a data ou o estabelecimento da cobrança?",
    },
    "no_candidates": {
        "es": "No encontré ese cargo. ¿Me das el monto exacto o la fecha aproximada?",
        "pt": "Não encontrei essa cobrança. Pode informar o valor exato ou a data aproximada?",
    },
    "options": {
        "es": "Encontré varios cargos posibles. ¿Cuál es?",
        "pt": "Encontrei várias cobranças possíveis. Qual delas é?",
    },
    "not_found": {
        "es": "No encontré esa transacción.",
        "pt": "Não encontrei essa transação.",
    },
    "confirm_case": {
        "es": "Encontré el cargo de {amount} {currency} del {date}. ¿Quieres que registre la disputa?",
        "pt": "Encontrei a cobrança de {amount} {currency} de {date}. Deseja que eu registre a contestação?",
    },
    "confirm_block": {
        "es": "Para protegerte, te recomiendo bloquear la tarjeta {card}. ¿La bloqueo?",
        "pt": "Para sua proteção, recomendo bloquear o cartão {card}. Posso bloquear?",
    },
    "blocked_then_case": {
        "es": "Listo, la tarjeta {card} quedó bloqueada. ¿Registro también la disputa por el cargo de {amount} {currency}?",
        "pt": "Pronto, o cartão {card} foi bloqueado. Registro também a contestação da cobrança de {amount} {currency}?",
    },
    "case_created": {
        "es": "Registré tu disputa con el número {case_id}. Te responderemos antes del {sla}.",
        "pt": "Registrei sua contestação com o número {case_id}. Responderemos até {sla}.",
    },
    "handoff": {
        "es": "Tu caso {case_id} requiere revisión de un especialista. Ya le pasé toda la información.",
        "pt": "Seu caso {case_id} precisa da análise de um especialista. Já passei todas as informações.",
    },
    "handoff_no_case": {
        "es": "Voy a pasar tu consulta a un especialista para que te ayude. Ya le dejé todo el contexto.",
        "pt": "Vou encaminhar sua solicitação a um especialista. Já deixei todo o contexto com ele.",
    },
    "cancelled_handoff": {
        "es": "Entendido, no hice ese cambio. Como tu caso necesita revisión, se lo pasé a un especialista con toda la información.",
        "pt": "Entendido, não fiz essa alteração. Como seu caso precisa de análise, encaminhei a um especialista com todas as informações.",
    },
    "inform_R2": {
        "es": "Ese intento de cobro fue rechazado, así que no se te cobró nada.",
        "pt": "Essa tentativa de cobrança foi recusada, então nada foi cobrado.",
    },
    "inform_R3": {
        "es": "Ese cargo todavía está pendiente y podría no asentarse. Si se confirma, puedes volver a escribirme.",
        "pt": "Essa cobrança ainda está pendente e pode não ser efetivada. Se for confirmada, fale comigo novamente.",
    },
    "inform_R4": {
        "es": "Ese cargo ya fue revertido; no necesitas hacer nada.",
        "pt": "Essa cobrança já foi estornada; você não precisa fazer nada.",
    },
    "inform_R5": {
        "es": "Ya tienes una disputa abierta por ese cargo ({case_id}, estado {status}). No hace falta registrarla de nuevo.",
        "pt": "Você já tem uma contestação aberta para essa cobrança ({case_id}, status {status}). Não é preciso registrá-la novamente.",
    },
    "status_none": {
        "es": "No tienes reclamos abiertos.",
        "pt": "Você não tem contestações abertas.",
    },
    "status_list": {
        "es": "Tus reclamos abiertos: {cases}.",
        "pt": "Suas contestações abertas: {cases}.",
    },
    "cancelled": {
        "es": "Entendido, no hice ningún cambio.",
        "pt": "Entendido, não fiz nenhuma alteração.",
    },
    "confirmation_expired": {
        "es": "Esa confirmación ya no es válida. ¿Empezamos de nuevo?",
        "pt": "Essa confirmação não é mais válida. Vamos começar de novo?",
    },
    "tool_failure": {
        "es": "No pude completar la acción. Un especialista revisará tu caso.",
        "pt": "Não consegui concluir a ação. Um especialista analisará seu caso.",
    },
}


def render(key: str, language: str, **facts) -> str:
    return TEMPLATES[key][language].format(**facts)


# Texto corto junto a los botones Confirmar/Cancelar (pending_action.summary).
# No es un mensaje del chat: no pasa por Gemini, solo se traduce.
SUMMARIES: dict[str, dict[str, str]] = {
    "block_card": {
        "es": "Bloquear la tarjeta {card}",
        "pt": "Bloquear o cartão {card}",
    },
    "create_dispute_case": {
        "es": "Registrar disputa por {amount} {currency} del {date}",
        "pt": "Registrar contestação de {amount} {currency} de {date}",
    },
}


def render_summary(action: str, language: str, **facts) -> str:
    return SUMMARIES[action][language].format(**facts)
