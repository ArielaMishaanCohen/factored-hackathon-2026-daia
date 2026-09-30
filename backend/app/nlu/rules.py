"""Extracción por reglas de los campos de NLUResult que salen del texto (todo menos la intención).

Es el fallback cuando Gemini falla (extractor="rules") y el baseline contra el que se mide a Gemini.
Sigue las convenciones de ml/llm/extraccion_casos.md y los casos de docs/integracion_backend.md §1.2
y §1.3. Se ajustó mirando solo el split dev del set; nunca el test.

Nunca lanza: si algo sale mal en un campo, ese campo queda en None.
"""
from __future__ import annotations

import calendar
import logging
import re
import unicodedata
from datetime import date, timedelta
from typing import Any

from ..config import get_policy

log = logging.getLogger(__name__)

CAMPOS = ("language", "amount", "currency", "date_from", "date_to", "merchant_hint",
          "selected_option", "confirmation", "suspected_injection")


def _sin_tildes(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _reference_date() -> date:
    return date.fromisoformat(str(get_policy()["reference_date"]))


# --- Inyección ------------------------------------------------------------------------------------

_INYECCION = [re.compile(p, re.I) for p in (
    # ignora/olvida/esquece + instrucciones o reglas (no "ignora mi mensaje anterior")
    r"\b(ignor\w*|olvid\w*|esquec\w*|desconsider\w*)\b[^.]{0,30}\b(instruc\w*|instru[cç][oõ]es|reglas|regras|restric\w*|prompt)",
    r"\b(system|sistema|assistant|developer)\s*:",
    r"\b(confirmation|intent|amount|extractor|suspected_injection)\s*[=:]",
    r"\b(ahora\s+)?eres\s+(un|una|el|la)\b",
    r"\b(voc[eê]|tu)\s+(agora\s+)?(é|e|es)\s+(o|a|um|uma)\b",
    r"\bact[uú]a\s+como\b|\bfinge\s+(ser|que)\b|\bfinja\s+(ser|que)\b|\bjailbreak\b|\bmodo\s+(desarrollador|dev)\b",
    # pedir datos de otro cliente
    r"\b(otro|outro)s?\s+clientes?\b|\bclientes?\s*(n[º°o.]?\s*)?\d{2,}|\bCUS-\d+",
    r"\bn[uú]mero\s+completo\b",
)]


def detectar_inyeccion(text: str) -> bool:
    return any(p.search(text) for p in _INYECCION)


# --- Idioma ---------------------------------------------------------------------------------------

_MARCADORES_ES = set("""
    reconozco cobraron cobro cobró cargo cargos tarjeta mi mis yo hice hicieron ayer hoy anteayer pasada
    dos veces un una el la los las y en del al con pero mío mía sé hola quiero préstamo hay llegó tengo lo
    junio mayo entre fue oye entiendo olvida ahora eres asistente mensaje sí si también otro esta este
    pedido nunca llegó cuánto cómo está estoy
""".split())
_MARCADORES_PT = set("""
    não nao reconheço reconheco cobrança cobranca cobraram cobrou cartão cartao cartões você voce meu minha
    eu fiz uma um sim ontem hoje passada duas vezes na numa do da teve tem apareceu olá oi quero pode
    seguir também outra outro essa esse isso e é foi esquece disse reais corrida agora passa número
    comprei regras confirme bloqueio junho maio primeiro primeira segunda segundo terceiro terceira
    obrigado obrigada entende mesma mesmo pedi
""".split())
# palabras que están en las dos listas no suman a ninguno
_AMBOS = _MARCADORES_ES & _MARCADORES_PT
_MARCADORES_ES -= _AMBOS
_MARCADORES_PT -= _AMBOS
_ARTICULO_PT_INICIAL = re.compile(r"^\s*(o|a|os|as)\s+\w", re.I)  # "a última", "o primeiro"


def detectar_idioma(text: str) -> str:
    palabras = re.findall(r"[\wáéíóúâêôãõçñü]+", text.lower())
    es = sum(p in _MARCADORES_ES for p in palabras)
    pt = sum(p in _MARCADORES_PT for p in palabras) + bool(_ARTICULO_PT_INICIAL.search(text))
    if "semana passada" in text.lower():
        pt += 1
    return "pt" if pt > es else "es"


# --- Fechas ---------------------------------------------------------------------------------------

_MESES = {
    "enero": 1, "janeiro": 1, "febrero": 2, "fevereiro": 2, "marzo": 3, "marco": 3, "abril": 4,
    "mayo": 5, "maio": 5, "junio": 6, "junho": 6, "julio": 7, "julho": 7, "agosto": 8,
    "septiembre": 9, "setiembre": 9, "setembro": 9, "octubre": 10, "outubro": 10,
    "noviembre": 11, "novembro": 11, "diciembre": 12, "dezembro": 12,
}
_DIAS_SEMANA = {
    "lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6,
    "segunda-feira": 0, "terca-feira": 1, "terca": 1, "quarta-feira": 2, "quarta": 2,
    "quinta-feira": 3, "quinta": 3, "sexta-feira": 4, "sexta": 4,
}
_MES = r"(?P<mes>" + "|".join(sorted(_MESES, key=len, reverse=True)) + r")"
_RANGO = re.compile(r"\b(entre\s+(el\s+)?(dia\s+)?|del?\s+(dia\s+)?|desde\s+(el\s+)?(dia\s+)?)(?P<d1>\d{1,2})"
                    r"\s+(y|e|al?|ao|hasta|ate)\s+(el\s+)?(dia\s+)?(?P<d2>\d{1,2})(\s+de)?\s+" + _MES + r"\b")
_DIA_MES = re.compile(r"\b(?P<d>\d{1,2})\s+de\s+" + _MES + r"\b")
_DIA_BARRA = re.compile(r"\b(?P<d>\d{1,2})/(?P<m>\d{1,2})(/(?P<a>\d{2,4}))?\b")
_DIA_SOLO = re.compile(r"\b(el\s+)?dia\s+(?P<d>\d{1,2})\b")
_HACE_DIAS = re.compile(r"\b(hace|ha)\s+(?P<n>\d{1,2})\s+dias?\b")
_DIA_SEMANA = re.compile(r"\b(el|na|no|este|esta|ultimo|ultima|pasado|passada)\s+(?P<ds>"
                         + "|".join(sorted(_DIAS_SEMANA, key=len, reverse=True)) + r")\b"
                         r"|\b(?P<dsf>segunda-feira|terca-feira|quarta-feira|quinta-feira|sexta-feira)\b")


def _fecha_sin_anio(dia: int, mes: int, ref: date) -> date | None:
    try:
        d = date(ref.year, mes, dia)
    except ValueError:
        return None
    return d.replace(year=ref.year - 1) if d > ref else d


def _fecha_sin_mes(dia: int, ref: date) -> date | None:
    anio, mes = (ref.year, ref.month) if dia <= ref.day else (
        (ref.year, ref.month - 1) if ref.month > 1 else (ref.year - 1, 12))
    try:
        return date(anio, mes, dia)
    except ValueError:
        return None


def extraer_fechas(text: str, ref: date) -> tuple[date | None, date | None, list[tuple[int, int]]]:
    """Devuelve (date_from, date_to, tramos del texto usados), para no leerlos después como montos."""
    t = _sin_tildes(text.lower())  # misma longitud que text: los tramos sirven sobre el original
    if len(t) != len(text):
        t = text.lower()

    if m := _RANGO.search(t):
        d1 = _fecha_sin_anio(int(m["d1"]), _MESES[m["mes"]], ref)
        d2 = _fecha_sin_anio(int(m["d2"]), _MESES[m["mes"]], ref)
        if d1 and d2 and d1 <= d2:
            return d1, d2, [m.span()]
    if m := _DIA_MES.search(t):
        if d := _fecha_sin_anio(int(m["d"]), _MESES[m["mes"]], ref):
            return d, d, [m.span()]
    if m := _DIA_BARRA.search(t):
        try:
            anio = int(m["a"]) if m["a"] else None
            if anio is not None and anio < 100:
                anio += 2000
            d = date(anio, int(m["m"]), int(m["d"])) if anio else _fecha_sin_anio(int(m["d"]), int(m["m"]), ref)
        except ValueError:
            d = None
        if d and d <= ref:
            return d, d, [m.span()]
    if m := _HACE_DIAS.search(t):
        d = ref - timedelta(days=int(m["n"]))
        return d, d, [m.span()]
    if m := _DIA_SOLO.search(t):
        if d := _fecha_sin_mes(int(m["d"]), ref):
            return d, d, [m.span()]

    if re.search(r"\b(anteayer|antier|anteontem)\b", t):
        d = ref - timedelta(days=2)
        return d, d, []
    if re.search(r"\b(ayer|ontem)\b", t):
        d = ref - timedelta(days=1)
        return d, d, []
    if re.search(r"\b(hoy|hoje)\b", t):
        return ref, ref, []
    lunes = ref - timedelta(days=ref.weekday())
    if re.search(r"\bsemana\s+pasada\b|\bsemana\s+passada\b|\bultima\s+semana\b|\bsemana\s+anterior\b", t):
        return lunes - timedelta(days=7), lunes - timedelta(days=1), []
    if re.search(r"\besta\s+semana\b", t):
        return lunes, ref, []
    if re.search(r"\bmes\s+pasado\b|\bmes\s+passado\b|\bmes\s+anterior\b|\bultimo\s+mes\b", t):
        fin = ref.replace(day=1) - timedelta(days=1)
        return fin.replace(day=1), fin, []
    if re.search(r"\beste\s+mes\b", t):
        return ref.replace(day=1), ref, []
    if m := re.search(r"\b(en|em|de|no|durante)\s+" + _MES + r"\b", t):
        mes = _MESES[m["mes"]]
        anio = ref.year if mes <= ref.month else ref.year - 1
        fin = min(date(anio, mes, calendar.monthrange(anio, mes)[1]), ref)
        return date(anio, mes, 1), fin, [m.span()]
    if m := _DIA_SEMANA.search(t):
        objetivo = _DIAS_SEMANA[m["ds"] or m["dsf"]]
        atras = (ref.weekday() - objetivo) % 7 or 7  # el más reciente ANTES de hoy
        d = ref - timedelta(days=atras)
        return d, d, []
    return None, None, []


# --- Monto ----------------------------------------------------------------------------------------

_NUMERO = re.compile(
    r"(?<![\w.,-])"
    r"(?P<num>\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?"  # 3.500 · 1.200.000 · 1.200,50
    r"|\d+,\d{1,2}(?!\d)"  # 350,50
    r"|\d+\.\d{2}(?!\d)"  # 350.50 (dos decimales tras el punto)
    r"|\d+)"
    r"(?![\w-]|[.,]\d)"
    r"(?P<mil>\s+mil\b)?", re.I)
# números que son parte de otra cosa: un id, un cliente, una orden inyectada, el final de la tarjeta
_NO_ES_MONTO = re.compile(
    r"(\b(clientes?|customer|caso|case|id|amount|monto|opci[oó]n|op[cç][aã]o|terminada\s+en|final|"
    r"termina\s+en|tarjeta|cart[aã]o|n[uú]mero|dsp|conv)\s*(n[º°o.]?)?\s*[=:#-]?\s*|•+\s*)$", re.I)

_PALABRAS_NUM = {
    "cien": 100, "ciento": 100, "cem": 100, "doscientos": 200, "doscientas": 200, "duzentos": 200,
    "duzentas": 200, "trescientos": 300, "trezentos": 300, "cuatrocientos": 400, "quatrocentos": 400,
    "quinientos": 500, "quinhentos": 500, "seiscientos": 600, "seiscentos": 600, "setecientos": 700,
    "setecentos": 700, "ochocientos": 800, "oitocentos": 800, "novecientos": 900, "novecentos": 900,
    "mil": 1000,
}
_PALABRA_MONTO = re.compile(r"\b(?P<w>" + "|".join(sorted(_PALABRAS_NUM, key=len, reverse=True))
                            + r")(?P<mil>\s+mil)?\b", re.I)


def _a_float(num: str) -> float:
    if "," in num:  # coma decimal; los puntos son miles
        return float(num.replace(".", "").replace(",", "."))
    if re.fullmatch(r"\d+\.\d{2}", num):  # 350.50
        return float(num)
    return float(num.replace(".", ""))  # 3.500 · 1.200.000


def _tapar(text: str, tramos: list[tuple[int, int]]) -> str:
    for a, b in tramos:
        text = text[:a] + " " * (b - a) + text[b:]
    return text


def extraer_monto(text: str, tapar: list[tuple[int, int]] = ()) -> float | None:
    t = _tapar(text, list(tapar))
    for m in _NUMERO.finditer(t):
        if _NO_ES_MONTO.search(t[:m.start()]):
            continue
        valor = _a_float(m["num"]) * (1000 if m["mil"] else 1)
        if valor > 0:
            return valor
    for m in _PALABRA_MONTO.finditer(t):
        return float(_PALABRAS_NUM[m["w"].lower()] * (1000 if m["mil"] else 1))
    return None


# --- Moneda ---------------------------------------------------------------------------------------

_MONEDAS = {
    "USD": re.compile(r"\bUSD\b|US\$|U\$S|\bd[oó]lar(es)?\b|\bdollars?\b", re.I),
    "ARS": re.compile(r"\bARS\b|\bpesos?\s+argentinos?\b", re.I),
    "COP": re.compile(r"\bCOP\b|\bpesos?\s+colombianos?\b", re.I),
}


def extraer_moneda(text: str) -> str | None:
    """"$", "pesos" a secas, "R$" o "reais" → None (el NLU no sabe el país; BRL no está en el contrato)."""
    halladas = [c for c, p in _MONEDAS.items() if p.search(text)]
    return halladas[0] if len(halladas) == 1 else None


# --- Comercio -------------------------------------------------------------------------------------

_MARCAS = ["Mercado Libre", "Mercado Pago", "iFood", "Rappi", "Uber Eats", "Uber", "Oxxo", "Netflix",
           "Spotify", "Amazon", "Éxito", "Didi", "Cabify", "Starbucks", "McDonald's", "Walmart",
           "Falabella", "Carrefour", "Disney", "Apple", "Google", "Steam", "PedidosYa", "Despegar"]
_MARCA = re.compile(r"\b(" + "|".join(re.escape(m) for m in _MARCAS) + r")\b", re.I)
# pistas genéricas: se devuelven en minúscula y sin tilde (el backend busca por "contiene")
_GENERICOS = [
    (re.compile(r"\bfarm[aá]cia\b", re.I), "farmacia"),
    (re.compile(r"\bs[uú]per(mercado)?\b", re.I), "super"),
    (re.compile(r"\bgasolinera\b", re.I), "gasolinera"),
    (re.compile(r"\bferreter[ií]a\b", re.I), "ferreteria"),
    (re.compile(r"\b[oó]ptica\b", re.I), "optica"),
    (re.compile(r"\bcl[ií]nica\b", re.I), "clinica"),
    (re.compile(r"\bcine\b", re.I), "cine"),
    (re.compile(r"\bteatro\b", re.I), "teatro"),
    (re.compile(r"\btaxi\b", re.I), "taxi"),
]
# nombre propio tras una preposición ("en Starbucks", "no Magalu") para marcas fuera de la lista
_PROPIO = re.compile(r"\b(?:en|no|na|do|da|del|de)\s+(?:el\s+|la\s+|o\s+|a\s+)?"
                     r"(?P<n>[A-ZÁÉÍÓÚ][\w'&]+(?:\s+[A-ZÁÉÍÓÚ][\w'&]+)?)")
_NO_PROPIO = {"USD", "ARS", "COP", "US", "R", "SYSTEM", "PD"} | {m.capitalize() for m in _MESES}
_NEGADO = re.compile(r"\b(no|n[aã]o)\s+(en|no|na|de|do|da)\s+(el\s+|la\s+)?$", re.I)  # "..., não no Rappi"


def extraer_comercio(text: str) -> str | None:
    candidatos: list[tuple[int, str]] = [(m.start(), m.group(1)) for m in _MARCA.finditer(text)]
    candidatos += [(m.start(), valor) for p, valor in _GENERICOS for m in p.finditer(text)]
    candidatos += [(m.start("n"), m["n"]) for m in _PROPIO.finditer(text)
                   if m["n"].split()[0] not in _NO_PROPIO and not _MARCA.search(m["n"])]
    candidatos = [(i, c) for i, c in sorted(candidatos) if not _NEGADO.search(text[:i])]
    if not candidatos:
        return None
    i, c = candidatos[0]
    m = _MARCA.fullmatch(c)
    return next(x for x in _MARCAS if x.lower() == c.lower()) if m else c


# --- Opción elegida -------------------------------------------------------------------------------

_ORDINALES = {
    "primero": 1, "primera": 1, "primer": 1, "primeiro": 1, "segundo": 2, "segunda": 2,
    "tercero": 3, "tercera": 3, "tercer": 3, "terceiro": 3, "terceira": 3, "cuarto": 4, "cuarta": 4,
    "quarto": 4, "quarta": 4, "quinto": 5, "quinta": 5, "ultimo": -1, "ultima": -1,
}
_OPCION = re.compile(
    r"^\s*(?:(?:el|la|lo|o|a)\s+)?(?:(?:opci[oó]n|op[cç][aã]o|n[uú]mero)\s+)?"
    r"(?P<ord>" + "|".join(_ORDINALES) + r"|[úu]ltim[oa])\b"
    r"|^\s*(?:(?:el|la|o|a)\s+)?(?:opci[oó]n|op[cç][aã]o|n[uú]mero)\s+(?P<n>\d)\b"
    r"|^\s*(?:el|la|o|a)\s+(?P<n2>\d)\s*$", re.I)


def extraer_opcion(text: str) -> tuple[int | None, list[tuple[int, int]]]:
    """Posición que empieza en 1; "la última" = -1 (⏳ pendiente de acordar con Alina)."""
    m = _OPCION.search(text)
    if not m:
        return None, []
    if m["ord"]:
        return _ORDINALES[_sin_tildes(m["ord"].lower())], []
    return int(m["n"] or m["n2"]), [m.span()]


# --- Confirmación ---------------------------------------------------------------------------------

_SI = {"si", "sim", "ok", "okay", "okey", "dale", "confirmo", "confirmar", "claro", "correcto", "exacto",
       "perfecto", "adelante", "listo", "va", "isso", "certo", "yes", "bueno", "sale", "hazlo", "acuerdo",
       "confirma", "confirme", "beleza", "fechado", "pode"}
_NO = {"no", "nao", "cancelar", "cancela", "cancele", "cancelo", "negativo", "nope", "nunca"}
_RELLENO = {"seguir", "por", "favor", "gracias", "obrigado", "obrigada", "esta", "bien", "bem", "ta", "de",
            "claro", "mejor", "melhor", "gracia", "entonces", "entao", "si,", "pues", "que", "sigue", "siga",
            "fazer", "faca", "haz", "hacelo", "todo", "tudo", "vale", "eso", "lo", "la", "o", "a"}


def extraer_confirmacion(text: str, state: str | None) -> str | None:
    """Solo respuestas cortas de sí/no (§1.3). "No reconozco otro cargo" → None."""
    if state is not None and state != "CONFIRMAR_ACCION":
        return None
    palabras = re.findall(r"\w+", _sin_tildes(text.lower()))
    if not palabras or len(palabras) > 6 or any(p not in _SI | _NO | _RELLENO for p in palabras):
        return None
    si, no = any(p in _SI for p in palabras), any(p in _NO for p in palabras)
    if si == no:  # ninguna o las dos ("no, mejor sí")
        return None
    return "yes" if si else "no"


# --- Todo junto -----------------------------------------------------------------------------------

def extract(text: str, state: str | None = None, reference_date: date | None = None) -> dict[str, Any]:
    """Campos de NLUResult menos intent/intent_confidence/abstain. Nunca lanza."""
    out: dict[str, Any] = {c: None for c in CAMPOS}
    out.update(language="es", suspected_injection=False)
    text = (text or "")[:2000]
    pasos = []
    try:
        ref = reference_date or _reference_date()
    except Exception:  # noqa: BLE001 - sin policy.yaml no hay fechas, pero lo demás sigue
        log.exception("rules: no pude leer reference_date")
        ref = None

    def paso(nombre, f):
        try:
            return f()
        except Exception:  # noqa: BLE001
            log.exception("rules: falló %s", nombre)
            pasos.append(nombre)
            return None

    inj = paso("injection", lambda: detectar_inyeccion(text))
    out["suspected_injection"] = bool(inj)
    out["language"] = paso("language", lambda: detectar_idioma(text)) or "es"

    tapar: list[tuple[int, int]] = []
    if ref is not None and (r := paso("dates", lambda: extraer_fechas(text, ref))):
        out["date_from"], out["date_to"], tramos = r
        tapar += tramos
    # sin state, solo respuestas cortas: "la segunda vez que me cobraron" no es elegir una opción
    corto = len(text.split()) <= 5
    if (state == "IDENTIFICAR_TRANSACCION" or (state is None and corto)) and (
            r := paso("option", lambda: extraer_opcion(text))):
        out["selected_option"], tramos = r
        tapar += tramos
    out["amount"] = paso("amount", lambda: extraer_monto(text, tapar))
    out["currency"] = paso("currency", lambda: extraer_moneda(text))
    out["merchant_hint"] = paso("merchant", lambda: extraer_comercio(text))
    out["confirmation"] = None if inj else paso("confirmation", lambda: extraer_confirmacion(text, state))
    return out
