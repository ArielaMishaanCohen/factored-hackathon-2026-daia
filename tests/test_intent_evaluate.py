"""Tests de ml/intent/evaluate.py (Fase 4.2, Paso 3) con un ejemplo hecho a mano.

Seis frases; las cuentas de cada τ están escritas al lado para revisarlas sin código:

    #  real                  pred                  conf
    0  cargo_no_reconocido   cargo_no_reconocido   0.9   bien
    1  cargo_no_reconocido   cobro_incorrecto      0.8   mal
    2  cobro_incorrecto      cobro_incorrecto      0.7   bien
    3  cobro_incorrecto      cobro_incorrecto      0.4   bien
    4  ambiguo               cargo_no_reconocido   0.6   contestar = error
    5  ambiguo               estado_disputa        0.3   contestar = error
"""
import numpy as np
import pandas as pd
import pytest

from ml.intent.evaluate import (CLASES, SplitBajoLlave, curva_cobertura_precision, elegir_tau, evaluar,
                                load_split, metricas)

LABELS = ["cargo_no_reconocido", "cargo_no_reconocido", "cobro_incorrecto", "cobro_incorrecto", "ambiguo", "ambiguo"]
PREDS = ["cargo_no_reconocido", "cobro_incorrecto", "cobro_incorrecto", "cobro_incorrecto", "cargo_no_reconocido", "estado_disputa"]
CONF = [0.9, 0.8, 0.7, 0.4, 0.6, 0.3]
TAUS = [0.0, 0.5, 0.75, 0.85, 0.95]


def curva():
    return {p["tau"]: p for p in curva_cobertura_precision(LABELS, PREDS, CONF, taus=TAUS)}


def test_cobertura_y_precision_a_mano():
    c = curva()
    # τ=0: contesta todo; aciertos 0, 2, 3 → 3/6.
    assert c[0.0]["cobertura"] == 1.0 and c[0.0]["precision"] == pytest.approx(3 / 6)
    # τ=0.5: contesta 0, 1, 2, 4 (el ambiguo 4 cuenta como error) → 2/4.
    assert c[0.5]["cobertura"] == pytest.approx(4 / 6) and c[0.5]["precision"] == pytest.approx(0.5)
    assert c[0.5]["ambiguo_abstenidas"] == pytest.approx(0.5)
    # τ=0.75: contesta 0, 1 → 1/2; ya se abstiene en los dos ambiguo.
    assert c[0.75]["precision"] == pytest.approx(0.5) and c[0.75]["ambiguo_abstenidas"] == 1.0
    # τ=0.85: solo 0 → precisión 100 %.
    assert c[0.85]["cobertura"] == pytest.approx(1 / 6) and c[0.85]["precision"] == 1.0
    # τ=0.95: no contesta nada → precisión indefinida.
    assert c[0.95]["contestadas"] == 0 and c[0.95]["precision"] is None


def test_elegir_tau_precision_95():
    t = elegir_tau(list(curva().values()))
    assert t["tau"] == 0.85 and not t["regla"].startswith("FALLBACK")


def test_elegir_tau_fallback_sin_95():
    c = [
        {"tau": 0.3, "cobertura": 0.9, "precision": 0.80},
        {"tau": 0.5, "cobertura": 0.6, "precision": 0.90},  # mejor precisión con cobertura ≥ 50 %
        {"tau": 0.7, "cobertura": 0.4, "precision": 0.93},  # más precisa, pero cobertura < 50 %
        {"tau": 0.9, "cobertura": 0.0, "precision": None},
    ]
    t = elegir_tau(c)
    assert t["tau"] == 0.5 and t["regla"].startswith("FALLBACK")


def test_macro_f1_ignora_ambiguo():
    df = pd.DataFrame({"label": LABELS, "language": ["es", "pt", "es", "pt", "es", "mix"], "source": ["x"] * 6})
    probs = np.zeros((6, 5))
    for i, (p, c) in enumerate(zip(PREDS, CONF)):
        probs[i, CLASES.index(p)] = c
    m = metricas(df, probs)
    assert m["n_sin_ambiguo"] == 4
    # cargo: P=1, R=1/2 → 2/3; cobro: P=2/3, R=1 → 4/5; el resto 0 (5 clases).
    assert m["f1_por_clase"]["cargo_no_reconocido"] == pytest.approx(2 / 3)
    assert m["f1_por_clase"]["cobro_incorrecto"] == pytest.approx(4 / 5)
    assert m["macro_f1"] == pytest.approx((2 / 3 + 4 / 5) / 5)
    assert "mix" not in m["por_idioma"]  # la única frase mix es ambiguo


def test_fila_en_cero_es_sin_respuesta():
    # Frase 1 (cargo) sin respuesta: ya no acierta nada en cargo → F1 0; no suma FP a ninguna clase.
    df = pd.DataFrame({"label": LABELS, "language": ["es"] * 6, "source": ["x"] * 6})
    probs = np.zeros((6, 5))
    for i, (p, c) in enumerate(zip(PREDS, CONF)):
        probs[i, CLASES.index(p)] = c
    probs[0] = 0
    m = metricas(df, probs)
    assert m["n_sin_respuesta"] == 1
    assert m["f1_por_clase"]["cargo_no_reconocido"] == 0.0
    assert m["f1_por_clase"]["cobro_incorrecto"] == pytest.approx(4 / 5)
    c = {p["tau"]: p for p in m["curva_cobertura_precision"]}
    assert c[0.0]["contestadas"] == 6 and c[0.0]["precision"] == pytest.approx(2 / 6)
    assert c[0.01]["contestadas"] == 5


def test_test_bajo_llave():
    with pytest.raises(SplitBajoLlave):
        load_split("test")
    with pytest.raises(SplitBajoLlave):
        evaluar(object(), "test")
