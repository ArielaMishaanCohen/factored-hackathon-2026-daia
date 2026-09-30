"""NLU: intención con el clasificador de la 4.2; el resto (idioma, monto, confirmación) sigue
en el stub de palabras clave hasta la extracción con Gemini de la 4.3.

Si el modelo no carga, todo el resultado es el del stub (classifier.get_classifier lo registra).
"""
from __future__ import annotations

from ..config import get_policy
from ..schemas import NLUResult
from . import stub
from .classifier import get_classifier


def understand(text: str) -> NLUResult:
    base = stub.understand(text)
    clf = get_classifier()
    if clf is None:
        return base
    intent, conf = clf.predict(text)
    tau = get_policy()["intent"]["tau_intencion"]
    return base.model_copy(update={"intent": intent, "intent_confidence": conf, "abstain": conf < tau,
                                   "model_version": clf.model_version})
