"""NLU (integracion_backend.md §1.1): intención con el clasificador de la 4.2; el resto de los campos
con Gemini (extract_llm) y, si Gemini falla por lo que sea, con las reglas (rules).

- intent, intent_confidence y abstain salen del clasificador y de tau_intencion. Solo si el
  clasificador se abstiene, Gemini da una segunda opinión (intent_llm, D4.5) en paralelo con la
  extracción: si nombra una de las 5 clases con confianza >= tau_gemini, esa es la intención y el
  turno deja de abstenerse. Gemini nunca cambia una intención que el clasificador ya aceptó.
- Si el modelo del clasificador no carga, la intención sale del stub y los campos de las reglas.
- model_version = "<versión del clasificador>[+intent_zeroshot_v1]+<extraccion_vN o rules>"; el
  segmento del medio aparece solo cuando la intención la decidió Gemini.
- Nunca lanza.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from ..config import get_policy, get_settings
from ..llm.gemini_client import LLMUnavailable, LLMUsage
from ..schemas import NLUResult
from . import extract_llm, intent_llm, rules, stub
from .classifier import get_classifier

log = logging.getLogger("latam.nlu")

_hilos = ThreadPoolExecutor(max_workers=4, thread_name_prefix="nlu-intent")


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


def _sin_senal_de_idioma(text: str) -> bool:
    """True si el texto no trae ninguna palabra que marque español o portugués ("88,88, Ferretería")."""
    palabras = rules.re.findall(r"[\wáéíóúâêôãõçñü]+", text.lower())
    return not any(p in rules._MARCADORES_ES or p in rules._MARCADORES_PT for p in palabras) \
        and not rules._ARTICULO_PT_INICIAL.search(text)


def _keywords(text: str, state: str | None) -> NLUResult:
    """Baseline B1 (NLU_MODE=keywords): intención del stub y campos de las reglas. Nunca Gemini."""
    base = stub.understand(text)
    return NLUResult(intent=base.intent, intent_confidence=base.intent_confidence, abstain=base.abstain,
                     **rules.extract(text, state), extractor="rules", model_version=f"{base.model_version}+rules")


def _understand(text: str, state: str | None) -> tuple[NLUResult, LLMUsage | None]:
    if get_settings().nlu_mode == "keywords":
        return _keywords(text, state), None
    clf = get_classifier()
    if clf is None:
        base = stub.understand(text)
        intent, conf, abstain, version = base.intent, base.intent_confidence, base.abstain, base.model_version
    else:
        intent, conf = clf.predict(text)
        abstain = conf < get_policy()["intent"]["tau_intencion"]
        version = clf.model_version

    tau_gemini = get_policy()["intent"].get("tau_gemini")
    segunda = None
    if clf is not None and abstain and tau_gemini is not None:
        segunda = _hilos.submit(intent_llm.clasificar, text, tau_gemini)

    campos, extractor, v_extraccion, uso = _extraer(text, state, con_llm=clf is not None)

    if segunda is not None:
        g_intent, g_conf, g_uso = segunda.result()
        if g_uso is not None:
            uso = extract_llm._sumar(uso, g_uso)
        if g_intent is not None:
            intent, conf, abstain = g_intent, g_conf, False
            version = f"{version}+{intent_llm.PROMPT_VERSION}"
    return NLUResult(intent=intent, intent_confidence=conf, abstain=abstain, **campos,
                     extractor=extractor, model_version=f"{version}+{v_extraccion}"), uso


def understand_con_uso(text: str, state: str | None = None,
                       language: str | None = None) -> tuple[NLUResult, LLMUsage | None]:
    """Como understand(), más el uso de Gemini (None si no se usó) para el span nlu.understand.

    language: idioma actual de la conversación. Si el texto no trae ninguna señal de idioma
    ("88,88, Ferretería"), se conserva ese idioma en vez de desempatar en español."""
    text = (text or "")[:2000]
    try:
        r, uso = _understand(text, state)
        if language in ("es", "pt") and r.language != language and _sin_senal_de_idioma(text):
            r = r.model_copy(update={"language": language})
        return r, uso
    except Exception as e:  # noqa: BLE001 - última red: el orquestador nunca ve una excepción del NLU
        log.error("nlu: falló understand (%s); se abstiene", type(e).__name__)
        return NLUResult(language="es", intent="fuera_de_alcance", intent_confidence=0.0, abstain=True,
                         extractor="rules", model_version="fallback+rules"), None


def understand(text: str, state: str | None = None, language: str | None = None) -> NLUResult:
    return understand_con_uso(text, state, language)[0]
