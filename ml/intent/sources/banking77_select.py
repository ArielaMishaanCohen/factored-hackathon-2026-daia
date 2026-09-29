"""Paso 4 de la Fase 4.1: filtra, muestrea y marca sospechosas de Banking77.

Uso: .venv/bin/python -m ml.intent.sources.banking77_select

1. Lee data/external/banking77.csv y ml/intent/b77_mapeo.csv (columna decision).
2. Elimina duplicados exactos (ignorando mayúsculas y puntuación).
3. Muestrea con semilla 42 hasta los topes de la guía, estratificando por clase
   original de Banking77 (asignación proporcional al tamaño de cada clase).
4. Marca como sospechosas las frases donde las reglas de
   ml/intent/labeling_guide.md (1.2) sugieren otra etiqueta.
5. Escribe ml/intent/b77_seleccion.csv.

Casos especiales del mapeo:
- cobro_incorrecto_o_fuera_de_alcance (comisiones): label_inicial sale de la
  heurística de comisiones y todas van a revisión. Las que quedan como
  cobro_incorrecto cuentan en su tope; las demás, en el de negativos difíciles.
- por_decidir (lost_or_stolen_phone): se incluye una muestra chica, fuera de los
  topes, con label_inicial vacía y todas marcadas para revisión.
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
RAW_PATH = ROOT / "data" / "external" / "banking77.csv"
MAPEO_PATH = ROOT / "ml" / "intent" / "b77_mapeo.csv"
OUT_PATH = ROOT / "ml" / "intent" / "b77_seleccion.csv"

SEED = 42

# Topes del Paso 4 de docs/Rol B - ML/guia_fase_4_1_etiquetado.md.
TOPES = {
    "cargo_no_reconocido": 450,
    "cobro_incorrecto": 450,
    "tarjeta_comprometida": 350,
    "fuera_de_alcance_dificil": 350,
    "fuera_de_alcance_resto": 250,
}
N_COMISIONES = 60  # por clase de comisiones
N_POR_DECIDIR = 30

DECISION_A_LABEL = {
    "cargo_no_reconocido": "cargo_no_reconocido",
    "cobro_incorrecto": "cobro_incorrecto",
    "tarjeta_comprometida": "tarjeta_comprometida",
    "fuera_de_alcance_dificil": "fuera_de_alcance",
    "fuera_de_alcance_resto": "fuera_de_alcance",
}

# --- Patrones de las reglas (sobre el texto en inglés, en minúsculas) --------

R1_COMPROMETIDA = re.compile(
    r"\b(stole|stolen|steal|theft|thief|lost my (card|wallet|purse)|my card (is|was|has been|got) (lost|missing)"
    r"|(card|wallet|purse) (is|was|went|has gone) missing|clon(e|ed|ing)|skimm|hack(ed|er)?|compromised"
    r"|fraud|someone (else )?(has )?(is |has been )?us(ed|ing) my card|without my (permission|consent|agreement)"
    r"|(several|multiple|many|lots of|a lot of|numerous) (\w+ )?(payments|transactions|charges|withdrawals)"
    r" (that )?i (didn'?t|did not|never))\b"
)
R2_DISPUTA = re.compile(
    r"\b(disputed|my (dispute|claim|complaint|case|ticket)|the (dispute|claim|complaint) i"
    r"|i (have |already |had )?(filed|opened|raised|submitted|made|started) (a |the )?(dispute|claim|complaint|case|ticket)"
    r"|already (reported|disputed|contacted|told|asked|spoke|called)|reported (it|this) to (you|the bank|support)"
    r"|status of (my |the )?(dispute|claim|complaint|refund request)|reference number|still no (answer|response|reply))\b"
)
R3_COBRO = re.compile(
    r"\b(twice|double|doubled|duplicate|duplicated|two times|charged (me )?(more|too much|extra)"
    r"|overcharg\w*|wrong (amount|rate|exchange|price)|incorrect (amount|rate|charge|exchange)"
    r"|exchange rate (is|was|applied) (wrong|incorrect|off|bad)|after (i )?cancel\w*"
    r"|(did ?n'?t|did not|never) (get|receive|give me) (the )?(full|right|correct|enough)|less (cash|money) than"
    r"|different amount|more than (i|what i)|repeated)\b"
)
R4_NO_RECONOCIDO = re.compile(
    r"\b(don'?t|do not|didn'?t|did not|can'?t|cannot|can not) (recogni[sz]e|know|remember|make|authori[sz]e)"
    r"|unrecogni[sz]ed|unknown|unauthori[sz]ed|not mine|wasn'?t me|never made|no idea (what|where)\b"
)
COMISION = re.compile(r"\b(fee|fees|charge|charged|charges|commission|cost)\b")
QUEJA_COMISION = re.compile(
    r"\b(shouldn'?t|should not|should ?n'?t have|wrong(ly)?|incorrect(ly)?|unfair|mistake|error|glitch|overcharg\w*"
    r"|by mistake|not supposed|(supposed to be|was|were|is|are) free|i thought|under the impression|told (me )?(there|it)"
    r"|promised|no fee|twice|double|refund|get (it|my money) back"
    r"|unexpected|without (warning|notice)|scam|ridiculous)\b"
)
RECHAZO = re.compile(r"\b(declin\w*|(did ?n'?t|did not|does ?n'?t|won'?t|not) work\w*)\b")
TRAGADA_ATM = re.compile(r"\b(atm|machine|cash ?point)\b")
PREGUNTA_GENERAL = re.compile(r"^\W*(what|how|does|do|is|are|can|where|when|will)\b")
QUEJA_CAMBIO = re.compile(r"\b(correct|higher|different|terrible|bad|awful|more|too|expected|off|not right|poor|fair)\b")
PENDIENTE = re.compile(r"\b(pending|still waiting|hasn'?t (gone|come) through|not (yet )?(show|post|appear))")
REEMBOLSO_COMERCIO = re.compile(r"\b(seller|merchant|store|shop|vendor)\b.*\brefund|\brefund\b.*\b(seller|merchant|store|shop|vendor)\b")
TARJETA = re.compile(r"\bcard\b")


def normalizar(texto: str) -> str:
    texto = re.sub(r"[^\w\s]", " ", texto.lower())
    return re.sub(r"\s+", " ", texto).strip()


def asignacion_proporcional(tamanos: pd.Series, total: int) -> pd.Series:
    """Reparte `total` entre clases en proporción a su tamaño (resto mayor)."""
    total = min(total, int(tamanos.sum()))
    cuota = tamanos / tamanos.sum() * total
    n = np.floor(cuota).astype(int).clip(upper=tamanos)
    faltan = total - n.sum()
    orden = (cuota - n).sort_values(ascending=False).index
    for clase in orden:
        if faltan == 0:
            break
        if n[clase] < tamanos[clase]:
            n[clase] += 1
            faltan -= 1
    return n


def muestrear(pool: pd.DataFrame, total: int) -> pd.DataFrame:
    n = asignacion_proporcional(pool["b77_label"].value_counts(), total)
    partes = [
        g.sample(n=int(n[clase]), random_state=SEED)
        for clase, g in pool.groupby("b77_label", sort=True)
    ]
    return pd.concat(partes)


def label_comision(texto: str) -> tuple[str, str]:
    t = texto.lower()
    if QUEJA_COMISION.search(t):
        return "cobro_incorrecto", "comisión: la considera indebida o mal cobrada (aclaración de comisiones)"
    return "fuera_de_alcance", "comisión: pregunta por qué existe o cuánto cuesta (aclaración de comisiones)"


def sugerir(texto: str, label_inicial: str, b77_label: str) -> tuple[str, str] | None:
    """Aplica las reglas de la guía en orden. Devuelve (label, motivo) si difiere."""
    t = texto.lower()

    recuperada = re.search(r"\b(found (it|my card)|got it back|turned up)\b", t)
    atm = b77_label == "card_swallowed" and TRAGADA_ATM.search(t)
    if R1_COMPROMETIDA.search(t) and label_inicial != "tarjeta_comprometida" and not recuperada and not atm:
        m = R1_COMPROMETIDA.search(t).group(0)
        return "tarjeta_comprometida", f'regla 1: menciona robo/pérdida/clonación/varias compras no hechas ("{m}")'

    if R2_DISPUTA.search(t):
        m = R2_DISPUTA.search(t).group(0)
        return "estado_disputa", f'regla 2: parece preguntar por un reclamo ya hecho ("{m}"); confirmar que fue al banco'

    if label_inicial == "tarjeta_comprometida":
        if recuperada and not re.search(r"\b(stole|stolen)\b", t):
            return "fuera_de_alcance", "tarjeta recuperada o trámite sin robo/pérdida activa"
        return None

    if label_inicial == "cargo_no_reconocido":
        if R3_COBRO.search(t):
            m = R3_COBRO.search(t).group(0)
            return "cobro_incorrecto", f'regla 3: habla de cobro mal hecho ("{m}"), puede que sí reconozca el comercio'
        if PENDIENTE.search(t):
            return "fuera_de_alcance", "aclaración pendientes: algo pendiente o que no se acredita"
        return None

    if label_inicial == "cobro_incorrecto":
        if R4_NO_RECONOCIDO.search(t) and not R3_COBRO.search(t):
            m = R4_NO_RECONOCIDO.search(t).group(0)
            return "cargo_no_reconocido", f'regla 4: no reconoce el cargo ("{m}")'
        if b77_label in {"card_payment_wrong_exchange_rate", "wrong_exchange_rate_for_cash_withdrawal", "extra_charge_on_statement"} \
                and not R3_COBRO.search(t) and not QUEJA_COMISION.search(t) and not QUEJA_CAMBIO.search(t) \
                and PREGUNTA_GENERAL.search(t):
            if b77_label == "extra_charge_on_statement" and not re.search(r"\bfees?\b", t):
                return "cargo_no_reconocido", "regla 4: pregunta qué es un cargo que no identifica, sin decir que está mal"
            return "fuera_de_alcance", "aclaración comisiones: pregunta cómo funciona o por qué existe, sin decir que está mal"
        return None

    # fuera_de_alcance (difíciles y resto)
    if REEMBOLSO_COMERCIO.search(t):
        return None  # aclaración: reembolso del comercio -> fuera_de_alcance
    if PENDIENTE.search(t) and not R3_COBRO.search(t):
        return None  # aclaración: pendientes -> fuera_de_alcance
    if RECHAZO.search(t) and not re.search(r"\b(charged|fee|debited|taken)\b", t):
        return None  # aclaración: pago rechazado -> fuera_de_alcance
    if R3_COBRO.search(t):
        m = R3_COBRO.search(t).group(0)
        return "cobro_incorrecto", f'regla 3: habla de cobro mal hecho ("{m}")'
    if COMISION.search(t) and QUEJA_COMISION.search(t) and re.search(r"\bcharged\b|\bfee\b", t):
        return "cobro_incorrecto", "aclaración comisiones: dice que la comisión/cargo está mal o no debió cobrarse"
    if R4_NO_RECONOCIDO.search(t) and re.search(r"\b(payment|charge|transaction|withdrawal|debit)\b", t):
        m = R4_NO_RECONOCIDO.search(t).group(0)
        return "cargo_no_reconocido", f'regla 4: no reconoce un cargo ("{m}")'
    return None


def main() -> None:
    df = pd.read_csv(RAW_PATH).rename(columns={"text": "text_en"})
    mapeo = pd.read_csv(MAPEO_PATH)
    decision = dict(zip(mapeo["b77_label"], mapeo["decision"]))
    df["decision"] = df["b77_label"].map(decision)
    assert df["decision"].notna().all(), "hay clases sin decision en el mapeo"

    df["_norm"] = df["text_en"].map(normalizar)
    antes = len(df)
    df = df.drop_duplicates("_norm", keep="first")
    print(f"Duplicados exactos eliminados (sin mayúsculas ni puntuación): {antes - len(df)}")

    # Comisiones: etiqueta por heurística, todas a revisión.
    com = df[df["decision"] == "cobro_incorrecto_o_fuera_de_alcance"]
    com = muestrear(com, N_COMISIONES * com["b77_label"].nunique())
    com[["label_inicial", "_motivo_com"]] = com["text_en"].apply(lambda t: pd.Series(label_comision(t)))
    n_com_cobro = int((com["label_inicial"] == "cobro_incorrecto").sum())
    n_com_fuera = len(com) - n_com_cobro

    topes = dict(TOPES)
    topes["cobro_incorrecto"] -= n_com_cobro
    topes["fuera_de_alcance_dificil"] -= n_com_fuera

    partes = []
    for dec, tope in topes.items():
        pool = df[df["decision"] == dec]
        s = muestrear(pool, tope)
        s["label_inicial"] = DECISION_A_LABEL[dec]
        partes.append(s)

    phone = muestrear(df[df["decision"] == "por_decidir"], N_POR_DECIDIR)
    phone["label_inicial"] = ""

    sel = pd.concat(partes, ignore_index=True)
    sel["sospechosa"] = "no"
    sel["label_sugerida"] = ""
    sel["motivo"] = ""
    for i, fila in sel.iterrows():
        r = sugerir(fila["text_en"], fila["label_inicial"], fila["b77_label"])
        if r and r[0] != fila["label_inicial"]:
            sel.loc[i, ["sospechosa", "label_sugerida", "motivo"]] = ["sí", r[0], r[1]]

    com = com.reset_index(drop=True)
    com["sospechosa"] = "sí"
    com["motivo"] = com["_motivo_com"] + "; clase mixta, revisar"
    com["label_sugerida"] = com["label_inicial"]
    for i, fila in com.iterrows():
        r = sugerir(fila["text_en"], fila["label_inicial"], fila["b77_label"])
        if r and r[0] in {"tarjeta_comprometida", "estado_disputa", "cargo_no_reconocido"}:
            com.loc[i, ["label_sugerida", "motivo"]] = [r[0], r[1] + "; clase mixta (comisiones)"]

    phone = phone.reset_index(drop=True)
    phone["sospechosa"] = "sí"
    habla_tarjeta = phone["text_en"].str.lower().str.contains(TARJETA)
    phone["label_sugerida"] = np.where(habla_tarjeta, "tarjeta_comprometida", "fuera_de_alcance")
    phone["motivo"] = np.where(
        habla_tarjeta,
        "por_decidir: celular perdido/robado y además menciona la tarjeta",
        "por_decidir: habla solo del celular/app (lost_or_stolen_phone sin decisión en el mapeo)",
    )

    sel = pd.concat([sel, com, phone], ignore_index=True)
    sel["label_final"] = np.where(sel["sospechosa"] == "no", sel["label_inicial"], "")
    sel = sel.sort_values("b77_idx")
    cols = ["b77_idx", "b77_label", "text_en", "label_inicial", "sospechosa", "label_sugerida", "motivo", "label_final"]
    sel[cols].to_csv(OUT_PATH, index=False)

    print(f"\n{len(sel)} frases -> {OUT_PATH.relative_to(ROOT)}\n")
    resumen = pd.crosstab(sel["label_inicial"].replace("", "(por_decidir)"), sel["sospechosa"], margins=True, margins_name="total")
    print("Por label_inicial y sospechosa:\n", resumen.to_string(), "\n")
    sos = sel[sel["sospechosa"] == "sí"]
    print("Sospechosas por label_inicial -> label_sugerida:\n",
          pd.crosstab(sos["label_inicial"].replace("", "(por_decidir)"), sos["label_sugerida"]).to_string())


if __name__ == "__main__":
    main()
