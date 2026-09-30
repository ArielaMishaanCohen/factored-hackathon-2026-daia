"""Extracción con Gemini de los campos de NLUResult que salen del texto (todo menos la intención).

- Prompt versionado en prompts/extraccion_v1.txt, con la fecha de referencia de policy.yaml
  inyectada (nunca el reloj del sistema).
- El texto del cliente se minimiza (app.llm.minimizar) y va entre <mensaje_cliente> y
  </mensaje_cliente>, separado de las instrucciones: es un dato, no una orden.
- La respuesta se valida campo por campo con CamposLLM (Pydantic). Un campo inválido se descarta
  (queda en None, o sale de las reglas si es language); el resto se conserva. suspected_injection
  es el OR de Gemini y la heurística de reglas: un Gemini que obedece la inyección no la apaga.
- Si la respuesta entera no es un objeto JSON con las claves pedidas, 1 reintento. Si vuelve a
  fallar, o Gemini no está disponible, lanza LLMUnavailable: understand() cae a las reglas.
- El log nunca lleva el texto del cliente ni los valores extraídos: solo nombres de campos.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, ValidationInfo, field_validator

from ..config import ROOT, get_policy
from ..llm import gemini_client
from ..llm.gemini_client import LLMUsage, RespuestaInvalida
from ..llm.minimizar import minimizar
from ..schemas import Currency, Language
from . import rules

log = logging.getLogger(__name__)

PROMPT_VERSION = "extraccion_v1"
PROMPT_PATH = ROOT / "prompts" / f"{PROMPT_VERSION}.txt"
MAX_CHARS = 2000
CAMPOS = rules.CAMPOS

_NULO = {"type": "null"}
ESQUEMA: dict = {
    "type": "object",
    "properties": {
        "language": {"type": "string", "enum": ["es", "pt"]},
        "amount": {"anyOf": [{"type": "number"}, _NULO]},
        "currency": {"anyOf": [{"type": "string", "enum": ["ARS", "COP", "USD"]}, _NULO]},
        "date_from": {"anyOf": [{"type": "string", "format": "date"}, _NULO]},
        "date_to": {"anyOf": [{"type": "string", "format": "date"}, _NULO]},
        "merchant_hint": {"anyOf": [{"type": "string"}, _NULO]},
        "selected_option": {"anyOf": [{"type": "integer"}, _NULO]},
        "confirmation": {"anyOf": [{"type": "string", "enum": ["yes", "no"]}, _NULO]},
        "suspected_injection": {"type": "boolean"},
    },
    "required": list(CAMPOS),
}

_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")
# nuestras propias etiquetas dentro del texto del cliente: se neutralizan y cuentan como inyección
_ETIQUETAS = re.compile(r"<\s*/?\s*(mensaje_cliente|estado|nota_del_sistema)\s*>", re.I)
_NOTA_REINTENTO = ("<nota_del_sistema>Tu respuesta anterior no fue un objeto JSON con las claves pedidas. "
                   "Responde solo ese objeto.</nota_del_sistema>")


def _sin_tildes(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


class CamposLLM(BaseModel):
    """Lo que devuelve Gemini, campo por campo. Contexto: reference_date y texto (minimizado)."""
    model_config = ConfigDict(strict=True, extra="ignore")

    language: Language | None = None
    amount: Annotated[float, Field(gt=0, lt=1e10, allow_inf_nan=False)] | None = None
    currency: Currency | None = None
    date_from: date | None = None
    date_to: date | None = None
    merchant_hint: Annotated[str, Field(min_length=1, max_length=80)] | None = None
    selected_option: int | None = None
    confirmation: Literal["yes", "no"] | None = None
    suspected_injection: bool | None = None

    @field_validator("date_from", "date_to", mode="before")
    @classmethod
    def _iso(cls, v: Any) -> Any:
        if isinstance(v, str):
            if not _ISO.fullmatch(v.strip()):
                raise ValueError("fecha que no es AAAA-MM-DD")
            return date.fromisoformat(v.strip())
        return v

    @field_validator("date_from", "date_to")
    @classmethod
    def _no_futura(cls, v: date | None, info: ValidationInfo) -> date | None:
        ref = (info.context or {}).get("reference_date")
        if v is not None and ref is not None and v > ref:
            raise ValueError("fecha después de reference_date")
        return v

    @field_validator("merchant_hint", mode="before")
    @classmethod
    def _limpiar(cls, v: Any) -> Any:
        return v.strip() if isinstance(v, str) else v

    @field_validator("merchant_hint")
    @classmethod
    def _en_el_texto(cls, v: str | None, info: ValidationInfo) -> str | None:
        """No inventes: el comercio tiene que estar en el texto (sin mayúsculas ni tildes)."""
        texto = (info.context or {}).get("texto")
        if v is not None and texto is not None and _sin_tildes(v) not in _sin_tildes(texto):
            raise ValueError("comercio que no está en el texto")
        return v

    @field_validator("selected_option")
    @classmethod
    def _posicion(cls, v: int | None) -> int | None:
        if v is not None and not (v == -1 or 1 <= v <= 20):
            raise ValueError("posición fuera de rango")
        return v


@dataclass
class Detalle:
    """Resultado con lo que hace falta para evaluar (sin texto del cliente)."""
    campos: dict[str, Any]
    uso: LLMUsage
    intentos: int = 1
    descartados: list[str] = field(default_factory=list)


# --- Prompt ---------------------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _plantilla() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _reference_date() -> date:
    return date.fromisoformat(str(get_policy()["reference_date"]))


def armar_prompt(ref: date) -> str:
    lunes = ref - timedelta(days=ref.weekday())
    fin_mes_pasado = ref.replace(day=1) - timedelta(days=1)
    valores = {
        "reference_date": ref, "dia_semana": _DIAS[ref.weekday()], "dia_ref": ref.day,
        "ayer": ref - timedelta(days=1), "anteayer": ref - timedelta(days=2),
        "semana_pasada_desde": lunes - timedelta(days=7), "semana_pasada_hasta": lunes - timedelta(days=1),
        "esta_semana_desde": lunes,
        "mes_pasado_desde": fin_mes_pasado.replace(day=1), "mes_pasado_hasta": fin_mes_pasado,
        "este_mes_desde": ref.replace(day=1),
    }
    prompt = _plantilla()
    for k, v in valores.items():
        prompt = prompt.replace(f"<<{k}>>", str(v))
    return prompt


def armar_mensaje(texto: str, state: str | None) -> tuple[str, bool]:
    """(contenido para Gemini, si el texto traía nuestras etiquetas)."""
    texto = minimizar((texto or "")[:MAX_CHARS])
    texto, n = _ETIQUETAS.subn("[etiqueta]", texto)
    return f"<estado>{state or 'ninguno'}</estado>\n<mensaje_cliente>\n{texto}\n</mensaje_cliente>", n > 0


# --- Validación -----------------------------------------------------------------------------------

def _estructura_valida(r: Any) -> bool:
    return isinstance(r, dict) and any(c in r for c in CAMPOS)


def validar(crudo: dict, texto: str, state: str | None, ref: date) -> tuple[dict[str, Any], list[str]]:
    """Valida campo por campo y aplica las reglas deterministas. Devuelve (campos, descartados)."""
    ctx = {"reference_date": ref, "texto": texto}
    out: dict[str, Any] = {}
    descartados: list[str] = []
    for c in CAMPOS:
        try:
            out[c] = getattr(CamposLLM.model_validate({c: crudo.get(c)}, context=ctx), c)
        except ValidationError:
            out[c] = None
            descartados.append(c)

    if out["date_from"] and out["date_to"] and out["date_from"] > out["date_to"]:
        out["date_from"] = out["date_to"] = None
        descartados += ["date_from", "date_to"]
    # campos obligatorios de NLUResult: si Gemini los manda mal, salen de las reglas
    if out["language"] is None:
        out["language"] = rules.detectar_idioma(texto)
    # Gemini puede obedecer la inyección y decir false: la heurística de reglas cuenta igual
    out["suspected_injection"] = bool(out["suspected_injection"]) or rules.detectar_inyeccion(texto)
    # la confirmación solo vale en CONFIRMAR_ACCION y nunca junto a una inyección (§1.3)
    if state != "CONFIRMAR_ACCION" or out["suspected_injection"]:
        out["confirmation"] = None
    return out, descartados


# --- Extracción -----------------------------------------------------------------------------------

def _sumar(a: LLMUsage | None, b: LLMUsage) -> LLMUsage:
    if a is None:
        return b
    return LLMUsage(b.model, a.tokens_in + b.tokens_in, a.tokens_out + b.tokens_out,
                    a.cost_usd + b.cost_usd, cached=a.cached and b.cached)


def extract_con_detalle(text: str, state: str | None = None, reference_date: date | None = None,
                        client: Any = None) -> Detalle:
    """Como extract(), con intentos y campos descartados. Lanza LLMUnavailable si Gemini falla."""
    ref = reference_date or _reference_date()
    cliente = client or gemini_client.get_client()
    prompt = armar_prompt(ref)
    mensaje, etiquetas = armar_mensaje(text, state)
    texto_min = minimizar((text or "")[:MAX_CHARS])

    uso: LLMUsage | None = None
    for intento in (1, 2):
        contenido = mensaje if intento == 1 else f"{mensaje}\n{_NOTA_REINTENTO}"
        try:
            crudo, u = cliente.generate_json(prompt, contenido, ESQUEMA)
        except RespuestaInvalida:
            log.warning("extract_llm: intento %d, respuesta que no es JSON", intento)
            if intento == 2:
                raise
            continue
        uso = _sumar(uso, u)
        if _estructura_valida(crudo):
            break
        log.warning("extract_llm: intento %d, JSON sin la estructura pedida", intento)
        if intento == 2:
            raise RespuestaInvalida("JSON sin la estructura pedida tras 1 reintento")

    campos, descartados = validar(crudo, texto_min, state, ref)
    if etiquetas:
        campos["suspected_injection"] = True
        campos["confirmation"] = None
    if descartados:
        log.warning("extract_llm: campos descartados por inválidos: %s", ", ".join(descartados))
    return Detalle(campos, uso, intento, descartados)


def extract(text: str, state: str | None = None, reference_date: date | None = None,
            client: Any = None) -> tuple[dict[str, Any], LLMUsage]:
    """Campos de NLUResult menos intent/intent_confidence/abstain, y el uso de Gemini.

    Lanza LLMUnavailable (sin llave, API caída, JSON inválido tras el reintento): quien llama cae a
    rules.extract."""
    d = extract_con_detalle(text, state, reference_date, client)
    return d.campos, d.uso
