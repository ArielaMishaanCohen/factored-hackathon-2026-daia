"""Tabla comparativa de todos los candidatos de la Fase 4.2, leída de ml/intent/runs/*_val.json.

Escribe ml/intent/comparacion_candidatos.md. Solo compara: elegir el modelo y τ es el Paso 9
(criterio_seleccion.md). Si hay varios runs con el mismo candidato y params, usa el más nuevo.

    .venv/bin/python -m ml.intent.comparar_candidatos
"""

import json
from pathlib import Path

from ml.intent.evaluate import CLASES, RUNS_DIR

SALIDA = Path(__file__).resolve().parent / "comparacion_candidatos.md"

NOMBRES = {
    "mayoritaria": "Baseline 0 · clase mayoritaria",
    "reglas": "Baseline 1 · palabras clave",
    "tfidf_lr": "TF-IDF + regresión logística",
    "embeddings_lr": "Embeddings + regresión logística",
    "gemini_zeroshot": "Gemini zero-shot",
}
ORDEN = list(NOMBRES)
CORTO = {"cargo_no_reconocido": "no_rec", "cobro_incorrecto": "cobro_inc", "tarjeta_comprometida": "tarjeta",
         "estado_disputa": "estado", "fuera_de_alcance": "fuera"}


def cargar() -> list[dict]:
    runs = {}
    for ruta in sorted(RUNS_DIR.glob("*_val.json")):  # nombre = fecha: el último pisa a los anteriores
        r = json.loads(ruta.read_text())
        r["_archivo"] = ruta.name
        runs[(r["candidato"], json.dumps(r["params"], sort_keys=True))] = r
    orden_params = lambda r: tuple((k, str(v)) if isinstance(v, str) else (k, "", v)
                                   for k, v in sorted(r["params"].items(), key=lambda kv: kv[0] != "modelo"))
    return sorted(runs.values(), key=lambda r: (ORDEN.index(r["candidato"]) if r["candidato"] in ORDEN else 99,
                                                r["params"].get("clases", 5), orden_params(r)))


def _params(r) -> str:
    p = dict(r["params"])
    if r["candidato"] == "gemini_zeroshot":
        return f"{p['modelo']}, {p['prompt']}"
    return ", ".join(f"{k}={v}" for k, v in p.items()) or "–"


def _pct(v) -> str:
    return f"{v:.1%}".replace(".", ",") if v is not None else "–"


def _num(v, d=3) -> str:
    return f"{v:.{d}f}".replace(".", ",") if v is not None else "–"


def _ms(v) -> str:
    if v is None:
        return "–"
    return f"{v:,.0f}".replace(",", ".") if v >= 100 else _num(v, 1)


def tabla_principal(runs) -> list[str]:
    out = ["| Candidato | Variante | macro-F1 | F1 es | F1 pt | F1 mix | τ | Cobertura | Precisión | "
           "ambiguo abstenidas | Latencia p50 (ms) | Costo por 1.000 (USD) | Tamaño (MB) |",
           "| :-- | :-- | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: |"]
    for r in runs:
        m, t, idi = r["metricas"], r["tau"], r["metricas"]["por_idioma"]
        tam = m.get("tamano_mb", {}).get("total")
        out.append(
            f"| {NOMBRES.get(r['candidato'], r['candidato'])} | {_params(r)} | **{_num(m['macro_f1'])}** | "
            + " | ".join(_num(idi[g]["macro_f1"]) if g in idi else "–" for g in ("es", "pt", "mix"))
            + f" | {_num(t['tau'], 2)} | {_pct(t['cobertura'])} | {_pct(t['precision'])} | "
              f"{_pct(t['ambiguo_abstenidas'])} | {_ms(m['latencia_ms_p50'])} | {_num(m['costo_por_1000_usd'], 2)} | "
              f"{_num(tam, 1) if tam is not None else '–'} |")
    return out


def mejores_por_familia(runs) -> list[dict]:
    fam = {}
    for r in runs:
        c = r["candidato"]
        if c not in fam or r["metricas"]["macro_f1"] > fam[c]["metricas"]["macro_f1"]:
            fam[c] = r
    return [fam[c] for c in sorted(fam, key=lambda c: ORDEN.index(c) if c in ORDEN else 99)]


def tabla_por_clase(runs) -> list[str]:
    out = ["| Candidato | Variante | " + " | ".join(CORTO[c] for c in CLASES) + " |",
           "| :-- | :-- | " + " | ".join("--:" for _ in CLASES) + " |"]
    for r in mejores_por_familia(runs):
        f = r["metricas"]["f1_por_clase"]
        out.append(f"| {NOMBRES.get(r['candidato'], r['candidato'])} | {_params(r)} | "
                   + " | ".join(_num(f[c]) for c in CLASES) + " |")
    return out


def bloque_gemini(runs) -> list[str]:
    gs = [r for r in runs if r["candidato"] == "gemini_zeroshot"]
    out = []
    for r in gs:
        g, m = r["metricas"]["gemini"], r["metricas"]
        tm = g["tokens_media_por_frase"]
        p = g["precio_usd_por_1M"]
        muestra = r["datos"].get("muestra")
        out += [
            f"**{g['modelo']}** (`{r['_archivo']}`)",
            "",
            f"- Frases: {m['n']}" + (f" (muestra estratificada de {r['datos']['val_n_total']})" if muestra else
                                     " (val completo)")
            + f" · errores de la API: {g['n_errores']} · con reintento: {g['n_con_reintento']} · "
              f"respondió `ambiguo`: {g['n_pred_ambiguo']}.",
            f"- Latencia p50 {_ms(m['latencia_ms_p50'])} ms · p95 {_ms(g['latencia_ms_p95'])} ms (solo la API, "
            "sin las esperas por límite de ritmo).",
            f"- Tokens por frase: {tm['entrada']:.0f} de entrada · {tm['salida']:.0f} de salida · "
            f"{tm['razonamiento']:.0f} de razonamiento (se cobran como salida).",
            f"- Costo: USD {_num(g['costo_total_usd'], 2)} por toda la corrida · USD "
            f"{_num(m['costo_por_1000_usd'], 2)} por 1.000 frases, con USD {_num(p['entrada'], 2)} entrada y USD "
            f"{_num(p['salida'], 2)} salida por 1M de tokens ({p['fuente']}).",
            "",
        ]
    return out


def main():
    runs = cargar()
    lineas = [
        "# Comparación de candidatos · clasificador de intención (Fase 4.2)",
        "",
        "Generado con `.venv/bin/python -m ml.intent.comparar_candidatos` a partir de `ml/intent/runs/*_val.json`. "
        "No editar a mano: volver a generar cuando haya runs nuevos.",
        "",
        "Todo es en **val** (507 frases, 45 `ambiguo`). El test no se abrió. Este archivo solo compara: "
        "la elección del modelo y de τ es el Paso 9 y sigue `criterio_seleccion.md` al pie de la letra.",
        "",
        "## Cómo leer la tabla",
        "",
        "- **macro-F1**: promedio simple del F1 de las 5 clases, sin las frases `ambiguo` y sin abstención. "
        "Cada clase pesa igual, aunque tenga pocas frases.",
        "- **F1 es / pt / mix**: el mismo macro-F1, separado por idioma de la frase.",
        "- **τ, cobertura, precisión**: el umbral de confianza con mayor cobertura que da precisión ≥ 95 % "
        "(`criterio_seleccion.md` §4). Cobertura = % de frases que el modelo contesta en vez de pedir aclaración; "
        "precisión = % de esas respuestas que son correctas. Contestar una frase `ambiguo` cuenta como error.",
        "- **ambiguo abstenidas**: con ese τ, qué % de las frases `ambiguo` de val no contesta (lo deseable es 100 %).",
        "- **Latencia p50**: mediana por frase. Los modelos locales se midieron en una laptop, sin red; "
        "Gemini incluye la red y la cola de la API.",
        "- **Costo**: USD por 1.000 frases clasificadas. Los modelos locales cuestan 0 por llamada.",
        "- **Tamaño**: MB en disco del modelo (solo registrado para embeddings).",
        "",
        "## Todos los runs",
        "",
        *tabla_principal(runs),
        "",
        "`clases=6` en embeddings: entrenado también con `ambiguo` como clase; si la predice, se abstiene.",
        "",
        "## F1 por clase (mejor variante de cada candidato)",
        "",
        *tabla_por_clase(runs),
        "",
        "## Detalle de Gemini",
        "",
        *bloque_gemini(runs),
        "Cuando Gemini responde `ambiguo` o la API falla, la frase queda sin respuesta: cuenta como fallo en "
        "macro-F1 y se abstiene con cualquier τ > 0 (`evaluate.metricas`). Su confianza es la que él mismo "
        "declara en el JSON, no una probabilidad calibrada.",
        "",
    ]
    SALIDA.write_text("\n".join(lineas), encoding="utf-8")
    print(f"{len(runs)} runs → {SALIDA.relative_to(Path.cwd()) if SALIDA.is_relative_to(Path.cwd()) else SALIDA}")


if __name__ == "__main__":
    main()
