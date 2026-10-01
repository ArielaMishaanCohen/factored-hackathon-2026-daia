"""Redacción con Gemini + verificador de hechos (integracion_backend.md §1.6).

compose() parte de la plantilla (templates.render) y le pide a Gemini que la reescriba con
prompts/redaccion_v1.txt. El texto de Gemini solo se usa si pasa el verificador:

- Todo ID (DSP-..., TX-..., CONV-...), tarjeta ("•••• 1234"), número, monto, fecha y nombre
  propio del texto tiene que estar en la plantilla o en facts, con formatos normalizados
  (350.00 = 350,00 = 350; 2026-10-09 = 9 de octubre = 09/10/2026).
- Y al revés: todo ID, número y fecha de la plantilla tiene que seguir en el texto, y si la
  plantilla pregunta algo, el texto también (mismo significado).
- Sin promesas ni acciones nuevas: palabras como reembolso, aprobado, bloquear o "mañana" solo
  valen si la plantilla ya las dice.
- Idioma pedido, no vacío, no más frases ni más largo de lo permitido.

Si algo no pasa, o Gemini no está disponible, o hay cualquier error, se devuelve la plantilla
tal cual con source="template". El log solo lleva la clave de la plantilla y el motivo, nunca
el texto ni los valores.

De los valores de facts que son texto libre (dos o más palabras con letras, ej. un
merchant_name con una inyección adentro) no se toma ningún dato permitido: no se le mandan a
Gemini y no pueden habilitar un número o una palabra nueva.

compose_summary() hace lo mismo con el summary del paquete de handoff (prompts/resumen_handoff_v1.txt).
"""
from __future__ import annotations

import logging
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from typing import Any

from ..config import ROOT, get_settings
from ..llm import gemini_client
from ..llm.gemini_client import LLMUsage
from . import templates

log = logging.getLogger(__name__)

PROMPT_VERSION = "redaccion_v1"
PROMPT_RESUMEN_VERSION = "resumen_handoff_v1"

MAX_FRASES = 2
MAX_CHARS = 280
MAX_FRASES_RESUMEN = 3
MAX_CHARS_RESUMEN = 400

# --- Extracción de datos --------------------------------------------------------------------------

_MESES = {
    "enero": 1, "janeiro": 1, "febrero": 2, "fevereiro": 2, "marzo": 3, "marco": 3, "abril": 4,
    "mayo": 5, "maio": 5, "junio": 6, "junho": 6, "julio": 7, "julho": 7, "agosto": 8,
    "septiembre": 9, "setiembre": 9, "setembro": 9, "octubre": 10, "outubro": 10,
    "noviembre": 11, "novembro": 11, "diciembre": 12, "dezembro": 12,
}
_MES = "|".join(sorted(_MESES, key=len, reverse=True))

_ID = re.compile(r"\b[A-Z]{2,6}(?:-[A-Z0-9]+)*-[A-Z]*\d[A-Z0-9]*\b")
_TARJETA = re.compile(r"[•*·xX]{2,}[  ]*(\d{4})\b")
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})(?:T[\d:.+Z-]+)?\b")
_DIA_MES = re.compile(r"\b(\d{1,2})\s+de\s+(" + _MES + r")(?:\s+(?:de|del)\s+(\d{4}))?\b")
_BARRA = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")
_NUMERO = re.compile(r"\d[\d.,]*")
# palabra con mayúscula inicial o toda en mayúsculas (OXXO, USD, Mercado)
_PALABRA_MAYUS = re.compile(r"[A-ZÁÉÍÓÚÂÊÔÃÕÇÑÜ][\wáéíóúâêôãõçñü&'’-]*")
_INICIO_FRASE = re.compile(r"(?:^|[.!?:;¿¡(\"«]\s*|[.!?]\s+)$")


def _sin_tildes(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _numero(s: str) -> str | None:
    """'350.00', '350,00', '1,234.56', '1.234,56', '120.000' → forma canónica ('350', '1234.56')."""
    s = s.strip(".,")
    if not s:
        return None
    if "." in s and "," in s:
        dec = "." if s.rfind(".") > s.rfind(",") else ","
        mil = "," if dec == "." else "."
        s = s.replace(mil, "").replace(dec, ".")
    elif "." in s or "," in s:
        sep = "." if "." in s else ","
        partes = s.split(sep)
        if len(partes) > 2 or len(partes[1]) == 3:
            s = "".join(partes)       # separador de miles: "120.000", "1,500"
        else:
            s = s.replace(sep, ".")   # decimal: "350,50", "49.99"
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    return format(d.normalize(), "f")


def _fecha(d: int, m: int, a: int | None) -> tuple[int, int, int | None] | None:
    if a is not None and a < 100:
        a += 2000
    try:
        date(a or 2000, m, d)
    except ValueError:
        return None
    return (m, d, a)


def extraer(texto: str) -> dict[str, set]:
    """Datos verificables de un texto: ids, números (incluye los 4 dígitos de las tarjetas),
    fechas (mes, día, año o None) y nombres propios (sin tildes, en minúscula)."""
    ids: set[str] = set()
    nums: set[str] = set()
    fechas: set[tuple] = set()
    nombres: set[str] = set()
    t = texto

    def _quitar(rx: re.Pattern, fn) -> None:
        nonlocal t
        def _sub(m: re.Match) -> str:
            fn(m)
            return " "
        t = rx.sub(_sub, t)

    _quitar(_ID, lambda m: ids.add(m.group(0).upper()))
    _quitar(_TARJETA, lambda m: nums.add(str(int(m.group(1)))))
    _quitar(_ISO, lambda m: fechas.add(_fecha(int(m[3]), int(m[2]), int(m[1]))))
    _quitar(re.compile(_DIA_MES.pattern, re.I),
            lambda m: fechas.add(_fecha(int(m[1]), _MESES[_sin_tildes(m[2])], int(m[3]) if m[3] else None)))
    _quitar(_BARRA, lambda m: fechas.add(_fecha(int(m[1]), int(m[2]), int(m[3]) if m[3] else None)))
    for m in _NUMERO.finditer(t):
        n = _numero(m.group(0))
        if n is not None:
            nums.add(n)
    for m in _PALABRA_MAYUS.finditer(t):
        palabra = m.group(0)
        antes = t[:m.start()]
        # la primera palabra de una frase va con mayúscula sin ser nombre propio
        if _INICIO_FRASE.search(antes) and not (len(palabra) > 1 and palabra.isupper()):
            continue
        nombres.add(_sin_tildes(palabra))
    fechas.discard(None)
    return {"ids": ids, "nums": nums, "fechas": fechas, "nombres": nombres}


def _texto_libre(v: str) -> bool:
    return len(re.findall(r"[^\W\d_]{2,}", v)) >= 2


def _valor(v: Any) -> str | None:
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float, Decimal)):
        return str(v)
    if isinstance(v, str) and not _texto_libre(v):
        return v
    return None


def permitidos(base: str, facts: dict) -> dict[str, set]:
    """Lo que el texto de Gemini puede mencionar: la plantilla + los valores de facts que no son texto libre."""
    out = extraer(base)
    for v in facts.values():
        s = _valor(v)
        if s is None:
            continue
        for k, vals in extraer(s).items():
            out[k] |= vals
        # un valor suelto ("OXXO", "USD") cuenta como nombre aunque vaya al inicio
        if re.fullmatch(r"[^\W\d_][\w&'’-]*", s):
            out["nombres"].add(_sin_tildes(s))
    return out


def _fecha_en(f: tuple, conjunto: set) -> bool:
    m, d, a = f
    return any(m == m2 and d == d2 and (a is None or a2 is None or a == a2) for m2, d2, a2 in conjunto)


# --- Promesas, acciones e idioma ------------------------------------------------------------------

# raíces sin tildes: solo pueden aparecer si la plantilla ya las tiene
_PROMESAS = [
    "reembols", "devolv", "devoluc", "estorn", "reintegr", "acredit", "abonar", "abonamos",
    "abonaremos", "credito", "compens", "indemniz", "aprobad", "aprueb", "aprovad", "aprovamos",
    "garant", "resuelt", "resolvid", "a tu favor", "a su favor", "a seu favor", "gratis",
    "sin costo", "sem custo", "inmediat", "imediat", "manana", "amanha", "hoy mismo", "hoje mesmo",
    "horas", "dias", "semana", "habiles", "uteis", "procede",
    # acciones
    "bloque", "cancel", "reemplaz", "substitu", "nueva tarjeta", "novo cartao", "cartao novo",
    "reenvi", "llamar", "llamaremos", "ligar", "ligaremos",
]
_RX_PROMESAS = [(p, re.compile(r"\b" + re.escape(p))) for p in _PROMESAS]

_MARCAS_ES = set("""
    el los las la del al y tu tus te su sus ya hay cargo cargos tarjeta disputa reclamo reclamos
    quieres puedes registre encontre bloquee listo tambien todavia ningun ninguna cual estas hice
    necesitas pero muy con un una no hace falta cobro cobrado ese esa eso hasta antes
""".split())
_MARCAS_PT = set("""
    o os as do da dos das e seu sua seus suas voce ja cobranca cobrancas cartao contestacao
    contestacoes deseja registrei encontrei bloqueado pronto ainda nenhum nenhuma qual precisa
    com mas muito um uma nao foi essa esse isso ate responderemos
""".split())


def _idioma_ok(texto: str, language: str) -> bool:
    palabras = re.findall(r"[a-z]+", _sin_tildes(texto))
    es = sum(p in _MARCAS_ES for p in palabras) + sum(c in "ñ¿¡" for c in texto.lower())
    pt = sum(p in _MARCAS_PT for p in palabras) + sum(c in "ãõç" for c in texto.lower())
    return pt <= es if language == "es" else es <= pt


def _frases(texto: str) -> int:
    return len([f for f in re.split(r"(?<=[.!?])\s+", texto.strip()) if f.strip()])


# --- Verificador ----------------------------------------------------------------------------------

def verificar(texto: str, base: str, facts: dict, language: str,
              max_frases: int = MAX_FRASES, max_chars: int = MAX_CHARS) -> str | None:
    """None si el texto de Gemini se puede usar; si no, el motivo (sin valores)."""
    if not texto or not texto.strip():
        return "vacio"
    if len(texto) > max(max_chars, int(len(base) * 1.5)):
        return "largo"
    if _frases(texto) > max(max_frases, _frases(base)):
        return "frases"
    if re.search(r"[<>{}\[\]`#\n]", texto):
        return "formato"
    if not _idioma_ok(texto, language):
        return "idioma"

    ok = permitidos(base, facts)
    nuevo = extraer(texto)
    if nuevo["ids"] - ok["ids"]:
        return "dato_nuevo:id"
    if nuevo["nums"] - ok["nums"]:
        return "dato_nuevo:numero"
    if any(not _fecha_en(f, ok["fechas"]) for f in nuevo["fechas"]):
        return "dato_nuevo:fecha"
    if nuevo["nombres"] - ok["nombres"]:
        return "dato_nuevo:nombre"

    # mismo significado: lo que decía la plantilla sigue ahí
    de_base = extraer(base)
    if de_base["ids"] - nuevo["ids"]:
        return "dato_faltante:id"
    if de_base["nums"] - nuevo["nums"]:
        return "dato_faltante:numero"
    if any(not _fecha_en(f, nuevo["fechas"]) for f in de_base["fechas"]):
        return "dato_faltante:fecha"
    if "?" in base and "?" not in texto:
        return "pregunta_perdida"

    t, b = _sin_tildes(texto), _sin_tildes(base)
    for p, rx in _RX_PROMESAS:
        if rx.search(t) and not rx.search(b):
            return "promesa"
    return None


# --- Redacción ------------------------------------------------------------------------------------

@lru_cache(maxsize=4)
def _prompt(version: str) -> str:
    return (ROOT / "prompts" / f"{version}.txt").read_text(encoding="utf-8")


def _limpiar(texto: str) -> str:
    t = " ".join((texto or "").split())
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'“”«»":
        t = t[1:-1].strip()
    return t


def _redactar(clave: str, version: str, etiqueta: str, base: str, language: str, facts: dict,
              max_frases: int, max_chars: int, client: Any) -> tuple[str, str, LLMUsage | None]:
    uso: LLMUsage | None = None
    if get_settings().nlu_mode == "keywords":   # baseline B1: nunca Gemini, siempre la plantilla
        return base, "template", None
    try:
        cliente = client or gemini_client.get_client()
        if not getattr(cliente, "disponible", True):
            log.info("compose: %s → plantilla (motivo: sin_llm)", clave)
            return base, "template", None
        mensaje = f"<idioma>{language}</idioma>\n<{etiqueta}>\n{base}\n</{etiqueta}>"
        crudo, uso = cliente.generate_text(_prompt(version), mensaje)
        texto = _limpiar(crudo)
        motivo = verificar(texto, base, facts, language, max_frases, max_chars)
    except gemini_client.LLMUnavailable:
        motivo = "sin_llm"
    except Exception as e:  # noqa: BLE001 — compose nunca lanza: cualquier error → plantilla
        motivo = f"error:{type(e).__name__}"
    if motivo is not None:
        log.info("compose: %s → plantilla (motivo: %s)", clave, motivo)
        return base, "template", uso
    return texto, "llm", uso


def compose(template_key: str, language: str, facts: dict,
            client: Any = None) -> tuple[str, str, LLMUsage | None]:
    """Devuelve (texto, source, uso). source = "llm" si Gemini redactó y pasó el verificador;
    "template" si se usó la plantilla tal cual. uso es None si no se llamó a Gemini; si se
    llamó y el verificador rechazó el texto, igual viene el uso (el costo ya se pagó).

    Solo lanza si la plantilla misma no se puede armar (clave o facts que faltan): en ese caso
    no hay texto seguro que devolver, igual que hoy con templates.render."""
    base = templates.render(template_key, language, **facts)
    return _redactar(template_key, PROMPT_VERSION, "mensaje_base", base, language, facts,
                     MAX_FRASES, MAX_CHARS, client)


def compose_summary(summary: str, language: str, facts: dict,
                    client: Any = None) -> tuple[str, str, LLMUsage | None]:
    """Reescribe el summary del handoff con el mismo verificador. Nunca lanza: si algo falla,
    devuelve el summary tal cual con source="template"."""
    return _redactar("handoff_summary", PROMPT_RESUMEN_VERSION, "resumen_base", summary or "",
                     language, facts or {}, MAX_FRASES_RESUMEN, MAX_CHARS_RESUMEN, client)
