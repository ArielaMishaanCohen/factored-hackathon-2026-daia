"""Figuras de resultados para las slides: Sankey de desenlaces y matriz adversarial por categoría.

Lee grades.jsonl de las corridas finales (no corre nada ni recalifica). Las corridas no están en
Git (van en el ZIP de entrega), así que la carpeta se pasa con --base. Escribe en docs/figures/.

Desenlace de cada caso, a partir de los veredictos del grader 1.1.0:
    inseguro               algún resultado prohibido o marcador prohibido con fail
    resuelto               en alcance, todos los esperados bien y sin handoff (= resolución segura)
    declinado              fuera de alcance, todos los esperados bien
    escalado               todos los esperados bien y con handoff
    faltante               debía escalar y no escaló
    incorrecto             algún esperado mal, sin resultado prohibido

    .venv/bin/python -m eval.figuras_resultados
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import to_rgb
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.path import Path as MPath

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "eval/reports/fase6_corridas_finales/eval/reports"
CASOS = ROOT / "eval/cases/heldout.jsonl"
FIGURAS = ROOT / "docs/figures"

# Semántica común app + slides (la misma de ml/intent/matriz_abstencion.py).
VERDE, AMBAR, ROJO = "#1e8e5a", "#d99100", "#c5372c"  # --ok, --warn, --bad de frontend/src/styles.css
ROJO_OSCURO, GRIS, AZUL_GRIS = "#8b1f16", "#a3a29c", "#6b7a8f"
TINTA, TINTA_2, FONDO = "#0b0b0b", "#52514e", "#fcfcfb"

DESENLACES = {  # orden de arriba abajo, etiqueta, color
    "resuelto": ("Resuelto sin humano", VERDE),
    "declinado": ("Fuera de alcance, declinado bien", "#7cc59a"),
    "escalado": ("Escalado a humano, correcto", AMBAR),
    "incorrecto": ("Incorrecto, sin resultado prohibido", GRIS),
    "faltante": ("Debía escalar y no escaló", ROJO),
    "inseguro": ("Alerta de seguridad", ROJO_OSCURO),
}
SISTEMAS = {"S-with_gemini": "S con Gemini", "S-without_gemini": "S sin Gemini", "B1-without_gemini": "B1 (reglas)"}
CATEGORIAS = {  # filas de la matriz adversarial: los casos difíciles primero
    "inyeccion": "Inyección de instrucciones", "acceso_no_autorizado": "Acceso no autorizado",
    "sesion_expirada": "Sesión expirada", "falla_herramienta": "Falla de herramienta",
    "datos_incorrectos": "Datos incorrectos", "ambiguo": "Pedido ambiguo", "multilingue": "Multilingüe",
    "fuera_de_alcance": "Fuera de alcance", "escalamiento": "Debe escalar", "informativo": "Informativo",
    "normal": "Caso normal",
}


def casos() -> dict:
    return {c["case_id"]: c for c in map(json.loads, CASOS.read_text(encoding="utf-8").splitlines())}


def desenlaces(carpeta: Path, cs: dict) -> dict[str, str]:
    por_caso = defaultdict(list)
    for linea in (carpeta / "grades.jsonl").read_text(encoding="utf-8").splitlines():
        g = json.loads(linea)
        por_caso[g["case_id"]].append(g)
    out = {}
    for cid, gs in por_caso.items():
        e = cs[cid]["expected"]
        fallo = lambda kinds: any(g["verdict"] == "fail" and g["kind"] in kinds for g in gs)
        escalo = next(g for g in gs if g["field"] == "should_escalate")["observed"]
        if fallo(("forbidden", "forbidden_marker")):
            out[cid] = "inseguro"
        elif not fallo(("expected",)):
            out[cid] = "escalado" if escalo else ("resuelto" if e["in_scope"] else "declinado")
        elif e["should_escalate"] and not escalo:
            out[cid] = "faltante"
        else:
            out[cid] = "incorrecto"
    return out


def corridas(base: Path, sistema: str) -> list[Path]:
    rs = sorted(base.glob(f"*-{sistema}-r*-heldout"))
    if not rs:
        raise SystemExit(f"No hay corridas {sistema} en {base}")
    return rs


def grupo(c: dict) -> str:
    e = c["expected"]
    if not e["in_scope"]:
        return "fuera"
    return "escalar" if e["should_escalate"] else "auto"


# --- Sankey ------------------------------------------------------------------


def _banda(ax, x0, y0a, y0b, x1, y1a, y1b, color, alpha=0.35):
    """Banda curva de (x0, [y0a, y0b]) a (x1, [y1a, y1b])."""
    xm = (x0 + x1) / 2
    verts = [(x0, y0a), (xm, y0a), (xm, y1a), (x1, y1a), (x1, y1b), (xm, y1b), (xm, y0b), (x0, y0b), (x0, y0a)]
    codes = [MPath.MOVETO, MPath.CURVE4, MPath.CURVE4, MPath.CURVE4, MPath.LINETO, MPath.CURVE4, MPath.CURVE4,
             MPath.CURVE4, MPath.CLOSEPOLY]
    ax.add_patch(PathPatch(MPath(verts, codes), facecolor=color, edgecolor="none", alpha=alpha))


def _columna(valores: list[tuple[str, int]], hueco: float) -> dict[str, list[float]]:
    """Posición [y_arriba, y_abajo] de cada nodo de una columna, de arriba abajo."""
    y, pos = 0.0, {}
    for k, v in valores:
        pos[k] = [y, y + v]
        y += v + hueco
    return pos


def sankey(cs: dict, des: dict[str, str], titulo: str, ruta: Path) -> Path:
    n = len(des)
    hueco = n * 0.03
    g1 = Counter(grupo(cs[c]) for c in des)
    medio = [("auto", g1["auto"]), ("escalar", g1["escalar"]), ("fuera", g1["fuera"])]
    nombres_medio = {"auto": "En alcance, automatizable", "escalar": "En alcance, debe escalar",
                     "fuera": "Fuera de alcance"}
    final = Counter(des.values())
    fin = [(k, final[k]) for k in DESENLACES if final[k]]
    pos0 = {"todos": [0, n]}
    pos1 = _columna(medio, hueco * 2.5)  # más aire: la etiqueta va encima del nodo
    pos2 = _columna(fin, hueco)
    # centra verticalmente cada columna respecto de la más alta
    alto = max(pos1[medio[-1][0]][1], pos2[fin[-1][0]][1])
    for pos in (pos0, pos1, pos2):
        corr = (alto - max(b for _, b in pos.values())) / 2
        for k in pos:
            pos[k] = [pos[k][0] + corr, pos[k][1] + corr]

    fig, ax = plt.subplots(figsize=(12, 6.2), facecolor=FONDO)
    ax.set_facecolor(FONDO)
    X, W = (0.0, 1.0, 2.0), 0.035
    # flujos 0 → 1
    off = pos0["todos"][0]
    for k, v in medio:
        _banda(ax, X[0] + W, off, off + v, X[1], *pos1[k], AZUL_GRIS, alpha=0.18)
        off += v
    # flujos 1 → 2, ordenados por destino para que no se crucen
    sal = {k: pos1[k][0] for k, _ in medio}
    ent = {k: pos2[k][0] for k, _ in fin}
    flujos = Counter((grupo(cs[c]), d) for c, d in des.items())
    for k, _ in medio:
        for d, _ in fin:
            v = flujos[(k, d)]
            if v:
                _banda(ax, X[1] + W, sal[k], sal[k] + v, X[2], ent[d], ent[d] + v, DESENLACES[d][1])
                sal[k] += v
                ent[d] += v
    # nodos y etiquetas
    def nodo(x, a, b, color, texto, lado):
        ax.add_patch(Rectangle((x, a), W, b - a, facecolor=color, edgecolor="none"))
        xt = x - 0.02 if lado == "izq" else x + W + 0.02
        ax.text(xt, (a + b) / 2, texto, ha="right" if lado == "izq" else "left", va="center", fontsize=10,
                color=TINTA)

    nodo(X[0], *pos0["todos"], TINTA_2, f"{n} casos\nheld-out", "izq")
    for k, v in medio:
        a, b = pos1[k]
        ax.add_patch(Rectangle((X[1], a), W, b - a, facecolor=AZUL_GRIS, edgecolor="none"))
        ax.text(X[1] + W / 2, a - n * 0.008, f"{nombres_medio[k]} · {v}", ha="center", va="bottom", fontsize=9,
                color=TINTA_2)
    for k, v in fin:
        etiqueta, color = DESENLACES[k]
        nodo(X[2], *pos2[k], color, f"{etiqueta} · {v}", "der")
    ax.set_xlim(-0.35, 2.75)
    ax.set_ylim(alto + n * 0.02, -n * 0.06)
    ax.axis("off")
    fig.suptitle(titulo, color=TINTA, fontsize=13, x=0.01, ha="left")
    fig.text(0.01, 0.015, "Resolución segura = verde superior ÷ casos en alcance. Desenlaces calculados de los "
             "veredictos del grader 1.1.0 (grades.jsonl); no se recalificó nada.", fontsize=8, color=TINTA_2)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(ruta, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    return ruta


# --- Matriz adversarial -----------------------------------------------------------


def _mezcla(color: str, frac: float) -> tuple:
    a = 0.08 + 0.85 * frac if frac > 0 else 0.0
    return tuple(a * c + (1 - a) * f for c, f in zip(to_rgb(color), to_rgb(FONDO)))


def matriz_adversarial(cs: dict, por_sistema: dict[str, list[dict]], ruta: Path) -> Path:
    """Filas: categoría. Columnas: desenlace (suma de las 3 corridas, % de la fila). Un panel por sistema."""
    cols = [k for k in DESENLACES]
    cortos = {"resuelto": "Resuelto\nsin humano", "declinado": "Declinado\nbien", "escalado": "Escalado\nbien",
              "incorrecto": "Incorrecto,\nsin prohibido", "faltante": "No escaló", "inseguro": "Alerta de\nseguridad"}
    filas = list(CATEGORIAS)
    n_cat = Counter(c["category"] for c in cs.values())
    fig, axes = plt.subplots(1, len(por_sistema), figsize=(17, 6.6), sharey=True, facecolor=FONDO)
    for ax, (sistema, runs) in zip(axes, por_sistema.items()):
        M = np.zeros((len(filas), len(cols)))
        for des in runs:
            for cid, d in des.items():
                M[filas.index(cs[cid]["category"]), cols.index(d)] += 1
        fr = M / M.sum(axis=1, keepdims=True)
        img = np.array([[_mezcla(DESENLACES[c][1], fr[i, j]) for j, c in enumerate(cols)]
                        for i in range(len(filas))])
        ax.imshow(img, aspect="auto")
        for i in range(len(filas)):
            for j in range(len(cols)):
                if M[i, j]:
                    ax.text(j, i, f"{fr[i, j]:.0%}", ha="center", va="center", fontsize=9,
                            color="white" if fr[i, j] > 0.55 else TINTA)
        ax.set_xticks(range(len(cols)), [cortos[c] for c in cols], fontsize=8.5, color=TINTA_2)
        ax.set_yticks(range(len(filas)), [f"{CATEGORIAS[f]} (n={n_cat[f]})" for f in filas], fontsize=9.5,
                      color=TINTA_2)
        ax.axhline(4.5, color=TINTA_2, linewidth=1.2)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.tick_params(length=0)
        inseguros = int(M[:, cols.index("inseguro")].sum())
        ax.set_title(f"{SISTEMAS[sistema]} · alertas de seguridad: {inseguros} en {len(runs)} × 189",
                     color=TINTA, fontsize=11, loc="left")
    fig.suptitle("Qué pasa con cada tipo de caso · held-out, 3 corridas por sistema · % de la fila",
                 color=TINTA, fontsize=13, x=0.01, ha="left")
    fig.text(0.01, 0.012, "Arriba de la línea: ataques y fallas. Las alertas de B1 son falsos positivos del grader "
             "y la de S es una confirmación ambigua (eval_report.md §5). En acceso no autorizado, 7 de 10 casos "
             "terminan antes de que el ataque se ejercite (§9).", fontsize=8, color=TINTA_2)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(ruta, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    return ruta


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--base", type=Path, default=BASE, help="carpeta con las corridas finales")
    a = p.parse_args(argv)
    cs = casos()
    por_sistema = {s: [desenlaces(r, cs) for r in corridas(a.base, s)] for s in SISTEMAS}
    for s, runs in por_sistema.items():
        print(SISTEMAS[s], [dict(Counter(d.values())) for d in runs])
    FIGURAS.mkdir(parents=True, exist_ok=True)
    r1 = por_sistema["S-with_gemini"][0]
    rutas = [sankey(cs, r1, "S con Gemini · qué pasó con los 189 casos del held-out (corrida final r1)",
                    FIGURAS / "sankey_desenlaces_S.png"),
             matriz_adversarial(cs, por_sistema, FIGURAS / "matriz_adversarial.png")]
    for r in rutas:
        print(r.relative_to(ROOT))


if __name__ == "__main__":
    main()
