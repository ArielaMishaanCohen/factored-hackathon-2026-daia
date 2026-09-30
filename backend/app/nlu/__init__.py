"""NLU (integracion_backend.md §1.1): intención con el clasificador de la 4.2; el resto de los campos
con Gemini (extract_llm) y, si Gemini falla por lo que sea, con las reglas (rules).

- intent, intent_confidence y abstain salen siempre del clasificador y de tau_intencion: Gemini
  nunca cambia la intención.
- Si el modelo del clasificador no carga, la intención sale del stub y los campos de las reglas.
- model_version = "<versión del clasificador>+<extraccion_vN o rules>".
- Nunca lanza.
"""
from __future__ import annotations

import logging

from ..config import get_policy
from ..llm.gemini_client import LLMUnavailable, LLMUsage
from ..schemas import NLUResult
from . import extract_llm, rules, stub
from .classifier import get_classifier

log = logging.getLogger("latam.nlu")


def _extraer(text: str, state: str | None, con_llm: bool) -> tuple[dict, str, str, LLMUsage | None]:
    """(campos, extractor, versión de la extracción, uso de Gemini)."""
    if con_llm:
        try:
            campos, uso = extract_llm.extract(text, state)
            return campos, "llm", extract_llm.PROMPT_VERSION, uso
        except LLMUnavailable as e:
            log.info("nlu: Gemini no disponible (%s); extracción por reglas", e)
        except Exception as e:  # noqa: BLE001 - cualquier fallo de Gemini cae a las reglas
            log.warning("nlu: la extracción con Gemini falló (%s); extracción por reglas", type(e).__name__)
    return rules.extract(text, state), "rules", "rules", None


def _understand(text: str, state: str | None) -> tuple[NLUResult, LLMUsage | None]:
    clf = get_classifier()
    if clf is None:
        base = stub.understand(text)
        intent, conf, abstain, version = base.intent, base.intent_confidence, base.abstain, base.model_version
    else:
        intent, conf = clf.predict(text)
        abstain = conf < get_policy()["intent"]["tau_intencion"]
        version = clf.model_version

    campos, extractor, v_extraccion, uso = _extraer(text, state, con_llm=clf is not None)
    return NLUResult(intent=intent, intent_confidence=conf, abstain=abstain, **campos,
                     extractor=extractor, model_version=f"{version}+{v_extraccion}"), uso


def understand_con_uso(text: str, state: str | None = None) -> tuple[NLUResult, LLMUsage | None]:
    """Como understand(), más el uso de Gemini (None si no se usó) para el span nlu.understand."""
    text = (text or "")[:2000]
    try:
        return _understand(text, state)
    except Exception as e:  # noqa: BLE001 - última red: el orquestador nunca ve una excepción del NLU
        log.error("nlu: falló understand (%s); se abstiene", type(e).__name__)
        return NLUResult(language="es", intent="fuera_de_alcance", intent_confidence=0.0, abstain=True,
                         extractor="rules", model_version="fallback+rules"), None


def understand(text: str, state: str | None = None) -> NLUResult:
    return understand_con_uso(text, state)[0]
