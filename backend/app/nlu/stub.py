"""NLU STUB de Fase 1: palabras clave. Solo para que el flujo funcione end-to-end.

Fase 4 (B): reemplazar por el clasificador elegido + extracción con Gemini, con la
misma salida (schemas.NLUResult) y el fallback por reglas.
"""
from __future__ import annotations

import re

from ..schemas import NLUResult

_PT = re.compile(r"\b(não|nao|cartão|cartao|cobrança|você|voce|meu|minha|roubaram|quero|compra)\b", re.I)
_KEYWORDS = [
    ("tarjeta_comprometida", r"rob|perd|clon|roub"),
    ("estado_disputa", r"c[oó]mo va|estado|como est[aá]"),
    ("cobro_incorrecto", r"dos veces|duas vezes|duplicad|de m[aá]s"),
    ("cargo_no_reconocido", r"reconozco|reconhe|no hice|n[aã]o fiz|cargo|cobro|cobran"),
    ("fuera_de_alcance", r"pr[eé]stamo|empr[eé]stimo|l[ií]mite|pin|saldo"),
]
_AMOUNT = re.compile(r"(\d[\d.,]*)")
_YES = re.compile(r"^\s*(s[ií]|sim|ok|dale|confirmo)\b", re.I)
_NO = re.compile(r"^\s*(no|n[aã]o|cancel)", re.I)


def understand(text: str) -> NLUResult:
    intent, conf = "fuera_de_alcance", 0.3
    for name, pattern in _KEYWORDS:
        if re.search(pattern, text, re.I):
            intent, conf = name, 0.9
            break
    amount = None
    if m := _AMOUNT.search(text):
        try:
            amount = float(m.group(1).replace(".", "").replace(",", "."))
        except ValueError:
            pass
    return NLUResult(
        language="pt" if _PT.search(text) else "es", intent=intent, intent_confidence=conf,
        abstain=conf < 0.6, amount=amount,
        confirmation="yes" if _YES.search(text) else "no" if _NO.search(text) else None,
        extractor="rules", model_version="stub-keywords-0",
    )
