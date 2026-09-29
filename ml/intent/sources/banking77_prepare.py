"""Paso 3 de la Fase 4.1: descarga Banking77 y propone el mapeo de clases.

Uso: .venv/bin/python -m ml.intent.sources.banking77_prepare

1. Descarga PolyAI/banking77 (train + test originales, juntos) y lo guarda en
   data/external/banking77.csv (data/ está en .gitignore).
   El dataset de Hugging Face (PolyAI/banking77) es un script de carga que baja
   estos mismos dos CSV del repo oficial de PolyAI; los leemos directo para no
   depender de la librería `datasets`.
2. Verifica que las clases del mapeo propuesto existan tal cual en el dataset.
3. Escribe ml/intent/b77_mapeo.csv con una fila por clase (77) para que la
   persona de ML llene la columna `decision`.

Licencia de Banking77: CC-BY-4.0 (Casanueva et al., 2020, arXiv:2003.04807).
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
RAW_PATH = ROOT / "data" / "external" / "banking77.csv"
MAPEO_PATH = ROOT / "ml" / "intent" / "b77_mapeo.csv"

URLS = {
    "train": "https://raw.githubusercontent.com/PolyAI-LDN/task-specific-datasets/master/banking_data/train.csv",
    "test": "https://raw.githubusercontent.com/PolyAI-LDN/task-specific-datasets/master/banking_data/test.csv",
}

SEED = 42
N_EJEMPLOS = 3

# Mapeo propuesto en docs/Rol B - ML/guia_fase_4_1_etiquetado.md (Paso 3).
# Las clases que no aparecen aquí quedan como "fuera_de_alcance_resto".
MAPEO_PROPUESTO = {
    "cargo_no_reconocido": [
        "card_payment_not_recognised",
        "cash_withdrawal_not_recognised",
        "direct_debit_payment_not_recognised",
    ],
    "cobro_incorrecto": [
        "transaction_charged_twice",
        "extra_charge_on_statement",
        "card_payment_wrong_exchange_rate",
        "wrong_exchange_rate_for_cash_withdrawal",
        "wrong_amount_of_cash_received",
    ],
    # Depende de cada frase (aclaración de comisiones); se revisan en el Paso 4.
    "cobro_incorrecto_o_fuera_de_alcance": [
        "card_payment_fee_charged",
        "cash_withdrawal_charge",
    ],
    "tarjeta_comprometida": [
        "compromised_card",
        "lost_or_stolen_card",
    ],
    # Negativos difíciles: se parecen a nuestras clases pero no lo son.
    "fuera_de_alcance_dificil": [
        "declined_card_payment",
        "pending_card_payment",
        "request_refund",
        "Refund_not_showing_up",
        "reverted_card_payment?",
        "balance_not_updated_after_card_payment",
        "card_swallowed",
    ],
    "por_decidir": [
        "lost_or_stolen_phone",
    ],
}


def descargar() -> pd.DataFrame:
    partes = []
    for split, url in URLS.items():
        df = pd.read_csv(url)
        df["split_original"] = split
        partes.append(df)
    df = pd.concat(partes, ignore_index=True)
    df = df.rename(columns={"category": "b77_label"})
    df.insert(0, "b77_idx", range(len(df)))
    return df[["b77_idx", "text", "b77_label", "split_original"]]


def verificar_mapeo(clases: set[str]) -> list[str]:
    faltantes = [
        clase
        for lista in MAPEO_PROPUESTO.values()
        for clase in lista
        if clase not in clases
    ]
    if faltantes:
        print("AVISO: estas clases del mapeo NO existen tal cual en Banking77:")
        for clase in faltantes:
            print(f"  - {clase}")
    else:
        n = sum(len(v) for v in MAPEO_PROPUESTO.values())
        print(f"OK: las {n} clases del mapeo propuesto existen tal cual en Banking77.")
    return faltantes


def construir_mapeo(df: pd.DataFrame) -> pd.DataFrame:
    propuesta = {c: label for label, lista in MAPEO_PROPUESTO.items() for c in lista}
    filas = []
    for clase, grupo in df.groupby("b77_label", sort=True):
        ejemplos = grupo["text"].sample(n=N_EJEMPLOS, random_state=SEED).tolist()
        filas.append(
            {
                "b77_label": clase,
                "n_frases": len(grupo),
                **{f"ejemplo_{i + 1}": e for i, e in enumerate(ejemplos)},
                "label_propuesta": propuesta.get(clase, "fuera_de_alcance_resto"),
                "decision": "",
            }
        )
    return pd.DataFrame(filas)


def main() -> None:
    df = descargar()
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(RAW_PATH, index=False)
    print(f"Banking77: {len(df)} frases, {df['b77_label'].nunique()} clases -> {RAW_PATH.relative_to(ROOT)}")
    print(df["split_original"].value_counts().to_string(), "\n")

    verificar_mapeo(set(df["b77_label"]))

    mapeo = construir_mapeo(df)
    mapeo.to_csv(MAPEO_PATH, index=False)
    print(f"\nMapeo: {len(mapeo)} clases -> {MAPEO_PATH.relative_to(ROOT)}")
    print(mapeo["label_propuesta"].value_counts().to_string())


if __name__ == "__main__":
    main()
