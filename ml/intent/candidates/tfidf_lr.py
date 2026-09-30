"""Candidato 2 (Paso 5 de la guía 4.2): TF-IDF + regresión logística.

Dos vistas del texto unidas en un solo vector:
    - palabras 1-2 (captura "no reconozco", "dos veces", "meu cartão")
    - n-gramas de caracteres 2-5 con char_wb (aguanta faltas de ortografía, ES/PT y ruido de chat)
LogisticRegression con class_weight="balanced"; C se busca en val.

    .venv/bin/python -m ml.intent.candidates.tfidf_lr          # barrido C ∈ {0.1, 1, 10}
    .venv/bin/python -m ml.intent.evaluate --candidato tfidf_lr --param C=1
"""

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline, make_union

from ml.intent.evaluate import CLASES

SEED = 42
C_GRILLA = [0.1, 1, 10]


class TfidfLR:
    costo_por_1000_usd = 0.0

    def __init__(self, C: float = 1.0):
        self.C = C
        self.pipe = make_pipeline(
            make_union(
                TfidfVectorizer(analyzer="word", ngram_range=(1, 2), lowercase=True,
                                strip_accents="unicode", sublinear_tf=True, min_df=1),
                TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), lowercase=True,
                                strip_accents="unicode", sublinear_tf=True, min_df=2),
            ),
            LogisticRegression(C=C, class_weight="balanced", max_iter=5000, random_state=SEED),
        )

    def fit(self, textos, labels):
        self.pipe.fit(textos, labels)
        return self

    def predict_proba(self, textos):
        # Reordena las columnas de sklearn (orden alfabético) al orden de CLASES.
        probs = self.pipe.predict_proba(textos)
        orden = [list(self.pipe.classes_).index(c) for c in CLASES]
        return probs[:, orden]


def crear(**params):
    return TfidfLR(**params)


def _barrido():
    from ml.intent.evaluate import INTENT_DIR, correr

    filas = []
    for C in C_GRILLA:
        res, ruta = correr("tfidf_lr", {"C": C}, "val")
        filas.append((C, res, ruta))

    print(f"{'C':>5} | {'macro-F1':>8} | {'es':>5} | {'pt':>5} | {'mix':>5} | {'τ':>4} | {'cobert.':>7} | "
          f"{'precis.':>7} | {'p50 ms':>6} | run")
    for C, res, ruta in filas:
        t, idi = res["tau"], res["por_idioma"]
        print(f"{C:>5} | {res['macro_f1']:>8.3f} | " + " | ".join(
            f"{idi[g]['macro_f1']:>5.3f}" if g in idi else "    -" for g in ("es", "pt", "mix"))
            + f" | {t['tau']:>4.2f} | {t['cobertura']:>7.1%} | {t['precision'] or 0:>7.1%} | "
              f"{res['latencia_ms_p50']:>6.2f} | {ruta.name}")

    C, mejor, ruta = max(filas, key=lambda f: f[1]["macro_f1"])
    print(f"\nMejor C = {C} (macro-F1 val {mejor['macro_f1']:.3f})")
    print("F1 por clase:", ", ".join(f"{k} {v:.3f}" for k, v in mejor["f1_por_clase"].items()))

    abrev = ["cargo_nr", "cobro_inc", "tarj_comp", "est_disp", "fuera"]
    print("\nMatriz de confusión en val (filas = real, columnas = predicho, sin ambiguo):")
    print(f"{'':>10} " + " ".join(f"{a:>9}" for a in abrev))
    for a, fila in zip(abrev, mejor["matriz_confusion"]["filas_real_columnas_pred"]):
        print(f"{a:>10} " + " ".join(f"{v:>9}" for v in fila))

    import pandas as pd
    val = pd.read_json(INTENT_DIR / "data" / "val.jsonl", lines=True).set_index("id")
    pred = pd.DataFrame(mejor["predicciones"]).set_index("id")
    err = pred[(pred["label"] != pred["pred"]) & (pred["label"] != "ambiguo")]
    err = err.sort_values("conf", ascending=False).head(15).join(val[["text", "language", "source"]])
    print(f"\n15 errores con más confianza (de {int(((pred['label'] != pred['pred']) & (pred['label'] != 'ambiguo')).sum())}):")
    for i, r in err.iterrows():
        print(f"- [{i}] conf {r['conf']:.2f} · real {r['label']} → pred {r['pred']} · {r['language']}/{r['source']}\n"
              f"    {r['text']}")

    return filas


if __name__ == "__main__":
    np.random.seed(SEED)
    _barrido()
