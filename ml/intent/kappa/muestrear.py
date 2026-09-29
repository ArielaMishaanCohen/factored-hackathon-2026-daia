"""Saca la muestra de 100 frases para medir el kappa entre anotadores.

Uso: .venv/bin/python -m ml.intent.kappa.muestrear

1. Lee data/frases.jsonl.
2. Reparte las 100 frases entre labels en proporción a su tamaño (mayor resto).
3. Dentro de cada label reserva una parte de las 20 frases de test_equipo
   (también en proporción) y llena el resto al azar con las demás fuentes.
4. Valida que haya al menos 30 de banking77 y 20 de test_equipo.
5. Escribe muestra_para_etiquetar.csv (id, text, label_persona2 vacía, en orden
   aleatorio) y muestra_respuestas.csv (id, label, source).
"""

import json
import random
from pathlib import Path

import pandas as pd

AQUI = Path(__file__).parent
FRASES = AQUI.parent / "data" / "frases.jsonl"
SEMILLA = 42
N = 100
MIN_B77 = 30
MIN_TEST = 20


def reparto(pesos: dict, total: int) -> dict:
    """Reparte `total` en proporción a `pesos` con el método del mayor resto."""
    suma = sum(pesos.values())
    exacto = {k: total * v / suma for k, v in pesos.items()}
    cuota = {k: int(v) for k, v in exacto.items()}
    faltan = total - sum(cuota.values())
    for k in sorted(exacto, key=lambda k: exacto[k] - cuota[k], reverse=True)[:faltan]:
        cuota[k] += 1
    return cuota


def main():
    df = pd.DataFrame([json.loads(l) for l in FRASES.open(encoding="utf-8")])
    rng = random.Random(SEMILLA)

    por_label = reparto(df["label"].value_counts().to_dict(), N)
    test_por_label = reparto(por_label, MIN_TEST)

    elegidos = []
    for label in sorted(por_label):
        grupo = df[df["label"] == label]
        test = grupo[grupo["source"] == "test_equipo"]["id"].tolist()
        resto = grupo[grupo["source"] != "test_equipo"]["id"].tolist()
        n_test = min(test_por_label[label], len(test))
        elegidos += rng.sample(sorted(test), n_test)
        elegidos += rng.sample(sorted(resto), por_label[label] - n_test)

    muestra = df.set_index("id").loc[elegidos].reset_index()
    n_b77 = (muestra["source"] == "banking77").sum()
    n_test = (muestra["source"] == "test_equipo").sum()
    assert len(muestra) == N, len(muestra)
    assert n_b77 >= MIN_B77, f"solo {n_b77} de banking77"
    assert n_test >= MIN_TEST, f"solo {n_test} de test_equipo"

    muestra = muestra.sample(frac=1, random_state=SEMILLA).reset_index(drop=True)
    para_etiquetar = muestra[["id", "text"]].assign(label_persona2="")
    para_etiquetar.to_csv(AQUI / "muestra_para_etiquetar.csv", index=False)
    muestra[["id", "label", "source"]].to_csv(AQUI / "muestra_respuestas.csv", index=False)

    print(pd.crosstab(muestra["label"], muestra["source"], margins=True))


if __name__ == "__main__":
    main()
