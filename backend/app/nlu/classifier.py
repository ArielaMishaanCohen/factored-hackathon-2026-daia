"""Clasificador de intención (Fase 4.2): TF-IDF + regresión logística entrenado con `make train`.

Carga ml/intent/model/intent_model.joblib una sola vez (o INTENT_MODEL_PATH) y devuelve
(intent, confidence), con confidence = probabilidad de la clase más probable. El umbral de
abstención no vive aquí: sale de config/policy.yaml (intent.tau_intencion).
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

import joblib

from ..config import ROOT

log = logging.getLogger("latam.nlu")

DEFAULT_PATH = ROOT / "ml" / "intent" / "model" / "intent_model.joblib"


class IntentClassifier:
    def __init__(self, path: Path):
        art = joblib.load(path)
        self.pipeline = art["pipeline"]
        self.model_version: str = art["model_version"]
        self.clases: list[str] = list(self.pipeline.classes_)

    def predict(self, text: str) -> tuple[str, float]:
        probs = self.pipeline.predict_proba([text])[0]
        i = int(probs.argmax())
        return str(self.clases[i]), float(probs[i])


@lru_cache(maxsize=1)
def get_classifier() -> IntentClassifier | None:
    """El modelo, o None si no carga (se registra una vez y el NLU usa el stub)."""
    path = Path(os.environ.get("INTENT_MODEL_PATH", DEFAULT_PATH))
    try:
        clf = IntentClassifier(path)
    except Exception as e:  # archivo faltante, pickle de otra versión de sklearn, etc.
        log.warning("clasificador de intención no cargó (%s: %s); se usa el stub de palabras clave",
                    type(e).__name__, e)
        return None
    log.info("clasificador de intención cargado: %s", clf.model_version)
    return clf
