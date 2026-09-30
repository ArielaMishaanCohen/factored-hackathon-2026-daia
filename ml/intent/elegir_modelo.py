"""Paso 9 de la Fase 4.2: aplica criterio_seleccion.md §3 y §4 a los runs de val y dibuja la curva.

Solo lee ml/intent/runs/*_val.json (el test no se toca). Escribe
ml/intent/figures/cobertura_precision_val.png e imprime la decisión.

    .venv/bin/python -m ml.intent.elegir_modelo
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ml.intent.comparar_candidatos import NOMBRES, _params, cargar, mejores_por_familia
from ml.intent.evaluate import COBERTURA_MINIMA, PRECISION_OBJETIVO, curva_cobertura_precision, elegir_tau

FIGURAS = Path(__file__).resolve().parent / "figures"
MARGEN_F1 = 0.02  # criterio §3.2: < 2 puntos de macro-F1

AZUL, NARANJA, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
TINTA, TINTA_2, GRILLA, FONDO = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def estilo(ax, y_pct: bool = True) -> None:
    """Estilo común de las figuras de ml/intent/figures/."""
    ax.set_facecolor(FONDO)
    ax.grid(color=GRILLA, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(TINTA_2)
    ax.tick_params(colors=TINTA_2, labelsize=9)
    if y_pct:
        ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))


def nombre(r) -> str:
    return f"{NOMBRES.get(r['candidato'], r['candidato'])} ({_params(r)})"


def elegir_modelo(runs) -> tuple[dict, list[str]]:
    """§3: mejor macro-F1; si el siguiente está a < 2 puntos, el más barato y rápido."""
    fams = sorted(mejores_por_familia(runs), key=lambda r: -r["metricas"]["macro_f1"])
    primero, segundo = fams[0], fams[1]
    dif = primero["metricas"]["macro_f1"] - segundo["metricas"]["macro_f1"]
    notas = [f"1.º {nombre(primero)}: macro-F1 {primero['metricas']['macro_f1']:.4f}",
             f"2.º {nombre(segundo)}: macro-F1 {segundo['metricas']['macro_f1']:.4f}",
             f"diferencia {dif * 100:.2f} puntos"]
    if dif >= MARGEN_F1:
        return primero, notas + ["≥ 2 puntos → gana el de mejor macro-F1 (§3.1)"]
    empatados = [r for r in fams if primero["metricas"]["macro_f1"] - r["metricas"]["macro_f1"] < MARGEN_F1]
    costo_lat = lambda r: (r["metricas"]["costo_por_1000_usd"], r["metricas"]["latencia_ms_p50"])
    barato = min(costo_lat(r) for r in empatados)
    ganadores = [r for r in empatados if costo_lat(r) == barato]
    ganador = max(ganadores, key=lambda r: r["metricas"]["macro_f1"])
    notas.append("< 2 puntos → gana el más barato y rápido (§3.2) entre: "
                 + "; ".join(f"{nombre(r)} USD {r['metricas']['costo_por_1000_usd']:.2f}/1.000, "
                             f"p50 {r['metricas']['latencia_ms_p50']:.1f} ms" for r in empatados))
    return ganador, notas


def dibujar(r, curva, tau, ruta: Path) -> None:
    pts = [p for p in curva if p["precision"] is not None]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.4), facecolor=FONDO)
    for ax in (a1, a2):
        estilo(ax)

    # Izquierda: precisión vs. cobertura, un punto por τ.
    a1.plot([p["cobertura"] for p in pts], [p["precision"] for p in pts], color=AZUL, linewidth=2)
    a1.axhline(PRECISION_OBJETIVO, color=TINTA_2, linewidth=1, linestyle="--")
    a1.text(0.02, PRECISION_OBJETIVO + 0.004, "precisión objetivo 95 %", color=TINTA_2, fontsize=9, va="bottom")
    a1.plot(tau["cobertura"], tau["precision"], "o", markersize=9, color=AZUL, markeredgecolor=FONDO,
            markeredgewidth=2, zorder=5)
    a1.annotate(f"τ = {tau['tau']:.2f}\ncobertura {tau['cobertura']:.1%}\nprecisión {tau['precision']:.1%}",
                (tau["cobertura"], tau["precision"]), xytext=(18, 18), textcoords="offset points",
                fontsize=9, color=TINTA, arrowprops={"arrowstyle": "-", "color": TINTA_2, "linewidth": 0.8})
    a1.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(0.02))
    a1.set_xlim(0, 1.02)
    a1.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    a1.set_xlabel("Cobertura (frases contestadas / total)", color=TINTA, fontsize=10)
    a1.set_ylabel("Precisión (contestadas correctas)", color=TINTA, fontsize=10)
    a1.set_title("Precisión vs. cobertura", color=TINTA, fontsize=11, loc="left")

    # Derecha: las tres cantidades contra τ.
    ts = [p["tau"] for p in pts]
    series = [("precisión", [p["precision"] for p in pts], AZUL),
              ("cobertura", [p["cobertura"] for p in pts], NARANJA),
              ("ambiguo abstenidas", [p["ambiguo_abstenidas"] for p in pts], AQUA)]
    for etiqueta, ys, color in series:
        a2.plot(ts, ys, color=color, linewidth=2, label=etiqueta)
    a2.axvline(tau["tau"], color=TINTA_2, linewidth=1, linestyle="--")
    a2.text(tau["tau"] + 0.01, 0.03, f"τ = {tau['tau']:.2f}", color=TINTA_2, fontsize=9)
    a2.set_xlim(0, 1)
    a2.set_ylim(0, 1.03)
    a2.set_xlabel("τ (umbral de confianza)", color=TINTA, fontsize=10)
    a2.set_title("Según τ", color=TINTA, fontsize=11, loc="left")
    a2.legend(frameon=False, fontsize=9, loc="lower left", bbox_to_anchor=(0, 0.08), labelcolor=TINTA)

    fig.suptitle(f"{nombre(r)} · val ({r['metricas']['n']} frases, contestar un ambiguo = error)",
                 color=TINTA, fontsize=12, x=0.01, ha="left")
    fig.tight_layout()
    ruta.parent.mkdir(exist_ok=True)
    fig.savefig(ruta, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


def main():
    runs = cargar()
    ganador, notas = elegir_modelo(runs)
    print("§3 selección del modelo")
    for n in notas:
        print(f"  {n}")
    print(f"  → gana {nombre(ganador)}  [{ganador['_archivo']}]")

    # Se recalcula la curva desde las predicciones guardadas para no depender de lo que diga el run.
    preds = ganador["predicciones"]
    curva = curva_cobertura_precision([p["label"] for p in preds], [p["pred"] for p in preds],
                                      [p["conf"] for p in preds])
    tau = elegir_tau(curva)
    if abs(tau["tau"] - ganador["tau"]["tau"]) > 1e-9:
        print(f"  AVISO: el run guardó τ={ganador['tau']['tau']:.2f} y recalculado da τ={tau['tau']:.2f}")

    n_amb = sum(p["label"] == "ambiguo" for p in preds)
    print(f"\n§4 τ_intención ({tau['regla']})")
    print(f"  τ = {tau['tau']:.2f} · cobertura {tau['cobertura']:.1%} ({tau['contestadas']}/{len(preds)}) · "
          f"precisión {tau['precision']:.1%} · ambiguo abstenidas {tau['ambiguo_abstenidas']:.1%} "
          f"({round(tau['ambiguo_abstenidas'] * n_amb)}/{n_amb})")
    if "FALLBACK" in tau["regla"]:
        print(f"  DECLARAR en model card y D4.3: ningún τ llega a {PRECISION_OBJETIVO:.0%} "
              f"(se usó cobertura ≥ {COBERTURA_MINIMA:.0%})")

    ruta = FIGURAS / "cobertura_precision_val.png"
    dibujar(ganador, curva, tau, ruta)
    print(f"\nfigura: {ruta.relative_to(Path.cwd()) if ruta.is_relative_to(Path.cwd()) else ruta}")


if __name__ == "__main__":
    main()
