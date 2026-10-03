"""τ_intención por costo esperado: ¿el 0,81 de D4.3 es también el umbral más barato?

D4.3 eligió τ como "el de mayor cobertura con precisión ≥ 95 % en val". Aquí se le pone un costo
a cada desenlace del clasificador y se busca el τ que minimiza el costo esperado en val, con y sin
la segunda opinión de Gemini (D4.5). No cambia τ: es un análisis para justificarlo o cuestionarlo.

Unidad: minutos de agente. El ancla es el AHT de los contactos de `Queja` en el call center
(analysis/metricas_problema.json, 434,6 s ≈ 7,2 min). Los factores de COSTOS son supuestos y se
declaran como tales; por eso el script también barre los dos que más pesan (sensibilidad).

Lee solo predicciones de val ya guardadas (sin red, sin test):
    ml/intent/runs/20260930-111809_tfidf_lr_val.json      clasificador servido (D4.6), entrenado con train
    ml/intent/runs/20260929-183041_gemini_zeroshot_val.json  Gemini zero-shot (para la cascada)

Escribe ml/thresholds/figures/*.png y ml/thresholds/resultados.json.

    .venv/bin/python -m ml.thresholds.costo_umbral
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from ml.intent.elegir_modelo import AZUL, FONDO, NARANJA, TINTA, TINTA_2, estilo
from ml.intent.evaluate import AMBIGUO, CLASES, RUNS_DIR

ROOT = Path(__file__).resolve().parents[2]
AQUI = Path(__file__).resolve().parent
FIGURAS = AQUI / "figures"
RUN_CLF = RUNS_DIR / "20260930-111809_tfidf_lr_val.json"
RUN_GEMINI = RUNS_DIR / "20260929-183041_gemini_zeroshot_val.json"

TAU_ACTUAL = 0.81    # config/policy.yaml · intent.tau_intencion
TAU_GEMINI = 0.80    # config/policy.yaml · intent.tau_gemini
TAUS = np.round(np.arange(0.30, 1.0001, 0.01), 2)
CASI_OPTIMO = 0.05   # τ con costo ≤ mínimo × 1,05 cuentan como "casi óptimos"

# Costo de cada desenlace, en múltiplos del AHT de Queja. Supuestos (ver costo_umbral.md §2).
COSTOS = {
    "acierto": 0.0,
    "abstencion": 0.25,          # una aclaración más; con max_clarifications = 2, una parte llega a agente
    "leve": 0.5,                 # flujo equivocado; se nota al confirmar y el cliente cancela y reexplica
    "ambiguo_contestado": 0.5,   # el bot adivina sobre una frase sin intención clara; mismo efecto que leve
    "rechazo": 1.0,              # una disputa real recibe "no puedo ayudarte con eso": vuelve a llamar
    "grave": 2.0,                # posible fraude que no se atiende: vuelve a llamar + exposición de la tarjeta
}
FRAUDE = {"cargo_no_reconocido", "tarjeta_comprometida"}
NO_ATIENDE = {"fuera_de_alcance", "estado_disputa"}


def aht_minutos() -> float:
    d = json.loads((ROOT / "analysis/metricas_problema.json").read_text(encoding="utf-8"))
    queja = next(c for c in d["call_center_by_category"] if c["reason_category"] == "Queja")
    return queja["mean_duration_seconds"] / 60


def desenlace(label: str, pred: str) -> str:
    """Tipo de desenlace de una frase contestada."""
    if pred == label:
        return "acierto"
    if label == AMBIGUO:
        return "ambiguo_contestado"
    if label in FRAUDE and pred in NO_ATIENDE:
        return "grave"
    if pred == "fuera_de_alcance":
        return "rechazo"
    return "leve"


def cargar() -> list[dict]:
    """Une por id las predicciones del clasificador y de Gemini. Sin predicción de Gemini = se abstiene."""
    clf = json.loads(RUN_CLF.read_text(encoding="utf-8"))["predicciones"]
    gem = {p["id"]: p for p in json.loads(RUN_GEMINI.read_text(encoding="utf-8"))["predicciones"]}
    filas = []
    for p in clf:
        g = gem.get(p["id"])
        acepta_g = g is not None and g["gemini"] in CLASES and g["conf"] >= TAU_GEMINI
        filas.append({"id": p["id"], "label": p["label"], "pred": p["pred"], "conf": p["conf"],
                      "pred_gemini": g["gemini"] if acepta_g else None, "con_gemini": g is not None})
    return filas


def evaluar(filas, tau: float, cascada: bool, costos=COSTOS) -> dict:
    """Desenlaces y costo (en múltiplos de AHT) de todas las frases para un τ."""
    cuenta = dict.fromkeys(costos, 0)
    for f in filas:
        if f["conf"] >= tau:
            cuenta[desenlace(f["label"], f["pred"])] += 1
        elif cascada and f["pred_gemini"]:
            cuenta[desenlace(f["label"], f["pred_gemini"])] += 1
        else:
            cuenta["abstencion"] += 1
    costo = sum(costos[k] * v for k, v in cuenta.items())
    n = len(filas)
    return {"tau": float(tau), "costo_por_frase": costo / n, "cobertura": 1 - cuenta["abstencion"] / n, **cuenta}


def curva(filas, cascada: bool, costos=COSTOS) -> list[dict]:
    return [evaluar(filas, t, cascada, costos) for t in TAUS]


def optimo(c: list[dict]) -> dict:
    """El τ de menor costo; en empate, el más alto (el más conservador)."""
    minimo = min(p["costo_por_frase"] for p in c)
    return max((p for p in c if np.isclose(p["costo_por_frase"], minimo)), key=lambda p: p["tau"])


def banda(c: list[dict]) -> tuple[float, float]:
    minimo = min(p["costo_por_frase"] for p in c)
    ok = [p["tau"] for p in c if p["costo_por_frase"] <= minimo * (1 + CASI_OPTIMO)]
    return min(ok), max(ok)


def en_tau(c: list[dict], tau: float) -> dict:
    return min(c, key=lambda p: abs(p["tau"] - tau))


def _guardar(fig, archivo: str, wspace: float | None = None) -> Path:
    fig.tight_layout()
    if wspace is not None:
        fig.subplots_adjust(wspace=wspace)
    FIGURAS.mkdir(exist_ok=True)
    ruta = FIGURAS / archivo
    fig.savefig(ruta, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    return ruta


def figura_curva(curvas: dict, aht: float, n: int) -> Path:
    """Costo esperado por 100 conversaciones (minutos de agente) contra τ, clasificador solo y cascada."""
    fig, ax = plt.subplots(figsize=(9, 4.8), facecolor=FONDO)
    estilo(ax, y_pct=False)
    for nombre, c, color in (("Clasificador solo", curvas["solo"], AZUL),
                             ("Cascada con Gemini (τ_g = 0,80)", curvas["cascada"], NARANJA)):
        x = [p["tau"] for p in c]
        y = [p["costo_por_frase"] * aht * 100 for p in c]
        ax.plot(x, y, color=color, linewidth=2, label=nombre)
        lo, hi = banda(c)
        ax.axvspan(lo, hi, color=color, alpha=0.08, linewidth=0)
        o = optimo(c)
        ax.plot(o["tau"], o["costo_por_frase"] * aht * 100, "o", color=color, markersize=8,
                markeredgecolor=FONDO, markeredgewidth=2, zorder=5)
        ax.annotate(f"mínimo τ = {o['tau']:.2f}", (o["tau"], o["costo_por_frase"] * aht * 100), xytext=(0, -16),
                    textcoords="offset points", ha="center", va="top", fontsize=9, color=color)
    ax.axvline(TAU_ACTUAL, color=TINTA_2, linewidth=1, linestyle="--")
    ax.text(TAU_ACTUAL + 0.005, ax.get_ylim()[1] * 0.97, f"τ actual = {TAU_ACTUAL:.2f}", color=TINTA_2, fontsize=9,
            va="top")
    ax.set_xlim(TAUS[0], 1)
    ax.set_ylim(bottom=0)
    ax.set_xlabel("τ_intención (bajo τ, el clasificador se abstiene)", color=TINTA, fontsize=10)
    ax.set_ylabel("Minutos de agente por 100 conversaciones", color=TINTA, fontsize=10)
    ax.legend(frameon=False, fontsize=9, labelcolor=TINTA, loc="upper left")
    fig.suptitle(f"Costo esperado contra τ · val ({n} frases) · franja = a ≤ 5 % del mínimo", color=TINTA,
                 fontsize=12, x=0.01, ha="left")
    ax.text(0, -0.2, f"1 AHT de Queja = {aht:.1f} min. Costos por desenlace: supuestos de costo_umbral.md §2.",
            transform=ax.transAxes, fontsize=8, color=TINTA_2)
    return _guardar(fig, "costo_vs_tau_val.png")


def barrido(filas, cascada: bool, factores_grave, factores_abst) -> np.ndarray:
    """τ óptimo para cada combinación de (costo de abstención, costo de un error grave)."""
    m = np.zeros((len(factores_abst), len(factores_grave)))
    for i, a in enumerate(factores_abst):
        for j, g in enumerate(factores_grave):
            costos = {**COSTOS, "abstencion": a, "grave": g}
            m[i, j] = optimo(curva(filas, cascada, costos))["tau"]
    return m


def figura_sensibilidad(filas, aht: float) -> tuple[Path, dict]:
    """τ óptimo contra el costo de un error grave (el que crece con el monto), para tres costos de abstención."""
    factores_grave = np.array([0.5, 1, 2, 3, 5, 8, 12, 20, 30, 50])
    factores_abst = [0.1, 0.25, 0.5]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), sharey=True, facecolor=FONDO)
    tabla = {"factores_grave_aht": factores_grave.tolist(), "factores_abstencion_aht": factores_abst}
    for ax, cascada, titulo in ((axes[0], False, "Sin Gemini (fallback)"),
                                (axes[1], True, "Con Gemini bajo τ (lo desplegado)")):
        m = barrido(filas, cascada, factores_grave, factores_abst)
        tabla["tau_optimo_" + ("cascada" if cascada else "solo")] = m.tolist()
        estilo(ax, y_pct=False)
        for fila, a, color in zip(m, factores_abst, (TINTA_2, AZUL, NARANJA)):
            ax.plot(factores_grave * aht, fila, "o-", color=color, linewidth=2, markersize=5,
                    markeredgecolor=FONDO, label=f"abstenerse = {a * aht:.1f} min ({a:g} AHT)")
        ax.axhline(TAU_ACTUAL, color=TINTA_2, linewidth=1, linestyle="--")
        ax.text(factores_grave[-1] * aht, TAU_ACTUAL - 0.012, f"τ actual = {TAU_ACTUAL:.2f}", color=TINTA_2,
                fontsize=9, ha="right", va="top")
        ax.set_xscale("log")
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
        ax.set_title(titulo, color=TINTA, fontsize=11, loc="left")
        ax.set_xlabel("Costo de un error grave, min de agente (log)", color=TINTA, fontsize=10)
    axes[0].set_ylim(TAUS[0] - 0.02, 1.0)
    axes[0].set_ylabel("τ que minimiza el costo", color=TINTA, fontsize=10)
    axes[0].legend(frameon=False, fontsize=9, labelcolor=TINTA, loc="lower right")
    fig.suptitle("Sensibilidad del τ óptimo a los supuestos de costo · val", color=TINTA, fontsize=12, x=0.01,
                 ha="left")
    axes[0].text(0, -0.2, "Error grave = posible fraude enviado a fuera de alcance o a estado de disputa. Su costo "
                 "crece con el monto.", transform=axes[0].transAxes, fontsize=8, color=TINTA_2)
    return _guardar(fig, "sensibilidad_tau_val.png", wspace=0.08), tabla


def main():
    aht = aht_minutos()
    filas = cargar()
    curvas = {"solo": curva(filas, False), "cascada": curva(filas, True)}
    resultados = {"aht_queja_min": aht, "n_val": len(filas),
                  "n_sin_gemini": sum(not f["con_gemini"] for f in filas), "costos_aht": COSTOS,
                  "tau_actual": TAU_ACTUAL, "tau_gemini": TAU_GEMINI}
    for nombre, c in curvas.items():
        o, act = optimo(c), en_tau(c, TAU_ACTUAL)
        resultados[nombre] = {"optimo": o, "actual": act, "banda_5pct": banda(c),
                              "ahorro_vs_actual_min_por_100": (act["costo_por_frase"] - o["costo_por_frase"]) * aht * 100}
        print(f"{nombre:8s} τ* = {o['tau']:.2f} (banda ±5 %: {banda(c)[0]:.2f}–{banda(c)[1]:.2f}) · "
              f"costo en τ*: {o['costo_por_frase'] * aht * 100:.0f} min/100 · en τ = {TAU_ACTUAL}: "
              f"{act['costo_por_frase'] * aht * 100:.0f} min/100 · cobertura {act['cobertura']:.1%} → {o['cobertura']:.1%}")
        print("         desenlaces en τ actual:", {k: act[k] for k in COSTOS}, "\n         en τ*:",
              {k: o[k] for k in COSTOS})
    rutas = [figura_curva(curvas, aht, len(filas))]
    ruta, resultados["sensibilidad"] = figura_sensibilidad(filas, aht)
    rutas.append(ruta)
    (AQUI / "resultados.json").write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    for r in rutas:
        print(r.relative_to(ROOT))


if __name__ == "__main__":
    main()
