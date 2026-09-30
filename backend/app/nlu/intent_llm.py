"""Segunda opinión de Gemini sobre la intención, solo cuando el clasificador se abstiene (D4.5).

- Mismo prompt y misma forma de llamar que el candidato evaluado en la 4.2
  (ml/intent/candidates/gemini_zeroshot.py, prompts/intent_zeroshot_v1.txt): la frase va entre
  <frase> y </frase> como dato, y la salida es {"intent", "confidence"}, donde intent puede ser
  "ambiguo". A diferencia del candidato, la frase se minimiza antes (app.llm.minimizar).
- Se acepta la intención solo si es una de las 5 clases (no "ambiguo") y confidence >= tau_gemini
  (config/policy.yaml, intent.tau_gemini). Si no, o si Gemini falla, devuelve None y el turno sigue
  abstenido, como sin Gemini.
- El log nunca lleva el texto del cliente.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from ..config import ROOT
from ..llm import gemini_client
from ..llm.gemini_client import LLMUsage
from ..llm.minimizar import minimizar

log = logging.getLogger(__name__)

PROMPT_VERSION = "intent_zeroshot_v1"
PROMPT_PATH = ROOT / "prompts" / f"{PROMPT_VERSION}.txt"
CLASES = ["cargo_no_reconocido", "cobro_incorrecto", "tarjeta_comprometida", "estado_disputa", "fuera_de_alcance"]
ESQUEMA: dict = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": CLASES + ["ambiguo"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["intent", "confidence"],
}


@lru_cache(maxsize=1)
def _prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def clasificar(text: str, tau: float, client: Any = None) -> tuple[str | None, float, LLMUsage | None]:
    """(intención o None, confianza de Gemini, uso). Nunca lanza."""
    uso: LLMUsage | None = None
    try:
        cliente = client or gemini_client.get_client()
        if not getattr(cliente, "disponible", True):
            return None, 0.0, None
        salida, uso = cliente.generate_json(_prompt(), f"<frase>\n{minimizar(text)}\n</frase>", ESQUEMA)
        intent, conf = salida.get("intent"), float(salida.get("confidence"))
    except Exception as e:  # noqa: BLE001 — sin segunda opinión el turno sigue abstenido
        log.info("nlu: sin segunda opinión de Gemini (%s)", type(e).__name__)
        return None, 0.0, uso
    if intent not in CLASES or not 0 <= conf <= 1 or conf < tau:
        log.info("nlu: Gemini no resuelve la abstención (intent=%s)", intent if intent in CLASES else "otro")
        return None, conf if 0 <= conf <= 1 else 0.0, uso
    return intent, conf, uso
