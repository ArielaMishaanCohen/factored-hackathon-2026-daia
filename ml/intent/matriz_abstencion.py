"""Matriz de confusión con abstención (slide de ML): clasificador solo vs. cascada con Gemini (D4.5).

A diferencia de figures/matriz_confusion_test.png (argmax, sin τ), aquí se aplica τ: la última
columna es "pide aclaración". Color semántico de la app y las slides: verde = acierto,
ámbar = se abstiene, rojo = error; la intensidad es el % de la fila.

Lee predicciones de test ya guardadas (no corre el modelo ni abre el test otra vez):
    runs/20260930-111820_tfidf_lr_test.json        clasificador servido (D4.6), τ fijado en val
    runs/20260929-192926_gemini_zeroshot_test.json  Gemini zero-shot

Escribe figures/matriz_abstencion_test.png.

    .venv/bin/python -m ml.intent.matriz_abstencion
"""

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import to_rgb

from ml.intent.comparar_candidatos import CORTO
from ml.intent.elegir_modelo import FIGURAS, FONDO, TINTA, TINTA_2
from ml.intent.evaluate import AMBIGUO, CLASES, RUNS_DIR

RUN_CLF = RUNS_DIR / "20260930-111820_tfidf_lr_test.json"
RUN_GEMINI = RUNS_DIR / "20260929-192926_gemini_zeroshot_test.json"
TAU, TAU_GEMINI = 0.81, 0.80  # config/policy.yaml
ABSTIENE = "aclara"

# Semántica común app + slides.
VERDE, AMBAR, ROJO = "#1e8e5a", "#d99100", "#c5372c"  # --ok, --warn, --bad de frontend/src/styles.css


def predicciones() -> tuple[list[dict], list[str], list[str]]:
    clf = json.loads(RUN_CLF.read_text(encoding="utf-8"))["predicciones"]
    gem = {p["id"]: p for p in json.loads(RUN_GEMINI.read_text(encoding="utf-8"))["predicciones"]}
    solo, cascada = [], []
    for p in clf:
        if p["conf"] >= TAU:
            solo.append(p["pred"])
            cascada.append(p["pred"])
            continue
        solo.append(ABSTIENE)
        g = gem.get(p["id"])
        cascada.append(g["gemini"] if g and g["gemini"] in CLASES and g["conf"] >= TAU_GEMINI else ABSTIENE)
    return clf, solo, cascada


def matriz(labels, preds) -> np.ndarray:
    filas, cols = CLASES + [AMBIGUO], CLASES + [ABSTIENE]
    M = np.zeros((len(filas), len(cols)), dtype=int)
    for y, p in zip(labels, preds):
        M[filas.index(y), cols.index(p)] += 1
    return M


def resumen(labels, preds) -> dict:
    labels, preds = np.asarray(labels), np.asarray(preds)
    contesta = preds != ABSTIENE
    amb = labels == AMBIGUO
    return {"cobertura": contesta.mean(), "precision": (preds[contesta] == labels[contesta]).mean(),
            "ambiguo_abstenidas": (~contesta[amb]).mean(), "con_intencion_abstenidas": (~contesta[~amb]).mean()}


def _color(i: int, j: int, frac: float) -> tuple:
    if j == len(CLASES):
        base = AMBAR
    elif i < len(CLASES) and i == j:
        base = VERDE
    else:
        base = ROJO
    a = 0.08 + 0.85 * frac if frac > 0 else 0.0
    return tuple(a * c + (1 - a) * f for c, f in zip(to_rgb(base), to_rgb(FONDO)))


def dibujar(ax, M: np.ndarray, titulo: str) -> None:
    ax.set_facecolor(FONDO)
    fr = M / M.sum(axis=1, keepdims=True)
    img = np.array([[_color(i, j, fr[i, j]) for j in range(M.shape[1])] for i in range(M.shape[0])])
    ax.imshow(img, aspect="auto")
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            if M[i, j]:
                ax.text(j, i, str(M[i, j]), ha="center", va="center", fontsize=10,
                        color="white" if fr[i, j] > 0.55 else TINTA)
    filas = CLASES + [AMBIGUO]
    ax.set_xticks(range(M.shape[1]), [CORTO[c] for c in CLASES] + ["pide\naclaración"], fontsize=9, color=TINTA_2)
    ax.set_yticks(range(M.shape[0]), [f"{CORTO.get(c, c)} (n={M[i].sum()})" for i, c in enumerate(filas)],
                  fontsize=9, color=TINTA_2)
    ax.axhline(len(CLASES) - 0.5, color=TINTA_2, linewidth=1.5)
    ax.axvline(len(CLASES) - 0.5, color=TINTA_2, linewidth=1.5)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    ax.set_title(titulo, color=TINTA, fontsize=10, loc="left")


def main():
    clf, solo, cascada = predicciones()
    labels = [p["label"] for p in clf]
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.6), sharey=True, facecolor=FONDO)
    for ax, preds, nombre in ((axes[0], solo, f"Clasificador solo (τ = {TAU:.2f})"),
                              (axes[1], cascada, f"Con Gemini bajo τ (τ_g = {TAU_GEMINI:.2f}) · lo desplegado")):
        r = resumen(labels, preds)
        dibujar(ax, matriz(labels, preds),
                f"{nombre}\ncontesta {r['cobertura']:.0%} con precisión {r['precision']:.0%} · "
                f"se abstiene en {r['ambiguo_abstenidas']:.0%} de las ambiguo")
        print(nombre, {k: round(float(v), 3) for k, v in r.items()})
    axes[0].set_ylabel("Clase real", color=TINTA, fontsize=10)
    for ax in axes:
        ax.set_xlabel("Decisión del NLU", color=TINTA, fontsize=10)
    fig.suptitle(f"Intención · test ({len(labels)} frases, otra fuente que train) · "
                 "verde = acierto · ámbar = pide aclaración · rojo = error",
                 color=TINTA, fontsize=12, x=0.01, ha="left")
    fig.text(0.01, 0.01, "Intensidad = % de la fila. La fila ambiguo no tiene intención: lo correcto es pedir "
             "aclaración. El τ_g de la cascada se eligió con val y test ya vistos (D4.5): test no es una medición "
             "limpia de la cascada.", fontsize=8, color=TINTA_2)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    ruta = FIGURAS / "matriz_abstencion_test.png"
    fig.savefig(ruta, dpi=150, facecolor=fig.get_facecolor())
    print(ruta)


if __name__ == "__main__":
    main()
