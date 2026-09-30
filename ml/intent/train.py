"""Paso 12 de la Fase 4.2: entrena el modelo elegido con train+val y guarda el artefacto de servicio.

Ganador (criterio_seleccion.md §3, elegir_modelo.py): TF-IDF + regresión logística, C=10.
Los parámetros están fijos aquí; no se busca nada. El test no se toca.

    make train        (= .venv/bin/python -m ml.intent.train)

Escribe en ml/intent/model/:
    intent_model.joblib  {"pipeline": Pipeline de sklearn, "clases": CLASES, "model_version": ...}
    model_meta.json      lo mismo sin el pipeline, legible (versión, datos, tamaños)

Se guarda solo el Pipeline de sklearn (no la clase TfidfLR) para que el backend lo cargue
sin importar ml/: la imagen de servicio solo tiene backend/, config/ y ml/intent/model/.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn

from ml.intent.candidates.tfidf_lr import SEED, TfidfLR
from ml.intent.evaluate import AMBIGUO, CLASES, DATA_DIR, INTENT_DIR, git_commit, load_split, md5_frases

MODEL_DIR = INTENT_DIR / "model"
ARTEFACTO = MODEL_DIR / "intent_model.joblib"
META = MODEL_DIR / "model_meta.json"

CANDIDATO = "tfidf_lr"
PARAMS = {"C": 10}  # ganador en val (runs/20260929-170918_tfidf_lr_val.json)
TAU_VAL = 0.81      # τ_intención elegido en val con train solo; va en config/policy.yaml


def md5_datos() -> str:
    """md5 de los archivos con que se entrena (train.jsonl + val.jsonl, en ese orden)."""
    h = hashlib.md5()
    for nombre in ("train", "val"):
        h.update((DATA_DIR / f"{nombre}.jsonl").read_bytes())
    return h.hexdigest()


def entrenar() -> dict:
    np.random.seed(SEED)
    df = pd.concat([load_split("train"), load_split("val")], ignore_index=True)
    df = df[df["label"] != AMBIGUO]  # variante principal: ambiguo no es una clase (criterio §1)

    modelo = TfidfLR(**PARAMS).fit(df["text"].tolist(), df["label"].tolist())
    assert sorted(modelo.pipe.classes_) == sorted(CLASES), modelo.pipe.classes_

    md5 = md5_datos()
    fecha = datetime.now()
    version = f"{CANDIDATO}-C{PARAMS['C']}-{fecha:%Y%m%d}-{md5[:8]}"
    meta = {
        "model_version": version,
        "candidato": CANDIDATO,
        "params": PARAMS,
        "clases": CLASES,
        "tau_val": TAU_VAL,
        "entrenado": fecha.isoformat(timespec="seconds"),
        "datos": {
            "splits": ["train", "val"],
            "n_frases": len(df),
            "por_clase": df["label"].value_counts().sort_index().to_dict(),
            "por_idioma": df["language"].value_counts().sort_index().to_dict(),
            "md5_train_val": md5,
            "md5_frases": md5_frases(),
        },
        "sklearn": sklearn.__version__,
        "git_commit": git_commit(),
    }

    MODEL_DIR.mkdir(exist_ok=True)
    joblib.dump({"pipeline": modelo.pipe, "clases": CLASES, "model_version": version}, ARTEFACTO, compress=3)
    meta["tamano_bytes"] = ARTEFACTO.stat().st_size
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return meta


if __name__ == "__main__":
    m = entrenar()
    print(f"model_version: {m['model_version']}")
    print(f"frases: {m['datos']['n_frases']} (sin ambiguo) · {m['datos']['por_idioma']}")
    print(f"artefacto: {ARTEFACTO.relative_to(INTENT_DIR.parents[1])} · {m['tamano_bytes'] / 1024:.0f} KB")
