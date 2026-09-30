"""Exactitud por campo de un extractor sobre ml/llm/extraccion_casos.jsonl.

Uso:  python ml/llm/evaluar_extraccion.py --extractor rules [--split dev]

Solo se ajusta mirando dev. El test se abre una sola vez (Paso 8 de la guía de la 4.3).
Los casos con `pendiente` no cuentan en las métricas: se listan aparte.
Compara merchant_hint sin mayúsculas ni tildes, y los montos con tolerancia de 0,005.
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path

AQUI = Path(__file__).parent
RAIZ = AQUI.parents[1]
sys.path.insert(0, str(RAIZ / "backend"))

CASOS = AQUI / "extraccion_casos.jsonl"
CAMPOS = ["language", "amount", "currency", "date_from", "date_to", "merchant_hint",
          "selected_option", "confirmation", "suspected_injection"]


def _norm(campo: str, v):
    if v is None:
        return None
    if isinstance(v, date):
        return v.isoformat()
    if campo == "merchant_hint":
        s = unicodedata.normalize("NFD", str(v).lower().strip())
        return "".join(c for c in s if unicodedata.category(c) != "Mn")
    if campo == "amount":
        return round(float(v), 2)
    return v


def cargar_extractor(nombre: str):
    if nombre == "rules":
        from app.nlu import rules
        return lambda texto, state: rules.extract(texto, state)
    raise SystemExit(f"extractor desconocido: {nombre}")


def evaluar(extractor, split: str) -> tuple[dict, list, list]:
    aciertos, total = defaultdict(int), defaultdict(int)
    errores, pendientes = [], []
    for linea in CASOS.read_text(encoding="utf-8").splitlines():
        caso = json.loads(linea)
        if caso["split"] != split:
            continue
        salida = extractor(caso["text"], caso["state"])
        mal = {c: (caso["expected"][c], _norm(c, salida.get(c))) for c in CAMPOS
               if _norm(c, caso["expected"][c]) != _norm(c, salida.get(c))}
        if caso["pendiente"]:
            pendientes.append((caso, mal))
            continue
        for c in CAMPOS:
            total[c] += 1
            aciertos[c] += c not in mal
        if mal:
            errores.append((caso, mal))
    metricas = {c: (aciertos[c], total[c]) for c in CAMPOS}
    metricas["casos sin error"] = (total["language"] - len(errores), total["language"])
    return metricas, errores, pendientes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extractor", default="rules")
    ap.add_argument("--split", default="dev", choices=["dev", "test"])
    args = ap.parse_args()
    metricas, errores, pendientes = evaluar(cargar_extractor(args.extractor), args.split)

    print(f"Extractor: {args.extractor} · split: {args.split}\n")
    print(f"{'campo':<22}{'aciertos':>10}{'exactitud':>11}")
    for c, (a, t) in metricas.items():
        print(f"{c:<22}{f'{a}/{t}':>10}{(a / t if t else 0):>10.1%}")
    print(f"\nErrores ({len(errores)} casos):")
    for caso, mal in errores:
        detalle = " · ".join(f"{c}: esperado {e!r}, salió {s!r}" for c, (e, s) in mal.items())
        print(f"  {caso['id']:<6} [{caso['state'] or '-'}] {caso['text']!r}\n         {detalle}")
    if pendientes:
        print(f"\nPendientes (no cuentan): {len(pendientes)}")
        for caso, mal in pendientes:
            print(f"  {caso['id']:<6} {caso['text']!r} → {'OK' if not mal else mal}")


if __name__ == "__main__":
    main()
