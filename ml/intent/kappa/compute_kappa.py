"""Kappa de Cohen entre la etiqueta del set y la de una segunda persona (Paso 10 de la guía 4.1).

Uso: .venv/bin/python -m ml.intent.kappa.compute_kappa [--llenado muestra_para_etiquetar_llenado_1.csv]

- Persona 1: la etiqueta actual de data/frases.jsonl (la que usan los modelos). Si alguna
  cambió desde que se sacó la muestra (muestra_respuestas.csv), se avisa.
- Persona 2: la columna label_persona2 del archivo llenado (se limpian espacios y mayúsculas).
- Calcula el kappa en total y por source, la matriz de confusión y la lista de desacuerdos,
  y escribe esa lista en desacuerdos.csv para revisarla juntos.
"""

import argparse
import json
from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score, confusion_matrix

AQUI = Path(__file__).parent
FRASES = AQUI.parent / "data" / "frases.jsonl"
ETIQUETAS = ["cargo_no_reconocido", "cobro_incorrecto", "tarjeta_comprometida", "estado_disputa",
             "fuera_de_alcance", "ambiguo"]
OBJETIVO = 0.8


def cargar(llenado: str) -> pd.DataFrame:
    p2 = pd.read_csv(AQUI / llenado, dtype=str)
    p2["label_persona2"] = p2["label_persona2"].fillna("").str.strip().str.lower()
    raras = sorted(set(p2["label_persona2"]) - set(ETIQUETAS))
    if raras:
        raise ValueError(f"etiquetas desconocidas en label_persona2: {raras}")

    frases = pd.DataFrame([json.loads(l) for l in FRASES.open(encoding="utf-8")]).set_index("id")
    faltan = set(p2["id"]) - set(frases.index)
    if faltan:
        raise ValueError(f"ids que no están en frases.jsonl: {sorted(faltan)}")
    df = p2.assign(label=p2["id"].map(frases["label"]), source=p2["id"].map(frases["source"]),
                   text_set=p2["id"].map(frases["text"]))
    espacios = lambda col: col.str.split().str.join(" ")  # la hoja de cálculo cambia saltos de línea por espacios
    distinto = df[espacios(df["text"]) != espacios(df["text_set"])]
    if len(distinto):
        raise ValueError(f"el texto no coincide con frases.jsonl en: {distinto['id'].tolist()}")

    resp = pd.read_csv(AQUI / "muestra_respuestas.csv").set_index("id")["label"]
    cambios = df[df["id"].map(resp) != df["label"]]
    for _, r in cambios.iterrows():
        print(f"AVISO: {r['id']} era {resp[r['id']]} al sacar la muestra; ahora es {r['label']}")
    return df.drop(columns="text_set")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--llenado", default="muestra_para_etiquetar_llenado_1.csv")
    a = ap.parse_args(argv)
    df = cargar(a.llenado)

    k = cohen_kappa_score(df["label"], df["label_persona2"], labels=ETIQUETAS)
    acuerdo = (df["label"] == df["label_persona2"]).mean()
    print(f"Frases: {len(df)} · acuerdo simple {acuerdo:.0%} · kappa {k:.3f} (objetivo > {OBJETIVO})\n")

    print(f"{'source':<12} {'n':>3} {'acuerdo':>8} {'kappa':>6}")
    for src, g in df.groupby("source"):
        ks = cohen_kappa_score(g["label"], g["label_persona2"], labels=ETIQUETAS)
        print(f"{src:<12} {len(g):>3} {(g['label'] == g['label_persona2']).mean():>8.0%} {ks:>6.3f}")

    cm = pd.DataFrame(confusion_matrix(df["label"], df["label_persona2"], labels=ETIQUETAS),
                      index=[f"set:{e}" for e in ETIQUETAS], columns=[e[:10] for e in ETIQUETAS])
    print("\nMatriz de confusión (filas = etiqueta del set, columnas = persona 2):")
    print(cm.to_string())

    des = df[df["label"] != df["label_persona2"]].sort_values(["label", "label_persona2"])
    des[["id", "source", "text", "label", "label_persona2"]].rename(
        columns={"label": "label_set"}).assign(decision="").to_csv(AQUI / "desacuerdos.csv", index=False)
    print(f"\nDesacuerdos ({len(des)}), también en ml/intent/kappa/desacuerdos.csv:")
    for _, r in des.iterrows():
        print(f"- {r['id']} [{r['source']}] set={r['label']} · persona2={r['label_persona2']}\n    {r['text']}")


if __name__ == "__main__":
    main()
