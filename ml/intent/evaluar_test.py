"""Paso 10 de la Fase 4.2: abre el test una sola vez (criterio_seleccion.md §5).

Cada candidato se corre en test con la variante que ganó su familia en val y con su propio τ de
val (no se elige nada en test). El ganador y su τ salen de elegir_modelo, que solo lee val.
Si ya hay un run de test para un candidato con esos params, se reusa: el test no se vuelve a correr.

Escribe:
    ml/intent/runs/<fecha>_<candidato>_test.json   un run por candidato
    ml/intent/resultados_test.md                   tabla final + errores del ganador
    ml/intent/figures/matriz_confusion_test.png    matriz de confusión del ganador

    .venv/bin/python -m ml.intent.evaluar_test
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from ml.intent.comparar_candidatos import (CORTO, NOMBRES, _ms, _num, _params, _pct, cargar,
                                           mejores_por_familia)
from ml.intent.elegir_modelo import FIGURAS, FONDO, TINTA, TINTA_2, elegir_modelo
from ml.intent.evaluate import AMBIGUO, CLASES, INTENT_DIR, RUNS_DIR, correr, elegir_tau, load_split

SALIDA = INTENT_DIR / "resultados_test.md"
FIGURA = FIGURAS / "matriz_confusion_test.png"


def variantes(runs) -> list[dict]:
    """La mejor variante de val de cada familia; en embeddings, también la mejor de 6 clases (Paso 6)."""
    elegidas = mejores_por_familia(runs)
    seis = [r for r in runs if r["candidato"] == "embeddings_lr" and r["params"].get("clases") == 6]
    if seis:
        mejor6 = max(seis, key=lambda r: r["metricas"]["macro_f1"])
        i = next(i for i, r in enumerate(elegidas) if r["candidato"] == "embeddings_lr")
        if mejor6 is not elegidas[i]:
            elegidas.insert(i + 1, mejor6)
    return elegidas


def run_test_existente(candidato: str, params: dict) -> dict | None:
    for ruta in sorted(RUNS_DIR.glob(f"*_{candidato}_test*.json"), reverse=True):
        r = json.loads(ruta.read_text())
        if r["params"] == params:
            r["_archivo"] = ruta.name
            return r
    return None


def correr_test(val: dict) -> dict:
    """Corre un candidato en test con los params y el τ de su run de val."""
    c, params, tau = val["candidato"], val["params"], val["tau"]["tau"]
    previo = run_test_existente(c, params)
    if previo:
        print(f"  {c} {params}: ya hay run de test ({previo['_archivo']}), no se vuelve a correr", flush=True)
        return previo
    print(f"  {c} {params}: corriendo en test con τ={tau:.2f}", flush=True)
    if c == "embeddings_lr":
        from ml.intent.candidates.embeddings_lr import _correr
        _, ruta = _correr(params, "test", permitir_test=True, tau=tau)
    elif c == "gemini_zeroshot":
        from ml.intent.candidates.gemini_zeroshot import correr as correr_gemini
        if params["modelo"] != _modelo_env():
            raise RuntimeError(f"GEMINI_MODEL de .env no es {params['modelo']!r}, el que se evaluó en val")
        _, ruta = correr_gemini("test", prompt=params["prompt"], permitir_test=True, tau=tau)
    else:
        _, ruta = correr(c, params, "test", permitir_test=True, tau=tau)
    r = json.loads(ruta.read_text())
    r["_archivo"] = ruta.name
    return r


def _modelo_env() -> str:
    import os

    from dotenv import load_dotenv
    load_dotenv(INTENT_DIR.parent.parent / ".env")
    return os.environ.get("GEMINI_MODEL", "").strip()


# --- Tablas --------------------------------------------------------------------


def _nombre(r) -> str:
    return NOMBRES.get(r["candidato"], r["candidato"])


def tabla_final(pares, ganador) -> list[str]:
    out = ["| Candidato | Variante | macro-F1 val | **macro-F1 test** | F1 es | F1 pt | F1 mix | τ (de val) | "
           "Cobertura | Precisión | ambiguo abstenidas | Latencia p50 (ms) | Costo por 1.000 (USD) |",
           "| :-- | :-- | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: |"]
    for val, test in pares:
        m, t, idi = test["metricas"], test["tau"], test["metricas"]["por_idioma"]
        marca = " ★" if val is ganador else ""
        out.append(
            f"| {_nombre(val)}{marca} | {_params(val)} | {_num(val['metricas']['macro_f1'])} | "
            f"**{_num(m['macro_f1'])}** | "
            + " | ".join(_num(idi[g]["macro_f1"]) if g in idi else "–" for g in ("es", "pt", "mix"))
            + f" | {_num(t['tau'], 2)} | {_pct(t['cobertura'])} | {_pct(t['precision'])} | "
              f"{_pct(t['ambiguo_abstenidas'])} | {_ms(m['latencia_ms_p50'])} | {_num(m['costo_por_1000_usd'], 2)} |")
    return out


def tabla_por_clase(pares) -> list[str]:
    out = ["| Candidato | Variante | " + " | ".join(CORTO[c] for c in CLASES) + " |",
           "| :-- | :-- | " + " | ".join("--:" for _ in CLASES) + " |"]
    for val, test in pares:
        f = test["metricas"]["f1_por_clase"]
        out.append(f"| {_nombre(val)} | {_params(val)} | " + " | ".join(_num(f[c]) for c in CLASES) + " |")
    return out


def _texto(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


def errores(test_run, df, tau) -> tuple[list[str], list[str], dict]:
    """Errores del ganador: (a) frases con intención mal clasificadas (argmax), (b) ambiguo contestadas con τ."""
    info = df.set_index("id")
    preds = test_run["predicciones"]
    mal = [p for p in preds if p["label"] != AMBIGUO and p["pred"] != p["label"]]
    amb = [p for p in preds if p["label"] == AMBIGUO and p["conf"] >= tau]
    mal.sort(key=lambda p: (-(p["conf"] >= tau), -p["conf"]))
    amb.sort(key=lambda p: -p["conf"])

    a = ["| id | idioma | frase | real | predicho | confianza | ¿contesta con τ? |",
         "| :-- | :-- | :-- | :-- | :-- | --: | :-- |"]
    for p in mal:
        f = info.loc[p["id"]]
        a.append(f"| {p['id']} | {f['language']} | {_texto(f['text'])} | {CORTO[p['label']]} | "
                 f"{CORTO.get(p['pred'], p['pred'])} | {_num(p['conf'], 2)} | "
                 f"{'**sí (error visible)**' if p['conf'] >= tau else 'no (pide aclaración)'} |")
    b = ["| id | idioma | frase | predicho | confianza |", "| :-- | :-- | :-- | :-- | --: |"]
    for p in amb:
        f = info.loc[p["id"]]
        b.append(f"| {p['id']} | {f['language']} | {_texto(f['text'])} | {CORTO.get(p['pred'], p['pred'])} | "
                 f"{_num(p['conf'], 2)} |")
    resumen = {"mal": len(mal), "mal_contestadas": sum(p["conf"] >= tau for p in mal), "amb_contestadas": len(amb),
               "n_amb": sum(p["label"] == AMBIGUO for p in preds)}
    return a, b, resumen


# --- Figura --------------------------------------------------------------------


def matriz_confusion(test_run, tau, titulo: str, ruta: Path) -> Path:
    """Filas: clase real (+ ambiguo, aparte). Columnas: predicción del argmax. Las cuentas son sin abstención."""
    filas = CLASES + [AMBIGUO]
    M = np.zeros((len(filas), len(CLASES)), dtype=int)
    for p in test_run["predicciones"]:
        if p["pred"] in CLASES:
            M[filas.index(p["label"]), CLASES.index(p["pred"])] += 1
    norm = M / np.maximum(M.sum(axis=1, keepdims=True), 1)

    fig, ax = plt.subplots(figsize=(7.4, 5.8), facecolor=FONDO)
    ax.set_facecolor(FONDO)
    ax.imshow(norm, cmap="Blues", vmin=0, vmax=1, aspect="auto")
    for i in range(len(filas)):
        for j in range(len(CLASES)):
            if M[i, j]:
                ax.text(j, i, M[i, j], ha="center", va="center", fontsize=10,
                        color="white" if norm[i, j] > 0.55 else TINTA)
    ax.axhline(len(CLASES) - 0.5, color=TINTA_2, linewidth=1.5)
    ax.set_xticks(range(len(CLASES)), [CORTO[c] for c in CLASES], fontsize=9, color=TINTA_2)
    ax.set_yticks(range(len(filas)), [CORTO.get(c, c) + f" (n={M[i].sum()})" for i, c in enumerate(filas)],
                  fontsize=9, color=TINTA_2)
    ax.set_xlabel("Predicción (argmax, sin abstención)", color=TINTA, fontsize=10)
    ax.set_ylabel("Clase real", color=TINTA, fontsize=10)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    ax.set_title(titulo, color=TINTA, fontsize=11, loc="left")
    fig.text(0.01, 0.01, f"Color = % de la fila. La fila ambiguo no entra al macro-F1; con τ = {tau:.2f} "
             "la mayoría se abstiene (ver resultados_test.md).", color=TINTA_2, fontsize=8)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    FIGURAS.mkdir(exist_ok=True)
    fig.savefig(ruta, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    return ruta


# --- Main ------------------------------------------------------------------------


def main():
    runs = cargar()
    ganador, _ = elegir_modelo(runs)
    tau_g = elegir_tau(ganador["metricas"]["curva_cobertura_precision"])["tau"]
    if abs(tau_g - ganador["tau"]["tau"]) > 1e-9:
        raise RuntimeError(f"τ del ganador no coincide: run {ganador['tau']['tau']} vs recalculado {tau_g}")
    print(f"Ganador (de val): {_nombre(ganador)} ({_params(ganador)}) · τ = {tau_g:.2f}")

    pares = [(val, correr_test(val)) for val in variantes(runs)]
    test_g = next(t for v, t in pares if v is ganador)
    df = load_split("test", permitir_test=True)

    titulo = f"{_nombre(ganador)} ({_params(ganador)}) · test ({len(df)} frases)"
    fig = matriz_confusion(test_g, tau_g, titulo, FIGURA)
    err_a, err_b, res = errores(test_g, df, tau_g)
    mv, mt, tt = ganador["metricas"], test_g["metricas"], test_g["tau"]
    n_amb, idi = res["n_amb"], mt["por_idioma"]
    idiomas = df["language"].value_counts()

    lineas = [
        "# Resultados en test · clasificador de intención (Fase 4.2, Paso 10)",
        "",
        "Generado con `.venv/bin/python -m ml.intent.evaluar_test`. El test se abrió **una sola vez**, con el "
        "modelo y τ ya fijados en val (`criterio_seleccion.md` §5). Nada se cambió después de verlo.",
        "",
        f"- **Test:** {len(df)} frases escritas por el equipo (`test_equipo`), {n_amb} `ambiguo` · "
        + " · ".join(f"{g} {idiomas.get(g, 0)}" for g in ("es", "pt", "mix")) + ". Otra fuente que train/val "
        "(Banking77 traducido + suplemento): es el sesgo que anticipa `data_report.md`.",
        "- **Cada candidato** usa la variante que ganó su familia en val y **su propio τ de val**. "
        "Embeddings se reporta también en su mejor variante de 6 clases.",
        f"- **Ganador (elegido en val):** {_nombre(ganador)} ({_params(ganador)}), τ_intención = {tau_g:.2f}. ★ en la tabla.",
        "- Macro-F1 y F1 por idioma/clase: sin `ambiguo` y sin abstención. Cobertura y precisión: todas las "
        "frases, con τ; contestar un `ambiguo` es error.",
        "",
        "## Tabla final",
        "",
        *tabla_final(pares, ganador),
        "",
        "Latencia: mediana por frase; los locales en laptop sin red, Gemini solo el tiempo de la API. "
        "Costo de Gemini con precio de capa pagada (ver `comparacion_candidatos.md`).",
        "",
        "## F1 por clase en test",
        "",
        *tabla_por_clase(pares),
        "",
        "## Ganador: val vs. test",
        "",
        "| | macro-F1 | F1 es | F1 pt | F1 mix | Cobertura | Precisión | ambiguo abstenidas |",
        "| :-- | --: | --: | --: | --: | --: | --: | --: |",
        f"| val | {_num(mv['macro_f1'])} | "
        + " | ".join(_num(mv["por_idioma"][g]["macro_f1"]) for g in ("es", "pt", "mix"))
        + f" | {_pct(ganador['tau']['cobertura'])} | {_pct(ganador['tau']['precision'])} | "
          f"{_pct(ganador['tau']['ambiguo_abstenidas'])} |",
        f"| test | {_num(mt['macro_f1'])} | "
        + " | ".join(_num(idi[g]["macro_f1"]) for g in ("es", "pt", "mix"))
        + f" | {_pct(tt['cobertura'])} | {_pct(tt['precision'])} | {_pct(tt['ambiguo_abstenidas'])} |",
        "",
        f"Con τ = {tau_g:.2f} en test contesta {tt['contestadas']} de {mt['n']} frases; "
        f"de las {n_amb} `ambiguo` contesta {res['amb_contestadas']}.",
        "",
        f"![Matriz de confusión del ganador en test](figures/{fig.name})",
        "",
        "## Errores del ganador en test",
        "",
        f"### Frases con intención mal clasificadas ({res['mal']}, de las cuales {res['mal_contestadas']} "
        f"se contestarían con τ = {tau_g:.2f})",
        "",
        "Primero las que el bot contestaría mal (confianza ≥ τ); el resto terminaría en una pregunta de aclaración.",
        "",
        *err_a,
        "",
        f"### Frases `ambiguo` que el modelo contesta con τ = {tau_g:.2f} ({res['amb_contestadas']} de {n_amb})",
        "",
        *(err_b if res["amb_contestadas"] else ["Ninguna."]),
        "",
        "## Runs",
        "",
        *[f"- {_nombre(v)} ({_params(v)}): val `{v['_archivo']}` · test `{t['_archivo']}`" for v, t in pares],
        "",
    ]
    SALIDA.write_text("\n".join(lineas), encoding="utf-8")

    print(f"\nmacro-F1 test del ganador {mt['macro_f1']:.3f} · "
          + " · ".join(f"{g} {idi[g]['macro_f1']:.3f}" for g in ("es", "pt", "mix")))
    print(f"τ={tau_g:.2f}: cobertura {tt['cobertura']:.1%} · precisión {tt['precision']:.1%} · "
          f"ambiguo abstenidas {tt['ambiguo_abstenidas']:.1%}")
    print(f"escrito: {SALIDA.relative_to(Path.cwd())} · {fig.relative_to(Path.cwd())}")


if __name__ == "__main__":
    main()
