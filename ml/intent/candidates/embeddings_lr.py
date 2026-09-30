"""Candidato 3 (Paso 6 de la guía 4.2): embeddings multilingües (fastembed, ONNX) + regresión logística.

Modelos (MODELOS):
    - minilm: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (nativo en fastembed).
    - e5s:    intfloat/multilingual-e5-small. No viene en fastembed 0.8.1; se registra como
              modelo custom con el ONNX del propio repo de HF (mean pooling + normalización,
              como su config de sentence-transformers). Pide el prefijo "query: ".
LogisticRegression con class_weight="balanced"; C se busca en val.

Caché (fuera de git, ml/intent/.cache/):
    - models/  pesos ONNX descargados por fastembed.
    - emb/     embeddings de train por modelo y md5 del texto. Solo se usa en fit: en
               predict_proba el embedding se calcula en vivo para que la latencia p50 sea real.

Variante de 6 clases (clases=6): entrena también con `ambiguo`. Si el argmax es `ambiguo`,
la fila de 5 columnas se multiplica por 1e-6: conserva el argmax entre las 5 (macro-F1)
pero la confianza queda ≈ 0, así que se abstiene a cualquier τ > 0.

    .venv/bin/python -m ml.intent.candidates.embeddings_lr    # barrido completo + variante 6 clases
"""

import hashlib
from pathlib import Path

import joblib
import numpy as np
from fastembed import TextEmbedding
from fastembed.common.model_description import ModelSource, PoolingType
from sklearn.linear_model import LogisticRegression

from ml.intent.evaluate import AMBIGUO, CLASES, INTENT_DIR

SEED = 42
C_GRILLA = [0.1, 1, 10]
CACHE_DIR = INTENT_DIR / ".cache"
MODELS_DIR = CACHE_DIR / "models"
EMB_DIR = CACHE_DIR / "emb"

MODELOS = {
    "minilm": {"hf": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", "prefijo": ""},
    "e5s": {"hf": "intfloat/multilingual-e5-small", "prefijo": "query: "},
}
_E5S_REGISTRADO = False


def _registrar_e5s() -> None:
    global _E5S_REGISTRADO
    if _E5S_REGISTRADO:
        return
    hf = MODELOS["e5s"]["hf"]
    if hf not in {m["model"] for m in TextEmbedding.list_supported_models()}:
        TextEmbedding.add_custom_model(
            model=hf, pooling=PoolingType.MEAN, normalization=True,
            sources=ModelSource(hf=hf), dim=384, model_file="onnx/model.onnx",
            description="multilingual-e5-small, ONNX del repo de HF", license="mit", size_in_gb=0.47)
    _E5S_REGISTRADO = True


_ENCODERS: dict[str, TextEmbedding] = {}


def encoder(modelo: str) -> TextEmbedding:
    """Un TextEmbedding por proceso y modelo (cargar el ONNX tarda segundos)."""
    if modelo not in _ENCODERS:
        if modelo == "e5s":
            _registrar_e5s()
        _ENCODERS[modelo] = TextEmbedding(MODELOS[modelo]["hf"], cache_dir=str(MODELS_DIR), threads=1)
    return _ENCODERS[modelo]


def embed(modelo: str, textos) -> np.ndarray:
    pre = MODELOS[modelo]["prefijo"]
    return np.vstack(list(encoder(modelo).embed([pre + t for t in textos], batch_size=64)))


def embed_cacheado(modelo: str, textos) -> np.ndarray:
    """Embeddings con caché en disco, clave = md5 de la lista de textos."""
    clave = hashlib.md5("\n".join(textos).encode()).hexdigest()[:16]
    ruta = EMB_DIR / f"{modelo}_{clave}.npy"
    if ruta.exists():
        return np.load(ruta)
    EMB_DIR.mkdir(parents=True, exist_ok=True)
    X = embed(modelo, textos)
    np.save(ruta, X)
    return X


def tamano_modelo_mb(modelo: str) -> float:
    """MB en disco de los archivos del modelo en la caché de fastembed (sin symlinks duplicados)."""
    nombre = MODELOS[modelo]["hf"].split("/")[1]  # fastembed puede bajarlo de otro repo (p. ej. qdrant/...-onnx-Q)
    archivos = {p.resolve() for d in MODELS_DIR.glob(f"*{nombre}*") for p in d.rglob("*") if p.is_file()}
    return sum(p.stat().st_size for p in archivos) / 1e6


class EmbeddingsLR:
    costo_por_1000_usd = 0.0

    def __init__(self, modelo: str = "minilm", C: float = 1.0, clases: int = 5):
        if modelo not in MODELOS:
            raise ValueError(f"modelo desconocido: {modelo!r} (usa uno de {sorted(MODELOS)})")
        if clases not in (5, 6):
            raise ValueError("clases debe ser 5 o 6")
        self.modelo, self.C, self.clases = modelo, C, clases
        self.lr = LogisticRegression(C=C, class_weight="balanced", max_iter=5000, random_state=SEED)

    def fit(self, textos, labels):
        self.lr.fit(embed_cacheado(self.modelo, list(textos)), labels)
        return self

    def predict_proba(self, textos):
        probs = self.lr.predict_proba(embed(self.modelo, list(textos)))
        cls = list(self.lr.classes_)
        cinco = probs[:, [cls.index(c) for c in CLASES]]
        if self.clases == 6:
            abstiene = probs.argmax(axis=1) == cls.index(AMBIGUO)
            cinco[abstiene] *= 1e-6
        return cinco

    def tamano_lr_mb(self) -> float:
        ruta = CACHE_DIR / f"lr_{self.modelo}_{self.clases}.joblib"
        joblib.dump(self.lr, ruta)
        return ruta.stat().st_size / 1e6


def crear(**params):
    return EmbeddingsLR(**params)


# --- Barrido (Paso 6) ----------------------------------------------------------


def _correr(params: dict, split: str = "val", permitir_test: bool = False, tau: float | None = None):
    """Como evaluate.correr, pero con 6 clases deja `ambiguo` en train. En test, τ es el de val."""
    from ml.intent.evaluate import evaluar, guardar_run, load_split

    cand = crear(**params)
    train = load_split("train")
    if params.get("clases", 5) == 5:
        train = train[train["label"] != AMBIGUO]
    cand.fit(train["text"].tolist(), train["label"].tolist())
    res = evaluar(cand, split, permitir_test=permitir_test, tau=tau)
    mb_modelo, mb_lr = tamano_modelo_mb(cand.modelo), cand.tamano_lr_mb()
    res["tamano_mb"] = {"modelo_embeddings": round(mb_modelo, 1), "logistica": round(mb_lr, 3),
                        "total": round(mb_modelo + mb_lr, 1)}
    datos = {"train_fuentes": "todas", "train_sin_ruido": False, "train_n": int(len(train)),
             "train_incluye_ambiguo": params.get("clases", 5) == 6}
    return res, guardar_run("embeddings_lr", split, params, res, datos)


def _fila(params, res, ruta) -> str:
    t, idi = res["tau"], res["por_idioma"]
    return (f"{params['modelo']:>6} | {params['clases']:>2} | {params['C']:>4} | {res['macro_f1']:>8.3f} | "
            + " | ".join(f"{idi[g]['macro_f1']:>5.3f}" if g in idi else "    -" for g in ("es", "pt", "mix"))
            + f" | {t['tau']:>4.2f} | {t['cobertura']:>7.1%} | {t['precision'] or 0:>7.1%} | "
              f"{t['ambiguo_abstenidas'] or 0:>7.1%} | {res['latencia_ms_p50']:>6.2f} | "
              f"{res['tamano_mb']['total']:>7.1f} | {ruta.name}")


def _barrido():
    filas = []
    for modelo in MODELOS:
        for C in C_GRILLA:
            params = {"modelo": modelo, "C": C, "clases": 5}
            res, ruta = _correr(params)
            filas.append((params, res, ruta))
            print(f"  {params}: macro-F1 {res['macro_f1']:.3f}", flush=True)

    mejor_p, mejor, _ = max(filas, key=lambda f: f[1]["macro_f1"])
    for C in C_GRILLA:
        params = {"modelo": mejor_p["modelo"], "C": C, "clases": 6}
        res, ruta = _correr(params)
        filas.append((params, res, ruta))
        print(f"  {params}: macro-F1 {res['macro_f1']:.3f}", flush=True)

    print(f"\n{'modelo':>6} | {'k':>2} | {'C':>4} | {'macro-F1':>8} | {'es':>5} | {'pt':>5} | {'mix':>5} | "
          f"{'τ':>4} | {'cobert.':>7} | {'precis.':>7} | {'amb.abs':>7} | {'p50 ms':>6} | {'MB disco':>7} | run")
    for f in filas:
        print(_fila(*f))

    seis = [f for f in filas if f[0]["clases"] == 6]
    p6, r6, _ = max(seis, key=lambda f: f[1]["macro_f1"])
    print(f"\nMejor 5 clases: {mejor_p} (macro-F1 {mejor['macro_f1']:.3f})")
    print(f"Mejor 6 clases: {p6} (macro-F1 {r6['macro_f1']:.3f})")
    print("\nCurva cobertura-precisión en val (5 clases vs 6 clases):")
    print(f"{'τ':>4} | {'cob5':>6} | {'prec5':>6} | {'amb5':>6} || {'cob6':>6} | {'prec6':>6} | {'amb6':>6}")
    c5 = {p["tau"]: p for p in mejor["curva_cobertura_precision"]}
    c6 = {p["tau"]: p for p in r6["curva_cobertura_precision"]}
    fmt = lambda v: f"{v:>6.1%}" if v is not None else "     -"
    for tau in [0.0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.99]:
        a, b = c5[tau], c6[tau]
        print(f"{tau:>4.2f} | {fmt(a['cobertura'])} | {fmt(a['precision'])} | {fmt(a['ambiguo_abstenidas'])} || "
              f"{fmt(b['cobertura'])} | {fmt(b['precision'])} | {fmt(b['ambiguo_abstenidas'])}")
    for nombre, r in (("5 clases", mejor), ("6 clases", r6)):
        t = r["tau"]
        print(f"τ elegido {nombre}: {t['tau']:.2f} → cobertura {t['cobertura']:.1%}, precisión "
              f"{t['precision'] or 0:.1%}, ambiguo abstenidas {t['ambiguo_abstenidas'] or 0:.1%} ({t['regla']})")
    return filas


if __name__ == "__main__":
    np.random.seed(SEED)
    _barrido()
