"""Valida eval/cases/dev.jsonl y eval/cases/heldout.jsonl (Fase 6.1, Paso 7).

Se corre cada vez que se toca un caso. Lee los JSONL ya construidos (no mensajes.jsonl) y falla
(exit 1) si:
1. Una línea no cumple schema.py, o su split no es el del archivo.
2. Un case_id se repite.
3. Una transacción (meta, sembrada en setup.open_cases o elegida en el guion) o un mensaje está en
   los dos splits.
4. expected.transaction_id no existe en el gold, o no es del customer_id del caso (en
   acceso_no_autorizado tiene que ser de OTRO cliente).
5. expected.rule_id no coincide con esperado.py (con la intención de provenance y los casos de
   setup.open_cases). Sin transacción esperada, rule_id tiene que ser None.
6. Una categoría del held-out queda por debajo del mínimo del roadmap (§6.1) y no está anotada, con
   ese mismo n, en la tabla «Categorías por debajo del mínimo» de inventario.md.
7. Un mensaje del guion se parece > 0,9 (TF-IDF, mismo cálculo que verificar_mensajes.py) a una
   frase de ml/intent/ o de ml/llm/.

Uso: python -m eval.cases.validar_casos
"""
from __future__ import annotations

import csv
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from pydantic import ValidationError

from eval.cases.esperado import CasoPrevio, esperado, transaccion_gold
from eval.cases.schema import Case
from eval.cases.verificar_mensajes import UMBRAL_SIM, frases_referencia, similitud_max

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "eval" / "cases"
ARCHIVOS = {"dev": DIR / "dev.jsonl", "heldout": DIR / "heldout.jsonl"}
INVENTARIO = DIR / "inventario.md"

# Mínimo por categoría del held-out (docs/roadmap_fases_1_a_8.md §6.1).
MINIMOS = {"normal": 40, "ambiguo": 25, "fuera_de_alcance": 15, "escalamiento": 30, "informativo": 20,
           "inyeccion": 15, "acceso_no_autorizado": 10, "sesion_expirada": 5, "falla_herramienta": 10,
           "datos_incorrectos": 10, "multilingue": 10}
# Cómo se puede llamar cada categoría en inventario.md (normalizado: minúsculas, sin tildes).
ALIAS = {"normal": {"normal"}, "ambiguo": {"ambiguo"}, "fuera_de_alcance": {"fuera de alcance"},
         "escalamiento": {"escalamiento"}, "informativo": {"informativo"},
         "inyeccion": {"inyeccion", "prompt injection"}, "acceso_no_autorizado": {"acceso no autorizado"},
         "sesion_expirada": {"sesion expirada"}, "falla_herramienta": {"falla de herramienta"},
         "datos_incorrectos": {"datos incorrectos"}, "multilingue": {"multilingue"}}


def _norm(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower().strip()) if unicodedata.category(c) != "Mn")


# --- Carga -------------------------------------------------------------------------------------------

def cargar(archivos: dict[str, Path]) -> tuple[list[Case], list[str]]:
    casos, errores = [], []
    for split, ruta in archivos.items():
        for n, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
            if not linea.strip():
                continue
            try:
                c = Case.model_validate_json(linea)
            except ValidationError as e:
                errores.append(f"{ruta.name}:{n}: no cumple schema.py: {e.errors()[0]['msg']}")
                continue
            if c.split != split:
                errores.append(f"{c.case_id}: split={c.split} pero está en {ruta.name}")
            casos.append(c)
    return casos, errores


# --- Comprobaciones ----------------------------------------------------------------------------------

def ids_repetidos(casos: list[Case]) -> list[str]:
    return [f"case_id repetido: {i} ({n} veces)" for i, n in Counter(c.case_id for c in casos).items() if n > 1]


def cruces_entre_splits(casos: list[Case]) -> list[str]:
    tx_split: dict[str, set] = defaultdict(set)
    msg_split: dict[str, set] = defaultdict(set)
    for c in casos:
        ids = {c.expected.transaction_id} | {s.transaction_id for s in c.setup.open_cases}
        ids |= {t.transaction_id for t in c.script if t.kind == "ui_action"}
        for t in ids - {None}:
            tx_split[t].add(c.split)
        for t in c.script:
            if t.kind == "message":
                msg_split[_norm(t.text)].add(c.split)
    return ([f"transacción {t} en dev y held-out" for t, s in sorted(tx_split.items()) if len(s) > 1]
            + [f"mensaje en dev y held-out: {m!r}" for m, s in sorted(msg_split.items()) if len(s) > 1])


def transacciones_y_reglas(casos: list[Case]) -> list[str]:
    errores = []
    for c in casos:
        e = c.expected
        if e.transaction_id is None:
            if e.rule_id is not None:
                errores.append(f"{c.case_id}: rule_id={e.rule_id} sin transacción esperada")
            continue
        tx = transaccion_gold(e.transaction_id)
        if tx is None:
            errores.append(f"{c.case_id}: {e.transaction_id} no existe en el gold")
            continue
        if c.category == "acceso_no_autorizado":
            if tx["customer_id"] == c.customer_id:
                errores.append(f"{c.case_id}: {e.transaction_id} es del mismo cliente; tiene que ser de otro")
        elif tx["customer_id"] != c.customer_id:
            errores.append(f"{c.case_id}: {e.transaction_id} es de {tx['customer_id']}, no de {c.customer_id}")
            continue

        q = c.provenance.gold_query
        intencion = (q.params.get("intencion") if q else None) or "cargo_no_reconocido"
        previos = [CasoPrevio(s.transaction_id, s.status) for s in c.setup.open_cases]
        regla = esperado(c.customer_id, e.transaction_id, str(intencion), casos_previos=previos).rule_id
        if regla != e.rule_id:
            errores.append(f"{c.case_id}: rule_id={e.rule_id}, esperado.py da {regla}")
    return errores


def anotadas_en_inventario(texto: str) -> dict[str, int]:
    """Categoría → n anotado en la tabla «Categorías por debajo del mínimo» de inventario.md.

    Una fila puede juntar varias: «Ambiguo · inyección · … | 23 · 14 · …» se empareja por posición."""
    m = re.search(r"^#+\s*Categor[ií]as por debajo del m[ií]nimo\s*$(.*?)(?=^#)", texto, re.M | re.S)
    if not m:
        return {}
    por_alias = {a: cat for cat, alias in ALIAS.items() for a in alias}
    out = {}
    for linea in m.group(1).splitlines():
        celdas = [x.strip() for x in linea.strip().strip("|").split("|")]
        if len(celdas) < 2 or not celdas[1] or set(celdas[1]) <= set(":- "):
            continue
        nombres = [_norm(x) for x in celdas[0].split("·")]
        numeros = re.findall(r"\d+", celdas[1].split("(")[0])
        if len(nombres) != len(numeros):
            continue
        for nombre, n in zip(nombres, numeros):
            if nombre in por_alias:
                out[por_alias[nombre]] = int(n)
    return out


def minimos(casos: list[Case], inventario: Path) -> tuple[list[str], list[str]]:
    anotadas = anotadas_en_inventario(inventario.read_text(encoding="utf-8"))
    n = Counter(c.category for c in casos if c.split == "heldout")
    errores, avisos = [], []
    for cat, minimo in MINIMOS.items():
        if n[cat] >= minimo:
            continue
        if cat not in anotadas:
            errores.append(f"held-out {cat}: {n[cat]} casos < mínimo {minimo} y no está anotada en inventario.md")
        elif anotadas[cat] != n[cat]:
            errores.append(f"held-out {cat}: {n[cat]} casos, pero inventario.md anota {anotadas[cat]}")
        else:
            avisos.append(f"held-out {cat}: {n[cat]} < {minimo} (anotada en inventario.md)")
    return errores, avisos


def referencias() -> list[str]:
    """Frases de ml/intent/ y ml/llm/: las de verificar_mensajes.py más la columna text de los CSV de ml/llm/."""
    textos = set(frases_referencia())
    for f in (ROOT / "ml" / "llm").glob("*.csv"):
        with f.open(encoding="utf-8-sig") as fh:
            textos.update(fila["text"] for fila in csv.DictReader(fh) if fila.get("text"))
    return sorted(t for t in textos if t.strip())


def similitud(casos: list[Case], refs: list[str]) -> tuple[list[str], float]:
    textos = [(c.case_id, i, t.text) for c in casos for i, t in enumerate(c.script) if t.kind == "message"]
    sims = similitud_max([t for _, _, t in textos], refs)
    errores = [f"{cid} msg {i}: similitud {s:.2f} con {ref!r}"
               for (cid, i, _), (s, ref) in zip(textos, sims) if s > UMBRAL_SIM]
    return errores, max((s for s, _ in sims), default=0.0)


# --- Principal ---------------------------------------------------------------------------------------

def validar(archivos: dict[str, Path] = ARCHIVOS, inventario: Path = INVENTARIO,
            refs: list[str] | None = None) -> tuple[list[str], list[str], list[Case]]:
    casos, errores = cargar(archivos)
    errores += ids_repetidos(casos)
    errores += cruces_entre_splits(casos)
    errores += transacciones_y_reglas(casos)
    e_min, avisos = minimos(casos, inventario)
    errores += e_min
    refs = referencias() if refs is None else refs
    e_sim, sim_max = similitud(casos, refs)
    errores += e_sim
    avisos.append(f"similitud máx. {sim_max:.3f} (umbral {UMBRAL_SIM}) contra {len(refs)} frases")
    return errores, avisos, casos


def main() -> int:
    errores, avisos, casos = validar()
    for split in ARCHIVOS:
        sub = [c for c in casos if c.split == split]
        print(f"{split}: {len(sub)} casos · {dict(Counter(c.category for c in sub))}")
    for a in avisos:
        print("AVISO:", a)
    for e in errores:
        print("ERROR:", e)
    print(f"\n{len(errores)} errores")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
