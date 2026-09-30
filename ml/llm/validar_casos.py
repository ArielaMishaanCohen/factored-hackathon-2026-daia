"""Valida ml/llm/extraccion_casos.jsonl, imprime conteos y escribe el CSV de revisión a mano.

El CSV se puede volver a generar sin perder la revisión: `ok (s/n)` y `comentario` se conservan
por id. Si un caso revisado cambió (texto, state o esperado), su revisión anterior pasa al
comentario con un aviso y `ok` queda vacío para revisarlo de nuevo. La revisión de un id que ya
no existe se agrega a extraccion_casos_revision_retirados.csv en vez de perderse.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

AQUI = Path(__file__).parent
ARCHIVO = AQUI / "extraccion_casos.jsonl"
CSV_REVISION = AQUI / "extraccion_casos_revision.csv"
CSV_RETIRADOS = AQUI / "extraccion_casos_revision_retirados.csv"
REFERENCE_DATE = date(2026, 6, 17)  # config/policy.yaml → reference_date
ESTADOS = {None, "IDENTIFICAR_TRANSACCION", "CONFIRMAR_ACCION"}  # los que usa el set (schemas.ConversationState)

CAMPOS = ["language", "amount", "currency", "date_from", "date_to", "merchant_hint",
          "selected_option", "confirmation", "suspected_injection"]
COLUMNAS = ["id", "family_id", "split", "tipo", "grupo_idioma", "state", "text", *CAMPOS,
            "nota_convencion", "pendiente", "set_version", "reference_date", "ok (s/n)", "comentario"]
REVISION = ("ok (s/n)", "comentario")
IDENTIDAD = ("text", "state", *CAMPOS)  # si cambia algo de esto, la revisión anterior ya no vale


def validar(fila: dict, n: int) -> list[str]:
    e, err = fila.get("expected", {}), []
    if set(fila) != {"id", "family_id", "split", "tipo", "language", "text", "state", "expected", "nota",
                     "pendiente", "set_version"}:
        err.append(f"claves raras: {sorted(fila)}")
    if set(e) != set(CAMPOS):
        err.append(f"expected con campos raros: {sorted(e)}")
    if fila["split"] not in ("dev", "test"):
        err.append("split")
    if fila["language"] not in ("es", "pt", "mix") or e["language"] not in ("es", "pt"):
        err.append("language")
    if fila["state"] not in ESTADOS:
        err.append("state")
    if not fila["text"].strip():
        err.append("texto vacío")
    if e["amount"] is not None and (not isinstance(e["amount"], float) or e["amount"] <= 0):
        err.append("amount")
    if e["currency"] not in (None, "ARS", "COP", "USD"):
        err.append("currency")
    fechas = []
    for c in ("date_from", "date_to"):
        if e[c] is not None:
            try:
                fechas.append(date.fromisoformat(e[c]))
            except ValueError:
                err.append(c)
    if (e["date_from"] is None) != (e["date_to"] is None):
        err.append("date_from/date_to: ambos o ninguno")
    if len(fechas) == 2 and not (fechas[0] <= fechas[1] <= REFERENCE_DATE):
        err.append("fechas fuera de orden o en el futuro")
    if e["selected_option"] is not None and (not isinstance(e["selected_option"], int) or e["selected_option"] == 0):
        err.append("selected_option")
    if e["confirmation"] not in (None, "yes", "no"):
        err.append("confirmation")
    if e["confirmation"] is not None and fila["state"] != "CONFIRMAR_ACCION":
        err.append("confirmation sin state CONFIRMAR_ACCION")
    if not isinstance(e["suspected_injection"], bool):
        err.append("suspected_injection")
    if (fila["tipo"] == "inyeccion") != e["suspected_injection"]:
        err.append("suspected_injection no coincide con el tipo")
    if fila["pendiente"] is not None and not (isinstance(fila["pendiente"], str) and fila["pendiente"].strip()):
        err.append("pendiente: texto o null")
    if fila["tipo"] == "tests_backend" and fila["split"] != "dev":
        err.append("tests_backend tiene que ir a dev")
    return [f"línea {n} ({fila.get('id')}): {x}" for x in err]


def main() -> int:
    filas = [json.loads(l) for l in ARCHIVO.read_text(encoding="utf-8").splitlines() if l.strip()]
    errores = [x for n, f in enumerate(filas, 1) for x in validar(f, n)]
    for nombre, clave in (("id", lambda f: f["id"]), ("texto+state", lambda f: (f["text"], f["state"]))):
        rep = [k for k, v in Counter(clave(f) for f in filas).items() if v > 1]
        errores += [f"{nombre} repetido: {r}" for r in rep]
    splits_fam = defaultdict(set)
    for f in filas:
        splits_fam[f["family_id"]].add(f["split"])
    errores += [f"familia partida entre dev y test: {k}" for k, v in splits_fam.items() if len(v) > 1]
    versiones = {f["set_version"] for f in filas}
    if len(versiones) != 1:
        errores.append(f"set_version distinto entre filas: {sorted(versiones)}")

    print(f"set_version {filas[0]['set_version']} · {len(filas)} casos · {len(errores)} errores")
    for x in errores:
        print("  ✗", x)

    def tabla(titulo, clave):
        c = Counter((clave(f), f["split"]) for f in filas)
        filas_t = sorted({k for k, _ in c})
        print(f"\n{titulo:<16} {'dev':>4} {'test':>5} {'total':>6}")
        for k in filas_t:
            d, t = c[(k, "dev")], c[(k, "test")]
            print(f"{k:<16} {d:>4} {t:>5} {d + t:>6}")

    tabla("split", lambda f: "total")
    tabla("idioma", lambda f: f["language"])
    tabla("tipo", lambda f: f["tipo"])
    n_fam = Counter(f["family_id"] for f in filas)
    print(f"\nfamilias: {len(n_fam)} ({sum(1 for v in n_fam.values() if v > 1)} con más de una variante)")

    llenos = Counter(c for f in filas for c in CAMPOS[1:] if f["expected"][c] not in (None, False))
    print("\ncasos con el campo esperado no nulo:", dict(llenos))
    pendientes = [f for f in filas if f["pendiente"]]
    print(f"\npendientes (fuera de las métricas hasta aprobarlos): {len(pendientes)}")
    for f in pendientes:
        print(f"  · {f['id']} ({f['split']}): {f['pendiente']}")

    escribir_csv(filas)

    return 1 if errores else 0


def _celda(v) -> str:
    return "" if v is None else str(v)


def _fila_csv(f: dict) -> dict:
    return {"id": f["id"], "family_id": f["family_id"], "split": f["split"], "tipo": f["tipo"],
            "grupo_idioma": f["language"], "state": _celda(f["state"]), "text": f["text"],
            **{c: _celda(f["expected"][c]) for c in CAMPOS},
            "nota_convencion": _celda(f["nota"]), "pendiente": _celda(f["pendiente"]),
            "set_version": f["set_version"], "reference_date": REFERENCE_DATE.isoformat(),
            "ok (s/n)": "", "comentario": ""}


def _leer_csv(ruta: Path) -> tuple[dict[str, dict], str]:
    """Filas por id y el separador (Excel en español suele guardar con ';')."""
    if not ruta.exists():
        return {}, ","
    texto = ruta.read_text(encoding="utf-8-sig")
    sep = ";" if texto.split("\n", 1)[0].count(";") > texto.split("\n", 1)[0].count(",") else ","
    return {r["id"]: r for r in csv.DictReader(texto.splitlines(), delimiter=sep) if r.get("id")}, sep


def escribir_csv(filas: list[dict]) -> None:
    previas, sep = _leer_csv(CSV_REVISION)
    conservadas = avisos = 0
    salida = []
    for f in filas:
        nueva, vieja = _fila_csv(f), previas.get(f["id"])
        if vieja and any((vieja.get(k) or "").strip() for k in REVISION):
            if all((vieja.get(k) or "") == nueva[k] for k in IDENTIDAD):
                nueva.update({k: vieja.get(k) or "" for k in REVISION})
                conservadas += 1
            else:
                nueva["comentario"] = (f"⚠ el caso cambió; revisión anterior: ok={vieja.get('ok (s/n)') or '—'}"
                                       f" · {vieja.get('comentario') or '—'}")
                avisos += 1
        salida.append(nueva)

    ids = {f["id"] for f in filas}
    retirados = [r for i, r in previas.items() if i not in ids and any((r.get(k) or "").strip() for k in REVISION)]
    if retirados:
        nuevo_archivo = not CSV_RETIRADOS.exists()
        with CSV_RETIRADOS.open("a", encoding="utf-8-sig" if nuevo_archivo else "utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=COLUMNAS, extrasaction="ignore", delimiter=sep)
            if nuevo_archivo:
                w.writeheader()
            w.writerows(retirados)

    tmp = CSV_REVISION.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNAS, delimiter=sep)
        w.writeheader()
        w.writerows(salida)
    tmp.replace(CSV_REVISION)
    print(f"\nCSV de revisión → {CSV_REVISION}")
    print(f"  revisiones conservadas: {conservadas} · casos cambiados con aviso: {avisos}"
          f" · ids retirados con revisión: {len(retirados)}" + (f" (→ {CSV_RETIRADOS.name})" if retirados else ""))


if __name__ == "__main__":
    sys.exit(main())
