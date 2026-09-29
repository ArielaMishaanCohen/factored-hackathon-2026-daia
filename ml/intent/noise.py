"""Paso 9 de la Fase 4.1: ruido de chat reproducible para train/val.

Uso (desde build_dataset.py):
    texto_ruidoso, transformaciones = aplicar_ruido(texto, language, clave=id)

Cada frase recibe cero o más transformaciones y se registran en una lista
(campo `noise` del JSONL). El test nunca pasa por aquí: su ruido es el natural.

- ~30 % de las frases quedan sin ruido.
- El 70 % restante recibe cada transformación con probabilidad P / 0,7, así la
  proporción sobre el total queda cerca de P (tabla PROBS). Si por azar no le
  toca ninguna, se fuerza una, para que "con ruido" siempre signifique algo.
- Una transformación solo se registra si cambió el texto (p. ej., sin_tildes en
  una frase sin tildes no cuenta).
- Los números y montos ("1,250", "18.400", "3:00", "24/09") están protegidos:
  ninguna transformación los toca.
- El azar depende de SEED y de la clave de la frase (su id), no del orden en que
  se procesan: agregar o quitar frases no cambia el ruido de las demás.
"""

import random
import re
import unicodedata

SEED = 42
P_SIN_RUIDO = 0.30

# Proporción objetivo sobre el total de frases.
PROBS = {
    "abreviaturas": 0.30,
    "sin_tildes": 0.50,
    "minusculas": 0.40,
    "sin_puntuacion": 0.40,
    "typo": 0.25,
    "repetidos": 0.10,
    "emoji": 0.10,
}
TRANSFORMACIONES = tuple(PROBS)  # también es el orden de aplicación

# Números con separadores internos: 1,250 · 18.400 · 3:00 · 24/09 · 5
_NUMERO = re.compile(r"\d(?:[\d.,:/]*\d)?")

# Abreviaturas de chat. Cada coincidencia se abrevia con probabilidad P_ABREV,
# para que no quede todo abreviado de forma mecánica.
P_ABREV = 0.8
_ABREV_ES = [
    (r"por qu[eé]", "xq"),
    (r"porque", "xq"),
    (r"qu[eé]", "q"),
    (r"tambi[eé]n", "tb"),
    (r"por favor", "porfa"),
    (r"para", "pa"),
    (r"está", "ta"),  # solo con tilde: "esta tarjeta" no se toca
]
_ABREV_PT = [
    (r"por qu[eê]", "pq"),
    (r"porque", "pq"),
    (r"qu[eê]", "q"),
    (r"voc[eê]s", "vcs"),
    (r"voc[eê]", "vc"),
    (r"n[aã]o", "n"),
    (r"tamb[eé]m", "tb"),
    (r"por favor", "pfv"),
    (r"quando", "qdo"),
    (r"tudo", "td"),
    (r"está", "tá"),
]
ABREVIATURAS = {
    "es": _ABREV_ES,
    "pt": _ABREV_PT,
    "mix": _ABREV_ES + [p for p in _ABREV_PT if p[0] not in dict(_ABREV_ES)],
}

EMOJIS = ["🙏", "😡", "😭", "😩", "🤔", "😕", "😤", "🥲", "😒", "🤦"]
_PUNTUACION = set(".,;:¡!¿?\"'()…—«»“”")  # sin "-": "sexta-feira", "e-mail"


def _segmentos(texto: str) -> list[tuple[str, bool]]:
    """Parte el texto en (trozo, es_numero). Los números no se tocan."""
    partes, inicio = [], 0
    for m in _NUMERO.finditer(texto):
        if m.start() > inicio:
            partes.append((texto[inicio : m.start()], False))
        partes.append((m.group(), True))
        inicio = m.end()
    if inicio < len(texto):
        partes.append((texto[inicio:], False))
    return partes


def _en_texto(texto: str, fn) -> str:
    """Aplica fn solo a los trozos que no son números."""
    return "".join(t if es_num else fn(t) for t, es_num in _segmentos(texto))


def numeros(texto: str) -> list[str]:
    return _NUMERO.findall(texto)


# --- Transformaciones ------------------------------------------------------


def _abreviaturas(texto: str, language: str, rng: random.Random) -> str:
    def reemplazar(m: re.Match, corto: str) -> str:
        if rng.random() >= P_ABREV:
            return m.group()
        return corto.upper() if m.group()[0].isupper() and len(corto) == 1 else corto

    def fn(t: str) -> str:
        for patron, corto in ABREVIATURAS[language]:
            t = re.sub(rf"\b{patron}\b", lambda m, c=corto: reemplazar(m, c), t, flags=re.IGNORECASE)
        return t

    return _en_texto(texto, fn)


def _sin_tildes(texto: str, language: str, rng: random.Random) -> str:
    def quitar(c: str) -> str:
        if c in "ñÑ":  # la ñ no es tilde
            return c
        base = unicodedata.normalize("NFD", c)
        return "".join(ch for ch in base if unicodedata.category(ch) != "Mn")

    return "".join(quitar(c) for c in texto)


def _minusculas(texto: str, language: str, rng: random.Random) -> str:
    return texto.lower()


def _sin_puntuacion(texto: str, language: str, rng: random.Random) -> str:
    texto = _en_texto(texto, lambda t: "".join(c for c in t if c not in _PUNTUACION))
    return re.sub(r"[ \t]{2,}", " ", texto).strip()


def _typo(texto: str, language: str, rng: random.Random) -> str:
    partes = _segmentos(texto)
    # Palabras de 4+ letras en los trozos que no son números.
    candidatas = [
        (i, m)
        for i, (t, es_num) in enumerate(partes)
        if not es_num
        for m in re.finditer(r"[^\W\d_]{4,}", t)
    ]
    if not candidatas:
        return texto
    i, m = rng.choice(candidatas)
    palabra = m.group()
    j = rng.randrange(1, len(palabra) - 1)  # no toca la primera letra
    if rng.random() < 0.5 and palabra[j] != palabra[j + 1]:
        nueva = palabra[:j] + palabra[j + 1] + palabra[j] + palabra[j + 2 :]  # intercambio
    else:
        nueva = palabra[:j] + palabra[j + 1 :]  # omisión
    t = partes[i][0]
    partes[i] = (t[: m.start()] + nueva + t[m.end() :], False)
    return "".join(t for t, _ in partes)


def _repetidos(texto: str, language: str, rng: random.Random) -> str:
    fin = texto.rstrip()
    if fin and fin[-1] in "?!" and rng.random() < 0.6:
        return fin + fin[-1] * rng.randint(1, 3)
    # Alarga la última vocal de la última palabra: "hola" -> "holaaa".
    partes = _segmentos(texto)
    for i in range(len(partes) - 1, -1, -1):
        t, es_num = partes[i]
        if es_num:
            continue
        m = None
        for m in re.finditer(r"[aeiouáéíóúãõê](?=[^\W\d_]*[^\w]*$)", t, flags=re.IGNORECASE):
            pass
        if m:
            vocal = m.group()
            partes[i] = (t[: m.end()] + vocal * rng.randint(2, 3) + t[m.end() :], False)
            return "".join(t for t, _ in partes)
    return texto


def _emoji(texto: str, language: str, rng: random.Random) -> str:
    return texto.rstrip() + " " + rng.choice(EMOJIS)


_FUNCIONES = {
    "abreviaturas": _abreviaturas,
    "sin_tildes": _sin_tildes,
    "minusculas": _minusculas,
    "sin_puntuacion": _sin_puntuacion,
    "typo": _typo,
    "repetidos": _repetidos,
    "emoji": _emoji,
}


def aplicar_ruido(texto: str, language: str, clave: str) -> tuple[str, list[str]]:
    """Devuelve (texto con ruido, lista de transformaciones que lo cambiaron)."""
    rng = random.Random(f"{SEED}:{clave}")
    if rng.random() < P_SIN_RUIDO:
        return texto, []

    elegidas = [n for n in TRANSFORMACIONES if rng.random() < PROBS[n] / (1 - P_SIN_RUIDO)]
    if not elegidas:
        elegidas = rng.choices(TRANSFORMACIONES, weights=list(PROBS.values()))

    aplicadas = []
    for nombre in TRANSFORMACIONES:  # orden fijo
        if nombre not in elegidas:
            continue
        nuevo = _FUNCIONES[nombre](texto, language, rng)
        # Frases de solo signos ("??", "…"): quitarles la puntuación las borra.
        if nuevo != texto and nuevo.strip():
            texto = nuevo
            aplicadas.append(nombre)
    return texto, aplicadas
