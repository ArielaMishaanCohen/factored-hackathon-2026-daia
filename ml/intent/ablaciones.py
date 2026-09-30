"""Paso 11 de la Fase 4.2: ablaciones de fuentes y de ruido con el ganador fijo.

El ganador, sus params y τ salen de elegir_modelo (solo val). Lo único que cambia es el train:
    fuentes: (a) solo banking77 · (b) solo suplemento · (c) ambos
    ruido:   (c) con ruido · (c) sin ruido (texto de data/sin_ruido.csv)
Val y test son siempre los mismos (val con su ruido; test es el del equipo). No se elige nada con
estos números: el modelo y τ ya están fijados; el test solo se mira para describir.

Los runs van a ml/intent/runs/ablaciones/ para no pisar los runs de selección (cargar() indexa
por candidato + params, y aquí los params son los del ganador).

Escribe:
    ml/intent/runs/ablaciones/<fecha>_<candidato>_<split>.json
    ml/intent/ablaciones.md

    .venv/bin/python -m ml.intent.ablaciones
"""

from ml.intent.comparar_candidatos import _num, _params, _pct, cargar
from ml.intent.elegir_modelo import elegir_modelo
from ml.intent.evaluate import INTENT_DIR, RUNS_DIR, correr, load_split

CARPETA = RUNS_DIR / "ablaciones"
SALIDA = INTENT_DIR / "ablaciones.md"
IDIOMAS = ("es", "pt", "mix")

# (clave, nombre, fuentes, sin_ruido)
CONFIGS = [
    ("a", "(a) solo Banking77", ["banking77"], False),
    ("b", "(b) solo suplemento", ["suplemento"], False),
    ("c", "(c) ambos, con ruido", None, False),
    ("c_sin", "(c) ambos, sin ruido", None, True),
]


def fila(nombre: str, train_n: int, res: dict) -> str:
    idi, t = res["por_idioma"], res["tau"]
    return (f"| {nombre} | {train_n} | **{_num(res['macro_f1'])}** | "
            + " | ".join(_num(idi[g]["macro_f1"]) if g in idi else "–" for g in IDIOMAS)
            + f" | {_pct(t['cobertura'])} | {_pct(t['precision'])} |")


def tabla(filas: list[str]) -> list[str]:
    return ["| Train | n train | **macro-F1** | F1 es | F1 pt | F1 mix | Cobertura (τ) | Precisión (τ) |",
            "| :-- | --: | --: | --: | --: | --: | --: | --: |", *filas]


def main():
    ganador, _ = elegir_modelo(cargar())
    cand, params, tau = ganador["candidato"], ganador["params"], ganador["tau"]["tau"]
    print(f"Ganador: {cand} {params} · τ = {tau:.2f}")

    res = {}
    for clave, nombre, fuentes, sin_ruido in CONFIGS:
        for split in ("val", "test"):
            r, ruta = correr(cand, params, split, fuentes=fuentes, sin_ruido=sin_ruido,
                             permitir_test=split == "test", tau=tau, carpeta=CARPETA)
            n = len(load_split("train", fuentes=fuentes).query("label != 'ambiguo'"))
            res[clave, split] = (nombre, n, r)
            print(f"{nombre:<24} {split:<4} macro-F1 {r['macro_f1']:.3f} · "
                  + " · ".join(f"{g} {v['macro_f1']:.3f}" for g, v in r["por_idioma"].items())
                  + f" · {ruta.relative_to(INTENT_DIR)}")

    # (c) con ruido es exactamente el ganador: debe reproducir su run de val.
    if abs(res["c", "val"][2]["macro_f1"] - ganador["metricas"]["macro_f1"]) > 1e-9:
        raise RuntimeError("(c) con ruido no reproduce el macro-F1 de val del ganador")

    bloque = lambda claves, split: tabla([fila(*res[k, split]) for k in claves])
    lineas = [
        "# Ablaciones · clasificador de intención (Fase 4.2, Paso 11)",
        "",
        "Generado con `.venv/bin/python -m ml.intent.ablaciones`. Runs en `ml/intent/runs/ablaciones/`.",
        "",
        f"- **Modelo fijo:** el ganador de val, {cand} ({_params(ganador)}), τ = {tau:.2f}. Solo cambia el train.",
        "- **Val y test no cambian** entre filas: val trae Banking77 + suplemento con su ruido; test son las "
        "200 frases del equipo. Nada de esto se usa para elegir: el modelo y τ ya estaban fijados.",
        "- Macro-F1 y F1 por idioma: sin `ambiguo` y sin abstención. Cobertura y precisión: todas las frases, "
        "con el τ del ganador.",
        "- Banking77 no tiene frases `mix` ni de `estado_disputa`: (a) nunca vio mezcla y no puede predecir "
        "esa clase (su F1 es 0 y le pone un techo de 0,8 al macro-F1).",
        "",
        "## Fuentes",
        "",
        "### Val",
        "",
        *bloque(("a", "b", "c"), "val"),
        "",
        "### Test",
        "",
        *bloque(("a", "b", "c"), "test"),
        "",
        "## Ruido",
        "",
        "### Val",
        "",
        *bloque(("c", "c_sin"), "val"),
        "",
        "### Test",
        "",
        *bloque(("c", "c_sin"), "test"),
        "",
    ]
    SALIDA.write_text("\n".join(lineas))
    print(f"\nEscrito {SALIDA.relative_to(INTENT_DIR.parent.parent)}")


if __name__ == "__main__":
    main()
