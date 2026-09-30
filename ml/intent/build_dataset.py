"""Paso 9 de la Fase 4.1: arma el set final de intenciones y valida que no haya fuga.

Uso: make dataset   (o .venv/bin/python -m ml.intent.build_dataset)

1. Lee b77_traducido.csv (Banking77), suplemento_llm.csv, suplemento_fuera_alcance.csv
   (lote 2, D4.6) y test_para_escribir.csv.
   Quita del pool los textos repetidos con la misma etiqueta (y los lista).
2. Divide el pool Banking77 + suplemento en train/val 80/20 por familia (semilla
   42), estratificando por source × label × language. El test va aparte. Las familias
   del lote 2 se dividen después y con su propio generador, para que agregarlas no
   cambie el split de las familias que ya existían.
3. Aplica noise.py a train/val (nunca a test) y guarda el texto sin ruido en
   data/sin_ruido.csv, para la ablación con/sin ruido de la 4.2.
4. Valida (y falla con un mensaje claro si algo está mal): familias en dos
   splits, origin prohibido en test, duplicados normalizados, valores fuera de
   los permitidos, números alterados por el ruido y similitud TF-IDF > 0,9
   entre test y train/val.
5. Escribe data/frases.jsonl, train.jsonl, val.jsonl y test.jsonl con el formato
   de labeling_guide.md, e imprime tablas de conteos.

Los archivos solo se escriben si todas las validaciones pasan.
"""

import json
import random
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ml.intent.noise import TRANSFORMACIONES, aplicar_ruido, numeros

SEED = 42
VAL_FRAC = 0.20
UMBRAL_SIMILITUD = 0.9

INTENT_DIR = Path(__file__).resolve().parent
DATA_DIR = INTENT_DIR / "data"

PERMITIDOS = {
    "label": {"cargo_no_reconocido", "cobro_incorrecto", "tarjeta_comprometida", "estado_disputa", "fuera_de_alcance", "ambiguo"},
    "language": {"es", "pt", "mix"},
    "variant": {"MX", "CO", "AR", "BR", "PT", "neutro"},
    "origin": {"equipo", "equipo_traducido", "externo_traducido", "llm", "llm_externo"},
    "source": {"banking77", "suplemento", "test_equipo"},
    "split": {"train", "val", "test"},
}
ORIGIN_PROHIBIDO_EN_TEST = {"llm", "externo_traducido"}
PREFIJO = {"banking77": "b", "suplemento": "s", "test_equipo": "t"}
CAMPOS = ["id", "family_id", "text", "label", "language", "variant", "author", "origin", "source", "source_ref", "noise", "split"]


# --- Lectura ---------------------------------------------------------------


def leer_banking77() -> pd.DataFrame:
    df = pd.read_csv(INTENT_DIR / "b77_traducido.csv")
    # En Banking77 cada frase es su propia familia.
    df["family_id"] = df["b77_idx"].map(lambda i: f"b{i:05d}")
    return pd.DataFrame({
        "id": df["family_id"] + "-01",
        "family_id": df["family_id"],
        "text": df["text"],
        "label": df["label"],
        "language": df["language"],
        "variant": df["variant"],
        "origin": "externo_traducido",
        "source": "banking77",
        "source_ref": df["b77_idx"].astype(str) + ":" + df["b77_label"],
    })


LOTE_2 = "suplemento_fuera_alcance.csv"  # D4.6: fuera de alcance (préstamo, límite, saldo, PIN, cuenta)


def leer_suplemento() -> pd.DataFrame:
    df = pd.concat([pd.read_csv(INTENT_DIR / "suplemento_llm.csv").assign(lote=1),
                    pd.read_csv(INTENT_DIR / LOTE_2).assign(lote=2)], ignore_index=True)
    nn = df.groupby("family_id").cumcount() + 1
    return pd.DataFrame({
        "id": df["family_id"] + "-" + nn.map("{:02d}".format),
        "family_id": df["family_id"],
        "text": df["text"],
        "label": df["label"],
        "language": df["language"],
        "variant": df["variant"],
        "origin": "llm",
        "source": "suplemento",
        "source_ref": None,
        "lote": df["lote"],
    })


def leer_test() -> pd.DataFrame:
    df = pd.read_csv(INTENT_DIR / "test_para_escribir.csv")
    # La variante viene en notas ("Variante sugerida: MX ...") cuando la columna está vacía.
    sugerida = df["notas"].str.extract(r"Variante sugerida:\s*(MX|CO|AR|BR|PT|neutro)\b")[0]
    df["variant"] = df["variant"].fillna(sugerida)
    columnas = ["semilla", "parafrasis_1", "parafrasis_2", "parafrasis_3"]
    largo = df.melt(
        id_vars=["family_id", "label", "language", "variant", "origin"],
        value_vars=columnas, var_name="columna", value_name="text",
    )
    largo["nn"] = largo["columna"].map({c: i + 1 for i, c in enumerate(columnas)})
    largo = largo.sort_values(["family_id", "nn"]).reset_index(drop=True)
    return pd.DataFrame({
        "id": largo["family_id"] + "-" + largo["nn"].map("{:02d}".format),
        "family_id": largo["family_id"],
        "text": largo["text"],
        "label": largo["label"],
        "language": largo["language"],
        "variant": largo["variant"],
        "origin": largo["origin"],
        "source": "test_equipo",
        "source_ref": None,
    })


# --- Split y ruido ----------------------------------------------------------


def deduplicar(pool: pd.DataFrame) -> pd.DataFrame:
    """Quita del pool los textos repetidos (normalizados) con la misma etiqueta.

    Banking77 tiene frases casi iguales en inglés que quedan idénticas al
    traducirlas. Se conserva la del suplemento (su familia queda completa) y, si
    no hay, la de id menor. Si los repetidos tienen etiquetas distintas no se
    toca nada: validar() lo reporta y hay que decidir a mano.
    """
    norm = pool["text"].map(normalizar)
    etiquetas = pool.groupby(norm)["label"].transform("nunique")
    orden = pool.assign(_norm=norm, _b77=pool["source"] == "banking77").sort_values(["_b77", "id"])
    sobran = orden[orden["_norm"].duplicated() & (etiquetas.loc[orden.index] == 1)]
    if len(sobran):
        print(f"Deduplicación: se quitan {len(sobran)} frases repetidas del pool (misma etiqueta):")
        conservada = orden.drop_duplicates("_norm").set_index("_norm")["id"]
        for _, f in sobran.sort_values("id").iterrows():
            print(f"  - {f['id']} (igual a {conservada[f['_norm']]}): {f['text']!r}")
        print()
    return pool.drop(index=sobran.index).reset_index(drop=True)


def split_por_familia(pool: pd.DataFrame) -> pd.Series:
    """80/20 por familia, estratificado por source × label × language."""
    lote = pool["lote"].fillna(1) if "lote" in pool else pd.Series(1, index=pool.index)
    familias = pool.assign(lote=lote).groupby("family_id")[["source", "label", "language", "lote"]].first().reset_index()
    split = {}
    for n_lote in sorted(familias["lote"].unique()):
        rng = random.Random(SEED + int(n_lote) - 1)
        for _, grupo in familias[familias["lote"] == n_lote].groupby(["source", "label", "language"], sort=True):
            ids = sorted(grupo["family_id"])
            rng.shuffle(ids)
            n_val = round(len(ids) * VAL_FRAC)
            for i, fam in enumerate(ids):
                split[fam] = "val" if i < n_val else "train"
    return pool["family_id"].map(split)


def agregar_ruido(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["text_limpio"] = df["text"]
    df["noise"] = [[] for _ in range(len(df))]
    es_pool = df["split"] != "test"
    resultados = [
        aplicar_ruido(t, lang, clave=i)
        for t, lang, i in zip(df.loc[es_pool, "text"], df.loc[es_pool, "language"], df.loc[es_pool, "id"])
    ]
    df.loc[es_pool, "text"] = [r[0] for r in resultados]
    df.loc[es_pool, "noise"] = pd.Series([r[1] for r in resultados], index=df.index[es_pool])
    return df


# --- Validaciones -----------------------------------------------------------


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes ni puntuación. Las frases de solo signos o emojis
    ("??", "😡") se comparan tal cual, para no volverlas todas ""."""
    base = unicodedata.normalize("NFD", texto.lower())
    base = "".join(c for c in base if unicodedata.category(c) != "Mn")
    base = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", base)).strip()
    return base or re.sub(r"\s+", " ", texto).strip()


def validar(df: pd.DataFrame) -> list[str]:
    errores = []

    # Valores permitidos y campos obligatorios.
    for campo, valores in PERMITIDOS.items():
        malos = df[~df[campo].isin(valores)]
        for _, f in malos.iterrows():
            errores.append(f"Valor no permitido en {campo}: {f[campo]!r} (id {f['id']})")
    vacios = df[df["text"].isna() | (df["text"].astype(str).str.strip() == "")]
    for i in vacios["id"]:
        errores.append(f"Texto vacío: {i}")
    for _, f in df[~df.apply(lambda f: f["id"].startswith(PREFIJO.get(f["source"], "?")), axis=1)].iterrows():
        errores.append(f"El id {f['id']} no tiene el prefijo de su fuente ({f['source']})")
    for i in df.loc[df["id"].duplicated(), "id"]:
        errores.append(f"id repetido: {i}")
    for i in df.loc[(df["source"] == "banking77") & df["source_ref"].isna(), "id"]:
        errores.append(f"Frase de Banking77 sin source_ref: {i}")
    for i in df.loc[(df["source"] != "banking77") & df["source_ref"].notna(), "id"]:
        errores.append(f"source_ref debe ser null fuera de Banking77: {i}")
    for _, f in df[~df["noise"].map(lambda n: set(n) <= set(TRANSFORMACIONES))].iterrows():
        errores.append(f"Transformación de ruido desconocida en {f['id']}: {f['noise']}")

    # Una familia = un split, una etiqueta, un idioma.
    for col in ["split", "label", "language"]:
        n = df.groupby("family_id")[col].nunique()
        for fam in n[n > 1].index:
            vals = sorted(df.loc[df["family_id"] == fam, col].unique())
            errores.append(f"La familia {fam} tiene más de un {col}: {vals}")

    # El test sale solo del test del equipo.
    test = df[df["split"] == "test"]
    for _, f in test[test["origin"].isin(ORIGIN_PROHIBIDO_EN_TEST)].iterrows():
        errores.append(f"origin {f['origin']} no puede ir a test: {f['id']}")
    for _, f in test[test["source"] != "test_equipo"].iterrows():
        errores.append(f"Frase de {f['source']} en test: {f['id']}")
    for _, f in test[test["noise"].map(len) > 0].iterrows():
        errores.append(f"El test no lleva ruido artificial: {f['id']}")

    # El ruido no toca números ni montos.
    cambiados = df[df.apply(lambda f: numeros(f["text"]) != numeros(f["text_limpio"]), axis=1)]
    for _, f in cambiados.iterrows():
        errores.append(f"El ruido alteró números en {f['id']}: {f['text_limpio']!r} -> {f['text']!r}")

    # Duplicados normalizados (con y sin ruido).
    for col in ["text_limpio", "text"]:
        norm = df[col].map(normalizar)
        dup = df.assign(norm=norm)[norm.duplicated(keep=False)]
        for texto, grupo in dup.groupby("norm"):
            errores.append(f"Texto duplicado ({col}) {texto!r}: {', '.join(grupo['id'])}")

    # Test demasiado parecido a train/val (con el texto sin ruido, que es el más parecido).
    pool = df[df["split"] != "test"]
    vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True).fit(df["text_limpio"].map(normalizar))
    sim = cosine_similarity(
        vec.transform(test["text_limpio"].map(normalizar)),
        vec.transform(pool["text_limpio"].map(normalizar)),
    )
    for i, j in zip(*(sim > UMBRAL_SIMILITUD).nonzero()):
        t, p = test.iloc[i], pool.iloc[j]
        errores.append(
            f"Similitud TF-IDF {sim[i, j]:.3f} entre test {t['id']} {t['text_limpio']!r} "
            f"y {p['split']} {p['id']} {p['text_limpio']!r}"
        )
    print(f"Similitud TF-IDF máxima test vs train/val: {sim.max():.3f} (umbral {UMBRAL_SIMILITUD})")
    return errores


# --- Salida -----------------------------------------------------------------


def imprimir_tablas(df: pd.DataFrame) -> None:
    pd.set_option("display.width", 200)
    print("\n== split × label × language")
    print(pd.crosstab([df["split"], df["label"]], df["language"], margins=True, margins_name="total").to_string())
    print("\n== split × language")
    print(pd.crosstab(df["split"], df["language"], margins=True, margins_name="total").to_string())
    print("\n== source × origin")
    print(pd.crosstab(df["source"], df["origin"], margins=True, margins_name="total").to_string())
    print("\n== source × split (frases / familias)")
    frases = pd.crosstab(df["source"], df["split"], margins=True, margins_name="total")
    familias = pd.crosstab(df["source"], df["split"], values=df["family_id"], aggfunc="nunique").fillna(0).astype(int)
    print(frases.to_string())
    print(familias.to_string())

    pool = df[df["split"] != "test"]
    print(f"\n== Ruido en train/val ({len(pool)} frases)")
    filas = [("sin_ruido", (pool["noise"].map(len) == 0).mean())]
    filas += [(t, pool["noise"].map(lambda n, t=t: t in n).mean()) for t in TRANSFORMACIONES]
    for nombre, p in filas:
        print(f"  {nombre:<15}{p:6.1%}")


def escribir(df: pd.DataFrame) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df = df.assign(author=None)
    df["source_ref"] = df["source_ref"].where(df["source_ref"].notna(), None)
    registros = df[CAMPOS].to_dict("records")

    def volcar(nombre: str, filas: list[dict]) -> None:
        with open(DATA_DIR / nombre, "w", encoding="utf-8") as f:
            for r in filas:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"  {nombre:<14}{len(filas):>6} frases")

    print(f"\n== Archivos en {DATA_DIR.relative_to(INTENT_DIR.parents[1])}/")
    volcar("frases.jsonl", registros)
    for split in ["train", "val", "test"]:
        volcar(f"{split}.jsonl", [r for r in registros if r["split"] == split])

    sin_ruido = df.loc[df["split"] != "test", ["id", "split", "label", "language", "source", "text_limpio", "text", "noise"]]
    sin_ruido = sin_ruido.rename(columns={"text": "text_con_ruido"}).assign(noise=lambda d: d["noise"].map(json.dumps))
    sin_ruido.to_csv(DATA_DIR / "sin_ruido.csv", index=False)
    print(f"  {'sin_ruido.csv':<14}{len(sin_ruido):>6} frases (train/val, para la ablación)")


def main() -> None:
    pool = deduplicar(pd.concat([leer_banking77(), leer_suplemento()], ignore_index=True))
    pool["split"] = split_por_familia(pool)
    test = leer_test().assign(split="test")
    df = agregar_ruido(pd.concat([pool, test], ignore_index=True))

    imprimir_tablas(df)
    print()
    errores = validar(df)
    if errores:
        print(f"\nERROR: {len(errores)} problema(s); no se escribió ningún archivo.", file=sys.stderr)
        for e in errores:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    print("OK: todas las validaciones pasaron.")
    escribir(df)


if __name__ == "__main__":
    main()
