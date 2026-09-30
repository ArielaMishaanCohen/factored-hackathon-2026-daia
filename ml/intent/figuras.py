"""Figuras de apoyo de la Fase 4.2 (model card y slides), leídas de ml/intent/runs/*_val.json.

Escribe en ml/intent/figures/:
    candidatos_f1_latencia_val.png   calidad vs. latencia y costo, mejor variante de cada candidato
    confianza_ambiguo_val.png        confianza del ganador: frases con intención vs. ambiguo, con τ
    f1_por_idioma_val.png            macro-F1 por idioma (es / pt / mix) de cada candidato

El ganador y τ salen de elegir_modelo (criterio_seleccion.md). El test no se toca.

    .venv/bin/python -m ml.intent.figuras
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from ml.intent.comparar_candidatos import NOMBRES, cargar, mejores_por_familia
from ml.intent.elegir_modelo import (AQUA, AZUL, FIGURAS, FONDO, NARANJA, TINTA, TINTA_2, elegir_modelo, estilo,
                                     nombre)
from ml.intent.evaluate import AMBIGUO, curva_cobertura_precision, elegir_tau

GRIS = "#a3a29c"
CORTO = {"mayoritaria": "Clase mayoritaria", "reglas": "Palabras clave", "tfidf_lr": "TF-IDF + LR",
         "embeddings_lr": "Embeddings + LR", "gemini_zeroshot": "Gemini zero-shot"}


def _guardar(fig, archivo: str) -> Path:
    fig.tight_layout()
    FIGURAS.mkdir(exist_ok=True)
    ruta = FIGURAS / archivo
    fig.savefig(ruta, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    return ruta


def _variante(r) -> str:
    p = r["params"]
    if r["candidato"] == "gemini_zeroshot":
        return p["modelo"]
    return ", ".join(f"{k}={v}" for k, v in p.items() if k != "clases")


def _costo(v: float) -> str:
    return "USD 0" if v == 0 else f"USD {v:.2f}"


# Dónde va la etiqueta de cada punto: (dx, dy en puntos, ha, va). Evita que se encimen.
POS_ETIQUETA = {"tfidf_lr": (0, 14, "center", "bottom"), "gemini_zeroshot": (8, 14, "right", "bottom"),
                "embeddings_lr": (12, -6, "left", "top"), "mayoritaria": (10, 8, "left", "bottom")}


def _eje_f1(ax) -> None:
    ax.yaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter("%.1f"))
    ax.set_yticks(np.arange(0, 1.01, 0.2))


def candidatos_f1_latencia(runs, ganador) -> Path:
    fams = mejores_por_familia(runs)
    fig, ax = plt.subplots(figsize=(9, 4.8), facecolor=FONDO)
    estilo(ax, y_pct=False)
    _eje_f1(ax)
    for r in fams:
        m = r["metricas"]
        es_ganador = r is ganador
        color = AZUL if es_ganador else GRIS
        ax.plot(m["latencia_ms_p50"], m["macro_f1"], "o", markersize=10 if es_ganador else 8, color=color,
                markeredgecolor=FONDO, markeredgewidth=2, zorder=5)
        variante = _variante(r)
        texto = (f"{CORTO[r['candidato']]}" + (f" ({variante})" if variante else "")
                 + f"\nF1 {m['macro_f1']:.3f} · {_costo(m['costo_por_1000_usd'])} / 1000 frases")
        dx, dy, ha, va = POS_ETIQUETA.get(r["candidato"], (12, -4, "left", "top"))
        ax.annotate(texto, (m["latencia_ms_p50"], m["macro_f1"]), xytext=(dx, dy),
                    textcoords="offset points", ha=ha, va=va, fontsize=9,
                    color=TINTA, fontweight="bold" if es_ganador else "normal")
    ax.set_xscale("log")
    ax.set_xlim(3e-4, 2e4)
    ax.set_ylim(0, 1.12)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
        lambda v, _: f"{v:g} ms" if v < 1000 else f"{v / 1000:g} s"))
    ax.set_xlabel("Latencia p50 por frase (escala logarítmica)", color=TINTA, fontsize=10)
    ax.set_ylabel("Macro-F1 (5 clases)", color=TINTA, fontsize=10)
    ax.set_title("Calidad vs. latencia y costo", color=TINTA, fontsize=11, loc="left")
    fig.suptitle(f"Mejor variante de cada candidato · val ({ganador['metricas']['n_sin_ambiguo']} frases sin "
                 "ambiguo) · azul = elegido", color=TINTA, fontsize=12, x=0.01, ha="left")
    ax.text(0, -0.2, "Locales medidos en una laptop sin red; Gemini incluye red y cola de la API.",
            transform=ax.transAxes, fontsize=8, color=TINTA_2)
    return _guardar(fig, "candidatos_f1_latencia_val.png")


def confianza_ambiguo(ganador) -> Path:
    preds = ganador["predicciones"]
    curva = curva_cobertura_precision([p["label"] for p in preds], [p["pred"] for p in preds],
                                      [p["conf"] for p in preds])
    tau = elegir_tau(curva)["tau"]
    grupos = [("Frases con intención", [p["conf"] for p in preds if p["label"] != AMBIGUO], AZUL),
              ("Frases ambiguo", [p["conf"] for p in preds if p["label"] == AMBIGUO], NARANJA)]
    bins = np.arange(0, 1.0001, 0.05)

    fig, axes = plt.subplots(2, 1, figsize=(9, 5.2), sharex=True, facecolor=FONDO)
    for ax, (titulo, conf, color) in zip(axes, grupos):
        estilo(ax, y_pct=False)
        conf = np.asarray(conf)
        ax.hist(conf, bins=bins, color=color, edgecolor=FONDO, linewidth=2)
        ax.axvline(tau, color=TINTA_2, linewidth=1, linestyle="--")
        abajo = (conf < tau).mean()
        ax.set_title(f"{titulo} (n = {len(conf)}): {abajo:.0%} debajo de τ → pide aclaración, "
                     f"{1 - abajo:.0%} se contesta", color=TINTA, fontsize=10, loc="left")
        ax.set_ylabel("Frases", color=TINTA, fontsize=10)
        ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True, nbins=4))
    axes[0].text(tau - 0.01, axes[0].get_ylim()[1] * 0.92, f"τ = {tau:.2f}", color=TINTA_2, fontsize=9,
                 ha="right")
    axes[1].set_xlim(0, 1)
    axes[1].set_xlabel("Confianza del modelo (probabilidad de la clase elegida)", color=TINTA, fontsize=10)
    fig.suptitle(f"{nombre(ganador)} · val · confianza y abstención", color=TINTA, fontsize=12, x=0.01, ha="left")
    return _guardar(fig, "confianza_ambiguo_val.png")


def f1_por_idioma(runs, ganador) -> Path:
    fams = [r for r in mejores_por_familia(runs) if r["candidato"] != "mayoritaria"]
    idiomas = [("es", AZUL), ("pt", NARANJA), ("mix", AQUA)]
    n = ganador["metricas"]["por_idioma"]
    x = np.arange(len(fams))
    ancho = 0.26

    fig, ax = plt.subplots(figsize=(9, 4.8), facecolor=FONDO)
    estilo(ax, y_pct=False)
    _eje_f1(ax)
    ax.grid(axis="x", visible=False)
    for i, (idi, color) in enumerate(idiomas):
        vals = [r["metricas"]["por_idioma"][idi]["macro_f1"] for r in fams]
        barras = ax.bar(x + (i - 1) * ancho, vals, width=ancho - 0.03, color=color, edgecolor=FONDO, linewidth=0,
                        label=f"{idi} (n = {n[idi]['n']})")
        for b, v in zip(barras, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.012, f"{v:.2f}", ha="center",
                    fontsize=8, color=TINTA_2)
    etiquetas = [CORTO[r["candidato"]] + ("\n(elegido)" if r is ganador else "") for r in fams]
    ax.set_xticks(x, etiquetas)
    for t, r in zip(ax.get_xticklabels(), fams):
        t.set_color(TINTA)
        if r is ganador:
            t.set_fontweight("bold")
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("Macro-F1 (5 clases)", color=TINTA, fontsize=10)
    ax.set_title("Macro-F1 por idioma", color=TINTA, fontsize=11, loc="left")
    ax.legend(frameon=False, fontsize=9, loc="upper left", ncols=3, labelcolor=TINTA, bbox_to_anchor=(0, 1.0))
    fig.suptitle("Mejor variante de cada candidato · val (sin ambiguo)", color=TINTA, fontsize=12, x=0.01,
                 ha="left")
    ax.text(0, -0.2, f"mix tiene solo {n['mix']['n']} frases: una frase mueve su F1 varios puntos.",
            transform=ax.transAxes, fontsize=8, color=TINTA_2)
    return _guardar(fig, "f1_por_idioma_val.png")


def main():
    runs = cargar()
    ganador, _ = elegir_modelo(runs)
    for ruta in (candidatos_f1_latencia(runs, ganador), confianza_ambiguo(ganador), f1_por_idioma(runs, ganador)):
        print(ruta.relative_to(Path.cwd()) if ruta.is_relative_to(Path.cwd()) else ruta)


if __name__ == "__main__":
    main()
