"""Paso 3 de la Fase 4.2: código común para cargar datos, medir candidatos y registrar corridas.

Todos los candidatos se miden con estas mismas funciones (criterio_seleccion.md).

Interfaz de un candidato (ml/intent/candidates/<nombre>.py expone crear(**params)):
    fit(textos, labels)     -> entrena con listas de str (labels sin "ambiguo").
    predict_proba(textos)   -> np.ndarray (n, 5) con las columnas en el orden de CLASES.
    costo_por_1000_usd      -> atributo opcional (0 si no existe).
Las filas de predict_proba no tienen que sumar 1: un candidato que puede decir
"ambiguo" (6 clases, Gemini) deja esa masa fuera y su confianza queda baja.

Uso por línea de comandos:
    .venv/bin/python -m ml.intent.evaluate --candidato tfidf_lr --split val --param C=1
    .venv/bin/python -m ml.intent.evaluate --candidato tfidf_lr --split test --test --tau 0.62

El test está bajo llave: load_split("test") y evaluar(..., "test") fallan si no se
pasa permitir_test=True (--test en la CLI). En test τ no se elige: se usa el de val.
"""

import argparse
import hashlib
import importlib
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, f1_score

INTENT_DIR = Path(__file__).resolve().parent
DATA_DIR = INTENT_DIR / "data"
RUNS_DIR = INTENT_DIR / "runs"

CLASES = ["cargo_no_reconocido", "cobro_incorrecto", "tarjeta_comprometida", "estado_disputa", "fuera_de_alcance"]
AMBIGUO = "ambiguo"
SPLITS = {"train", "val", "test"}

# criterio_seleccion.md §4
PRECISION_OBJETIVO = 0.95
COBERTURA_MINIMA = 0.50
TAUS = np.round(np.arange(0, 1.0001, 0.01), 2)


class SplitBajoLlave(RuntimeError):
    pass


def _revisar_llave(nombre: str, permitir_test: bool) -> None:
    if nombre == "test" and not permitir_test:
        raise SplitBajoLlave(
            "El split 'test' está bajo llave: se evalúa una sola vez, al final (Paso 10 de la guía 4.2). "
            "Usa --test (o permitir_test=True) solo cuando el modelo y τ ya estén fijados en val.")


# --- Datos -------------------------------------------------------------------


def load_split(nombre: str, fuentes=None, sin_ruido: bool = False, permitir_test: bool = False) -> pd.DataFrame:
    """Lee ml/intent/data/<nombre>.jsonl.

    fuentes: lista de valores de `source` para quedarse (None = todas).
    sin_ruido: reemplaza `text` por `text_limpio` de data/sin_ruido.csv (solo train/val).
    """
    if nombre not in SPLITS:
        raise ValueError(f"split desconocido: {nombre!r} (usa uno de {sorted(SPLITS)})")
    _revisar_llave(nombre, permitir_test)

    df = pd.read_json(DATA_DIR / f"{nombre}.jsonl", lines=True)
    if fuentes is not None:
        fuentes = [fuentes] if isinstance(fuentes, str) else list(fuentes)
        desconocidas = set(fuentes) - set(pd.read_json(DATA_DIR / "frases.jsonl", lines=True)["source"])
        if desconocidas:
            raise ValueError(f"fuentes desconocidas: {sorted(desconocidas)}")
        df = df[df["source"].isin(fuentes)]
    if sin_ruido:
        if nombre == "test":
            raise ValueError("sin_ruido.csv no tiene test: el test nunca lleva ruido agregado.")
        limpio = pd.read_csv(DATA_DIR / "sin_ruido.csv").set_index("id")["text_limpio"]
        faltan = set(df["id"]) - set(limpio.index)
        if faltan:
            raise ValueError(f"{len(faltan)} frases de {nombre} no están en sin_ruido.csv; corre make dataset")
        df = df.assign(text=df["id"].map(limpio))
    return df.reset_index(drop=True)


def md5_frases() -> str:
    return hashlib.md5((DATA_DIR / "frases.jsonl").read_bytes()).hexdigest()


def git_commit() -> str:
    def git(*args):
        return subprocess.run(["git", *args], cwd=INTENT_DIR, capture_output=True, text=True).stdout.strip()
    commit = git("rev-parse", "HEAD") or "desconocido"
    return commit + ("-dirty" if git("status", "--porcelain") else "")


# --- Métricas ----------------------------------------------------------------


def curva_cobertura_precision(labels, preds, confianzas, taus=TAUS) -> list[dict]:
    """Para cada τ: contestadas = confianza ≥ τ. Un `ambiguo` contestado es error."""
    labels, preds, conf = np.asarray(labels), np.asarray(preds), np.asarray(confianzas, dtype=float)
    n = len(labels)
    es_ambiguo = labels == AMBIGUO
    curva = []
    for tau in taus:
        contesta = conf >= tau
        n_cont = int(contesta.sum())
        aciertos = int((contesta & (preds == labels)).sum())  # preds nunca es "ambiguo"
        curva.append({
            "tau": float(tau),
            "contestadas": n_cont,
            "cobertura": n_cont / n if n else 0.0,
            "precision": aciertos / n_cont if n_cont else None,
            "ambiguo_abstenidas": float((~contesta[es_ambiguo]).mean()) if es_ambiguo.any() else None,
        })
    return curva


def elegir_tau(curva: list[dict]) -> dict:
    """criterio_seleccion.md §4.

    1. El τ con mayor cobertura que da precisión ≥ 95 % (empate: el τ más alto).
    2. Si ninguno llega: el de mayor precisión con cobertura ≥ 50 % (empate: más cobertura), y se declara.
    """
    ok = [p for p in curva if p["precision"] is not None and p["precision"] >= PRECISION_OBJETIVO]
    if ok:
        elegido = max(ok, key=lambda p: (p["cobertura"], p["tau"]))
        regla = f"precision>={PRECISION_OBJETIVO:.0%}, max cobertura"
    else:
        cand = [p for p in curva if p["precision"] is not None and p["cobertura"] >= COBERTURA_MINIMA]
        if not cand:
            raise ValueError("ningún τ da cobertura ≥ 50 %; revisa la curva")
        elegido = max(cand, key=lambda p: (p["precision"], p["cobertura"]))
        regla = f"FALLBACK: ningún τ llega a {PRECISION_OBJETIVO:.0%}; max precision con cobertura>={COBERTURA_MINIMA:.0%}"
    return {**elegido, "regla": regla}


def punto_en_tau(curva: list[dict], tau: float) -> dict:
    return min(curva, key=lambda p: abs(p["tau"] - tau))


def _macro_f1(y, p) -> float:
    return float(f1_score(y, p, labels=CLASES, average="macro", zero_division=0))


def metricas(df: pd.DataFrame, probs: np.ndarray) -> dict:
    """df con columnas label, language, source (todas las frases, con ambiguo); probs (n, 5)."""
    probs = np.asarray(probs, dtype=float)
    if probs.shape != (len(df), len(CLASES)):
        raise ValueError(f"predict_proba debe devolver forma {(len(df), len(CLASES))}, devolvió {probs.shape}")
    preds = np.array(CLASES)[probs.argmax(axis=1)]
    conf = probs.max(axis=1)
    labels = df["label"].to_numpy()

    # Macro-F1 de 5 clases: sin ambiguo y sin abstención (criterio §2).
    m = labels != AMBIGUO
    y5, p5, sub = labels[m], preds[m], df[m]
    por_grupo = lambda col: {
        g: {"n": int(ix.sum()), "macro_f1": _macro_f1(y5[ix], p5[ix])}
        for g in sorted(sub[col].unique()) for ix in [(sub[col] == g).to_numpy()]
    }
    f1_clase = f1_score(y5, p5, labels=CLASES, average=None, zero_division=0)
    curva = curva_cobertura_precision(labels, preds, conf)
    return {
        "n": int(len(df)),
        "n_sin_ambiguo": int(m.sum()),
        "macro_f1": _macro_f1(y5, p5),
        "f1_por_clase": dict(zip(CLASES, map(float, f1_clase))),
        "por_idioma": por_grupo("language"),
        "por_source": por_grupo("source"),
        "matriz_confusion": {"clases": CLASES,
                             "filas_real_columnas_pred": confusion_matrix(y5, p5, labels=CLASES).tolist()},
        "curva_cobertura_precision": curva,
        "_preds": preds, "_conf": conf,
    }


def evaluar(candidato, split: str, permitir_test: bool = False, tau: float | None = None) -> dict:
    """Evalúa un candidato ya entrenado. Predice frase por frase para medir latencia p50.

    En val, τ se elige con elegir_tau; en test hay que pasar el τ fijado en val.
    """
    _revisar_llave(split, permitir_test)
    df = load_split(split, permitir_test=permitir_test)

    filas, lat = [], []
    for texto in df["text"]:
        t0 = time.perf_counter()
        filas.append(np.asarray(candidato.predict_proba([texto]), dtype=float)[0])
        lat.append((time.perf_counter() - t0) * 1000)

    res = metricas(df, np.vstack(filas))
    res["latencia_ms_p50"] = float(np.median(lat))
    res["costo_por_1000_usd"] = float(getattr(candidato, "costo_por_1000_usd", 0.0))

    if split == "test":
        if tau is None:
            raise ValueError("En test τ no se elige: pasa el τ fijado en val (--tau).")
        res["tau"] = {**punto_en_tau(res["curva_cobertura_precision"], tau), "regla": "fijado en val"}
    elif tau is not None:
        res["tau"] = {**punto_en_tau(res["curva_cobertura_precision"], tau), "regla": "dado"}
    else:
        res["tau"] = elegir_tau(res["curva_cobertura_precision"])

    preds, conf = res.pop("_preds"), res.pop("_conf")
    res["predicciones"] = [
        {"id": i, "label": l, "pred": p, "conf": round(float(c), 4)}
        for i, l, p, c in zip(df["id"], df["label"], preds, conf)
    ]
    return res


# --- Registro ----------------------------------------------------------------


def guardar_run(candidato: str, split: str, params: dict, res: dict, datos: dict | None = None) -> Path:
    """Escribe ml/intent/runs/<fecha>_<candidato>_<split>.json."""
    RUNS_DIR.mkdir(exist_ok=True)
    fecha = datetime.now().strftime("%Y%m%d-%H%M%S")
    ruta = RUNS_DIR / f"{fecha}_{candidato}_{split}.json"
    k = 2
    while ruta.exists():
        ruta = RUNS_DIR / f"{fecha}_{candidato}_{split}_{k}.json"
        k += 1
    run = {
        "candidato": candidato,
        "split": split,
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "params": params,
        "datos": {"frases_md5": md5_frases(), **(datos or {})},
        "git_commit": git_commit(),
        "tau": res.get("tau"),
        "metricas": {k: v for k, v in res.items() if k not in ("tau", "predicciones")},
        "predicciones": res.get("predicciones", []),
    }
    ruta.write_text(json.dumps(run, ensure_ascii=False, indent=1))
    return ruta


def correr(nombre: str, params: dict, split: str, fuentes=None, sin_ruido: bool = False,
           permitir_test: bool = False, tau: float | None = None) -> tuple[dict, Path]:
    """Entrena ml.intent.candidates.<nombre> con train (sin ambiguo), evalúa y guarda el run."""
    _revisar_llave(split, permitir_test)
    if split == "train":
        raise ValueError("evaluar en train no sirve para elegir; usa val")
    modulo = importlib.import_module(f"ml.intent.candidates.{nombre}")
    candidato = modulo.crear(**params)
    train = load_split("train", fuentes=fuentes, sin_ruido=sin_ruido)
    train = train[train["label"] != AMBIGUO]
    candidato.fit(train["text"].tolist(), train["label"].tolist())
    res = evaluar(candidato, split, permitir_test=permitir_test, tau=tau)
    datos = {"train_fuentes": fuentes or "todas", "train_sin_ruido": sin_ruido, "train_n": int(len(train))}
    return res, guardar_run(nombre, split, params, res, datos)


def _valor(v: str):
    for tipo in (int, float):
        try:
            return tipo(v)
        except ValueError:
            pass
    return v


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--candidato", required=True, help="módulo en ml/intent/candidates/")
    ap.add_argument("--split", default="val", choices=["val", "test"])
    ap.add_argument("--param", action="append", default=[], metavar="K=V")
    ap.add_argument("--fuentes", nargs="+", help="sources para entrenar (default: todas)")
    ap.add_argument("--sin-ruido", action="store_true", help="entrena con el texto sin ruido")
    ap.add_argument("--tau", type=float, help="τ fijo (obligatorio en test)")
    ap.add_argument("--test", action="store_true", help="abre el test (una sola vez, Paso 10)")
    a = ap.parse_args(argv)

    params = {k: _valor(v) for k, v in (p.split("=", 1) for p in a.param)}
    try:
        res, ruta = correr(a.candidato, params, a.split, a.fuentes, a.sin_ruido, a.test, a.tau)
    except SplitBajoLlave as e:
        sys.exit(f"ERROR: {e}")
    t = res["tau"]
    print(f"{a.candidato} {params} en {a.split}: macro-F1 {res['macro_f1']:.3f} · "
          + " · ".join(f"{g} {v['macro_f1']:.3f}" for g, v in res["por_idioma"].items()))
    print(f"τ={t['tau']:.2f}: cobertura {t['cobertura']:.1%} · precisión {t['precision'] or 0:.1%} · "
          f"ambiguo abstenidas {t['ambiguo_abstenidas'] or 0:.1%} ({t['regla']})")
    print(f"latencia p50 {res['latencia_ms_p50']:.2f} ms · run: {ruta.relative_to(INTENT_DIR.parent.parent)}")


if __name__ == "__main__":
    main()
