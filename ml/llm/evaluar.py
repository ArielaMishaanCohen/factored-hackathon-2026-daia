"""Evaluación final de la 4.3 (Paso 8): extracción en el split test y redacción con verificador.

Uso:  python ml/llm/evaluar.py [--solo extraccion|redaccion]

1. Extracción: reglas vs. Gemini sobre el split **test** de ml/llm/extraccion_casos.jsonl, con el
   prompt y las reglas ya fijados (el test se abre una sola vez: no se ajusta nada después).
   Exactitud por campo y por idioma, tasa de fallback, latencia p50/p95, costo por 1.000 frases
   e inyección (aciertos sobre las inyecciones del test, falsos positivos sobre las frases normales).
2. Redacción: cada plantilla de app.responder.templates × es/pt × 3 juegos de facts tomados del
   gold de demo. Tasa de aprobación del verificador, motivos de rechazo, latencia y costo.

Gemini pasa por una caché en disco (ml/llm/.cache/gemini/, fuera de git) que guarda la respuesta,
la latencia real y los tokens: repetir la corrida no vuelve a llamar a la API ni cambia los números.
Cada corrida se guarda en ml/llm/runs/<fecha>_<parte>.json (parámetros, versión y md5 de los
prompts, md5 del set, commit, métricas y predicciones) y se rearma ml/llm/report.md.
La sección «Lectura» del reporte se escribe a mano: el script la conserva si ya existe.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import string
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

AQUI = Path(__file__).parent
RAIZ = AQUI.parents[1]
sys.path.insert(0, str(RAIZ / "backend"))
sys.path.insert(0, str(AQUI))

from evaluar_extraccion import CACHE_DIR, CAMPOS, CASOS, ExtractorLLM, _norm  # noqa: E402

RUNS = AQUI / "runs"
REPORTE = AQUI / "report.md"
SPLIT = "test"
MARCA_LECTURA = "## Lectura"


# --- Utilidades -----------------------------------------------------------------------------------

def md5_archivo(ruta: Path) -> str:
    return hashlib.md5(ruta.read_bytes()).hexdigest()


def git_commit() -> str:
    def git(*args):
        return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True).stdout.strip()
    commit = git("rev-parse", "HEAD") or "desconocido"
    return commit + ("-dirty" if git("status", "--porcelain") else "")


def percentil(valores: list[float], q: float) -> float:
    """Rango más cercano, igual que evaluar_extraccion.py."""
    v = sorted(valores)
    return v[min(len(v) - 1, int(q * len(v)))] if v else 0.0


def pct(a: int, t: int) -> str:
    return f"{a / t:.1%}" if t else "—"


def guardar_run(parte: str, datos: dict) -> Path:
    RUNS.mkdir(exist_ok=True)
    ruta = RUNS / f"{datetime.now():%Y%m%d-%H%M%S}_{parte}.json"
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return ruta


# --- 1. Extracción --------------------------------------------------------------------------------

def _es_inyeccion(caso) -> bool:
    return bool(caso["expected"]["suspected_injection"])


def evaluar_extraccion() -> dict:
    from app.nlu import extract_llm, rules

    casos = [json.loads(l) for l in CASOS.read_text(encoding="utf-8").splitlines()]
    casos = [c for c in casos if c["split"] == SPLIT]
    llm = ExtractorLLM()

    def correr_reglas(texto, state):
        return rules.extract(texto, state)

    res: dict = {}
    for nombre, fn in [("rules", correr_reglas), ("llm", llm)]:
        aciertos, total = defaultdict(int), defaultdict(int)
        por_idioma = defaultdict(lambda: defaultdict(lambda: [0, 0]))
        latencias, predicciones, errores = [], [], []
        for caso in casos:
            t0 = time.perf_counter()
            salida = fn(caso["text"], caso["state"])
            latencias.append((time.perf_counter() - t0) * 1000)
            mal = {c: (caso["expected"][c], _norm(c, salida.get(c))) for c in CAMPOS
                   if _norm(c, caso["expected"][c]) != _norm(c, salida.get(c))}
            predicciones.append({"id": caso["id"], "salida": {c: _norm(c, salida.get(c)) for c in CAMPOS},
                                 "errores": sorted(mal)})
            if caso["pendiente"]:
                continue
            for c in CAMPOS:
                total[c] += 1
                aciertos[c] += c not in mal
                por_idioma[caso["language"]][c][0] += c not in mal
                por_idioma[caso["language"]][c][1] += 1
            if mal:
                errores.append({"id": caso["id"], "tipo": caso["tipo"], "language": caso["language"],
                                "state": caso["state"], "text": caso["text"],
                                "mal": {c: {"esperado": e, "salio": s} for c, (e, s) in mal.items()}})
        detectado = {p["id"]: p["salida"]["suspected_injection"] for p in predicciones}
        iny = [c for c in casos if _es_inyeccion(c)]
        normales = [c for c in casos if not _es_inyeccion(c)]
        falsas = [c for c in casos if c["tipo"] == "falsa_inyeccion"]
        m = {
            "n": len(casos) - sum(bool(c["pendiente"]) for c in casos),
            "por_campo": {c: [aciertos[c], total[c]] for c in CAMPOS},
            "casos_sin_error": [total["language"] - len(errores), total["language"]],
            "por_idioma": {i: {c: v for c, v in d.items()} for i, d in sorted(por_idioma.items())},
            "inyeccion": {
                "detectadas": [sum(bool(detectado[c["id"]]) for c in iny), len(iny)],
                "falsos_positivos_normales": [sum(bool(detectado[c["id"]]) for c in normales), len(normales)],
                "falsos_positivos_falsa_inyeccion": [sum(bool(detectado[c["id"]]) for c in falsas), len(falsas)],
                "no_detectadas": [c["id"] for c in iny if not detectado[c["id"]]],
                "falsos_positivos": [c["id"] for c in normales if detectado[c["id"]]],
            },
        }
        if nombre == "rules":
            m["latencia_ms"] = {"p50": percentil(latencias, 0.5), "p95": percentil(latencias, 0.95)}
            m["fallback"] = None
            m["costo_usd"] = 0.0
        else:
            lat = llm.cache.latencias_ms
            m["latencia_ms"] = {"p50": percentil(lat, 0.5), "p95": percentil(lat, 0.95),
                                "max": max(lat) if lat else 0.0, "llamadas": len(lat),
                                "llamadas_api_en_esta_corrida": llm.cache.llamadas_api}
            m["fallback"] = {"n": len(llm.fallbacks), "de": len(casos),
                             "motivos": dict(Counter(motivo for _, motivo in llm.fallbacks))}
            m["reintentos_json"] = llm.reintentos
            m["campos_descartados"] = [{"text": t, "campos": cs} for t, cs in llm.descartados]
            m["tokens"] = {"entrada": llm.tokens_in, "salida": llm.tokens_out}
            m["costo_usd"] = llm.costo_usd
        m["costo_por_1000"] = m["costo_usd"] / max(len(casos), 1) * 1000
        res[nombre] = {"metricas": m, "errores": errores, "predicciones": predicciones}

    return {
        "parte": "extraccion", "split": SPLIT, "fecha": datetime.now().isoformat(timespec="seconds"),
        "params": {"modelo": llm.cache.cliente.modelo, "temperatura": 0.0,
                   "prompt": extract_llm.PROMPT_VERSION, "prompt_md5": md5_archivo(extract_llm.PROMPT_PATH),
                   "reglas_md5": md5_archivo(Path(rules.__file__)), "cache_dir": str(CACHE_DIR.relative_to(RAIZ))},
        "datos": {"set": str(CASOS.relative_to(RAIZ)), "set_md5": md5_archivo(CASOS),
                  "n_test": len(casos), "idiomas": dict(Counter(c["language"] for c in casos))},
        "git_commit": git_commit(),
        "resultados": res,
    }


# --- 2. Redacción ---------------------------------------------------------------------------------

def juegos_de_facts() -> list[dict]:
    """3 juegos realistas del gold de demo (data/gold/gold.duckdb), con los mismos formatos que usa
    el orquestador: amount con f"{:,.2f}", date como date, sla como ISO, status Open/Escalated."""
    from app.config import get_policy
    ref = date.fromisoformat(get_policy()["reference_date"])
    sla = get_policy()["sla_days_by_priority"]
    return [
        {   # Cliente demo 1 (México, es): Empresa Telefónica, TRX-9CHA2LRITIMEFRSAT93E
            "nombre": "demo1_usd", "amount": f"{115.02:,.2f}", "currency": "USD", "date": date(2026, 6, 16),
            "card": "•••• 3723", "case_id": "DSP-000001", "status": "Open",
            "sla": (ref + timedelta(days=sla["medium"])).isoformat(), "cases": "DSP-000001 (Open)",
        },
        {   # Cliente demo 8 (México, pt): Empresa Telefónica, TRX-50UI2GIA9765FFUU8POF
            "nombre": "demo8_usd_pt", "amount": f"{373.14:,.2f}", "currency": "USD", "date": date(2026, 6, 14),
            "card": "•••• 3804", "case_id": "DSP-000002", "status": "Escalated",
            "sla": (ref + timedelta(days=sla["high"])).isoformat(),
            "cases": "DSP-000002 (Escalated), DSP-000003 (Open)",
        },
        {   # Cliente demo 6 (Colombia, monto alto): Tienda General, TRX-0003Y34IMGRAAKKVVQHR
            "nombre": "demo6_cop_alto", "amount": f"{1952832.76:,.2f}", "currency": "COP", "date": date(2026, 5, 19),
            "card": "•••• 8469", "case_id": "DSP-000014", "status": "Escalated",
            "sla": (ref + timedelta(days=sla["critical"])).isoformat(), "cases": "DSP-000014 (Escalated)",
        },
    ]


class CacheTexto:
    """Envuelve al GeminiClient para generate_text con caché en disco (respuesta, latencia, tokens).
    La clave incluye el juego: las plantillas sin datos se redactan 3 veces (3 muestras, no 1)."""

    def __init__(self):
        from app.llm.gemini_client import get_client
        self.cliente = get_client()
        self.disponible = self.cliente.disponible
        self.juego = ""
        self.ultimo: str | None = None
        self.latencias_ms: list[float] = []
        self.llamadas_api = 0
        self.errores: list[str] = []

    def generate_text(self, prompt_sistema, texto_usuario):
        from app.llm.gemini_client import LLMUsage
        clave = hashlib.md5(f"texto\n{prompt_sistema}\n{texto_usuario}\n{self.juego}".encode()).hexdigest()
        ruta = CACHE_DIR / self.cliente.modelo / f"{clave}.json"
        if ruta.exists():
            r = json.loads(ruta.read_text(encoding="utf-8"))
            self.latencias_ms.append(r["latencia_ms"])
            self.ultimo = r["resultado"]
            return r["resultado"], LLMUsage(**{**r["uso"], "cached": True})
        self.cliente._cache.clear()  # sin la caché en memoria, cada juego es una llamada real
        t0 = time.perf_counter()
        try:
            texto, uso = self.cliente.generate_text(prompt_sistema, texto_usuario)
        except Exception as e:
            self.errores.append(str(e))
            raise
        ms = (time.perf_counter() - t0) * 1000
        self.llamadas_api += 1
        self.latencias_ms.append(ms)
        self.ultimo = texto
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps({"resultado": texto, "latencia_ms": ms, "uso": {
            "model": uso.model, "tokens_in": uso.tokens_in, "tokens_out": uso.tokens_out,
            "cost_usd": uso.cost_usd}}, ensure_ascii=False), encoding="utf-8")
        return texto, uso


def evaluar_redaccion() -> dict:
    from app.responder import compose as mod
    from app.responder import templates

    cache = CacheTexto()
    juegos = juegos_de_facts()
    filas = []
    costo = 0.0
    tokens_in = tokens_out = 0
    for clave, por_idioma in templates.TEMPLATES.items():
        campos = {f for _, f, _, _ in string.Formatter().parse(por_idioma["es"]) if f}
        for language in ("es", "pt"):
            for juego in juegos:
                facts = {k: juego[k] for k in campos}  # solo lo que la plantilla usa, como el orquestador
                base = templates.render(clave, language, **facts)
                cache.juego, cache.ultimo = juego["nombre"], None
                texto, source, uso = mod.compose(clave, language, facts, client=cache)
                if uso is not None:
                    costo += uso.cost_usd
                    tokens_in += uso.tokens_in
                    tokens_out += uso.tokens_out
                if source == "llm":
                    motivo = None
                elif cache.ultimo is None:
                    motivo = f"sin_respuesta:{cache.errores[-1] if cache.errores else 'desconocido'}"
                else:
                    motivo = mod.verificar(mod._limpiar(cache.ultimo), base, facts, language) or "error"
                filas.append({"template": clave, "language": language, "juego": juego["nombre"],
                              "con_datos": bool(campos), "base": base,
                              "gemini": mod._limpiar(cache.ultimo) if cache.ultimo is not None else None,
                              "final": texto, "source": source, "motivo": motivo})

    n = len(filas)
    aprobadas = sum(f["source"] == "llm" for f in filas)
    lat = cache.latencias_ms

    def tasa(pred):
        sel = [f for f in filas if pred(f)]
        return [sum(f["source"] == "llm" for f in sel), len(sel)]

    return {
        "parte": "redaccion", "fecha": datetime.now().isoformat(timespec="seconds"),
        "params": {"modelo": cache.cliente.modelo, "temperatura": 0.0, "prompt": mod.PROMPT_VERSION,
                   "prompt_md5": md5_archivo(RAIZ / "prompts" / f"{mod.PROMPT_VERSION}.txt"),
                   "compose_md5": md5_archivo(Path(mod.__file__)), "max_frases": mod.MAX_FRASES,
                   "max_chars": mod.MAX_CHARS},
        "datos": {"templates_md5": md5_archivo(Path(templates.__file__)), "n_plantillas": len(templates.TEMPLATES),
                  "juegos": juegos},
        "git_commit": git_commit(),
        "metricas": {
            "aprobadas": [aprobadas, n],
            "por_idioma": {lg: tasa(lambda f, lg=lg: f["language"] == lg) for lg in ("es", "pt")},
            "por_juego": {j["nombre"]: tasa(lambda f, j=j: f["juego"] == j["nombre"]) for j in juegos},
            "con_datos": tasa(lambda f: f["con_datos"]),
            "sin_datos": tasa(lambda f: not f["con_datos"]),
            "por_plantilla": {k: tasa(lambda f, k=k: f["template"] == k) for k in templates.TEMPLATES},
            "motivos_rechazo": dict(Counter(f["motivo"] for f in filas if f["motivo"])),
            "latencia_ms": {"p50": percentil(lat, 0.5), "p95": percentil(lat, 0.95),
                            "max": max(lat) if lat else 0.0, "llamadas": len(lat),
                            "llamadas_api_en_esta_corrida": cache.llamadas_api},
            "tokens": {"entrada": tokens_in, "salida": tokens_out},
            "costo_usd": costo, "costo_por_1000": costo / max(n, 1) * 1000,
        },
        "redacciones": filas,
    }


# --- Reporte --------------------------------------------------------------------------------------

def _tabla(encabezado: list[str], filas: list[list]) -> list[str]:
    out = ["| " + " | ".join(encabezado) + " |", "|" + "|".join(":--" if i == 0 else "--:" for i in range(len(encabezado))) + "|"]
    out += ["| " + " | ".join(str(x) for x in f) + " |" for f in filas]
    return out


def _md_extraccion(run: dict, archivo: str) -> list[str]:
    r, l = run["resultados"]["rules"]["metricas"], run["resultados"]["llm"]["metricas"]
    p = run["params"]
    L = [f"## 1. Extracción en el split test ({run['datos']['n_test']} frases)", "",
         f"Corrida `{archivo}` · commit `{run['git_commit'][:12]}` · set md5 `{run['datos']['set_md5']}` · "
         f"{p['modelo']} · prompt `{p['prompt']}` (md5 `{p['prompt_md5'][:8]}`) · reglas md5 `{p['reglas_md5'][:8]}`. "
         f"Idiomas: {', '.join(f'{k} {v}' for k, v in run['datos']['idiomas'].items())}.", "",
         "### Exactitud por campo", ""]
    filas = [[c, f"{r['por_campo'][c][0]}/{r['por_campo'][c][1]} ({pct(*r['por_campo'][c])})",
              f"{l['por_campo'][c][0]}/{l['por_campo'][c][1]} ({pct(*l['por_campo'][c])})"] for c in CAMPOS]
    filas.append(["**frases sin ningún error**", f"{r['casos_sin_error'][0]}/{r['casos_sin_error'][1]} ({pct(*r['casos_sin_error'])})",
                  f"{l['casos_sin_error'][0]}/{l['casos_sin_error'][1]} ({pct(*l['casos_sin_error'])})"])
    L += _tabla(["campo", "reglas", "Gemini"], filas) + ["", "### Exactitud por idioma (todos los campos juntos)", ""]
    filas = []
    for idioma in r["por_idioma"]:
        def tot(m):
            a = sum(v[0] for v in m["por_idioma"][idioma].values())
            t = sum(v[1] for v in m["por_idioma"][idioma].values())
            return f"{a}/{t} ({pct(a, t)})"
        filas.append([idioma, tot(r), tot(l)])
    L += _tabla(["idioma", "reglas", "Gemini"], filas)
    L += ["", "Por idioma y campo (reglas / Gemini):", ""]
    filas = [[c] + [f"{pct(*r['por_idioma'][i][c])} / {pct(*l['por_idioma'][i][c])}" for i in r["por_idioma"]] for c in CAMPOS]
    L += _tabla(["campo"] + list(r["por_idioma"]), filas)

    ir, il = r["inyeccion"], l["inyeccion"]
    L += ["", "### Inyección", "",
          *_tabla(["", "reglas", "Gemini"], [
              ["inyecciones detectadas", f"{ir['detectadas'][0]}/{ir['detectadas'][1]}", f"{il['detectadas'][0]}/{il['detectadas'][1]}"],
              ["falsos positivos en frases normales", f"{ir['falsos_positivos_normales'][0]}/{ir['falsos_positivos_normales'][1]}",
               f"{il['falsos_positivos_normales'][0]}/{il['falsos_positivos_normales'][1]}"],
              ["… de ellas, «falsas inyecciones»", f"{ir['falsos_positivos_falsa_inyeccion'][0]}/{ir['falsos_positivos_falsa_inyeccion'][1]}",
               f"{il['falsos_positivos_falsa_inyeccion'][0]}/{il['falsos_positivos_falsa_inyeccion'][1]}"],
              ["no detectadas", ", ".join(ir["no_detectadas"]) or "—", ", ".join(il["no_detectadas"]) or "—"],
              ["falsos positivos", ", ".join(ir["falsos_positivos"]) or "—", ", ".join(il["falsos_positivos"]) or "—"],
          ])]
    lat = l["latencia_ms"]
    fb = l["fallback"]
    L += ["", "### Latencia, fallback y costo", "",
          *_tabla(["", "reglas", "Gemini"], [
              ["latencia p50", f"{r['latencia_ms']['p50']:.2f} ms", f"{lat['p50']:.0f} ms"],
              ["latencia p95", f"{r['latencia_ms']['p95']:.2f} ms", f"{lat['p95']:.0f} ms (máx {lat['max']:.0f})"],
              ["fallback a reglas (JSON inválido o error de API)", "—",
               f"{fb['n']}/{fb['de']} ({pct(fb['n'], fb['de'])})" + (f" · {fb['motivos']}" if fb["motivos"] else "")],
              ["reintentos por JSON inválido", "—", str(l["reintentos_json"])],
              ["tokens entrada / salida", "—", f"{l['tokens']['entrada']} / {l['tokens']['salida']}"],
              ["costo por 1.000 frases", "USD 0", f"USD {l['costo_por_1000']:.2f}"],
          ]),
          "", f"La latencia de Gemini es por llamada, medida en la llamada real a la API ({lat['llamadas']} llamadas; "
              "las repeticiones de la corrida salen de la caché en disco con la latencia original)."]
    if l["campos_descartados"]:
        L += ["", "Campos que la validación Pydantic descartó: " +
              "; ".join(f"{d['campos']} en {d['text']!r}" for d in l["campos_descartados"])]
    for nombre, titulo in [("rules", "reglas"), ("llm", "Gemini")]:
        errs = run["resultados"][nombre]["errores"]
        L += ["", f"### Errores de {titulo} ({len(errs)} frases)", ""]
        if not errs:
            L.append("Ninguno.")
            continue
        filas = [[e["id"], e["language"], e["state"] or "—", e["text"].replace("|", "\\|"),
                  "; ".join(f"`{c}` esperado {v['esperado']!r}, salió {v['salio']!r}" for c, v in e["mal"].items())]
                 for e in errs]
        L += _tabla(["id", "idioma", "state", "frase", "campos"], filas)
    return L


def _md_redaccion(run: dict, archivo: str) -> list[str]:
    m, p = run["metricas"], run["params"]
    fs = run["redacciones"]
    L = [f"## 2. Redacción con verificador ({m['aprobadas'][1]} redacciones)", "",
         f"Corrida `{archivo}` · commit `{run['git_commit'][:12]}` · {p['modelo']} · prompt `{p['prompt']}` "
         f"(md5 `{p['prompt_md5'][:8]}`) · compose md5 `{p['compose_md5'][:8]}`. "
         f"{run['datos']['n_plantillas']} plantillas × es/pt × 3 juegos de facts del gold de demo "
         f"({', '.join(j['nombre'] for j in run['datos']['juegos'])}). Las plantillas sin datos reciben el mismo "
         "texto en los 3 juegos: son 3 muestras de la misma entrada.", "",
         *_tabla(["", "aprobadas por el verificador"], [
             ["**total**", f"**{m['aprobadas'][0]}/{m['aprobadas'][1]} ({pct(*m['aprobadas'])})**"],
             *[[f"idioma {k}", f"{v[0]}/{v[1]} ({pct(*v)})"] for k, v in m["por_idioma"].items()],
             *[[f"juego {k}", f"{v[0]}/{v[1]} ({pct(*v)})"] for k, v in m["por_juego"].items()],
             ["plantillas con datos", f"{m['con_datos'][0]}/{m['con_datos'][1]} ({pct(*m['con_datos'])})"],
             ["plantillas sin datos", f"{m['sin_datos'][0]}/{m['sin_datos'][1]} ({pct(*m['sin_datos'])})"],
         ]),
         "", "### Motivos de rechazo", "",
         *(_tabla(["motivo", "veces"], sorted(([k, v] for k, v in m["motivos_rechazo"].items()), key=lambda x: -x[1]))
           if m["motivos_rechazo"] else ["Ninguno."]),
         "", "### Por plantilla", "",
         *_tabla(["plantilla", "aprobadas"], [[k, f"{v[0]}/{v[1]}"] for k, v in m["por_plantilla"].items()]),
         "", "### Latencia y costo", "",
         *_tabla(["", "Gemini"], [
             ["latencia p50", f"{m['latencia_ms']['p50']:.0f} ms"],
             ["latencia p95", f"{m['latencia_ms']['p95']:.0f} ms (máx {m['latencia_ms']['max']:.0f})"],
             ["tokens entrada / salida", f"{m['tokens']['entrada']} / {m['tokens']['salida']}"],
             ["costo por 1.000 redacciones", f"USD {m['costo_por_1000']:.2f}"],
         ])]
    ok = [f for f in fs if f["source"] == "llm"]
    # 5 aprobadas variadas: plantillas con datos distintas, rotando idioma y juego
    combos = [(lg, j["nombre"]) for j in run["datos"]["juegos"] for lg in ("es", "pt")]
    muestra = []
    for clave in dict.fromkeys(f["template"] for f in ok if f["con_datos"]):
        lg, juego = combos[len(muestra) % len(combos)]
        elegida = next((f for f in ok if (f["template"], f["language"], f["juego"]) == (clave, lg, juego)), None)
        if elegida and len(muestra) < 5:
            muestra.append(elegida)
    L += ["", "### 5 redacciones aprobadas", ""]
    L += _tabla(["plantilla · idioma · juego", "plantilla renderizada", "Gemini (aprobada)"],
                [[f"{f['template']} · {f['language']} · {f['juego']}", f["base"], f["final"]] for f in muestra])
    rech = [f for f in fs if f["source"] != "llm"]
    L += ["", f"### Todas las rechazadas ({len(rech)})", ""]
    if rech:
        L += _tabla(["plantilla · idioma · juego", "motivo", "plantilla renderizada (lo que se envía)", "texto de Gemini (descartado)"],
                    [[f"{f['template']} · {f['language']} · {f['juego']}", f"`{f['motivo']}`", f["base"],
                      f["gemini"] or "—"] for f in rech])
    else:
        L.append("Ninguna.")
    return L


def escribir_reporte(ext: tuple[dict, str] | None, red: tuple[dict, str] | None) -> None:
    lectura = None
    if REPORTE.exists():
        previo = REPORTE.read_text(encoding="utf-8")
        if MARCA_LECTURA in previo:
            lectura = previo[previo.index(MARCA_LECTURA):].rstrip() + "\n"
    ultimo = sorted(RUNS.glob("*_extraccion.json")), sorted(RUNS.glob("*_redaccion.json"))
    if ext is None and ultimo[0]:
        ext = (json.loads(ultimo[0][-1].read_text(encoding="utf-8")), ultimo[0][-1].name)
    if red is None and ultimo[1]:
        red = (json.loads(ultimo[1][-1].read_text(encoding="utf-8")), ultimo[1][-1].name)
    L = ["# Reporte 4.3 · Extracción y redacción con Gemini", "",
         "Generado por `ml/llm/evaluar.py` a partir de las corridas en `ml/llm/runs/`. "
         "El split test se abrió una sola vez, con el prompt y las reglas ya fijados; no se cambiaron después. "
         "La sección «Lectura» se escribe a mano y el script la conserva.", ""]
    if ext:
        L += _md_extraccion(*ext) + [""]
    if red:
        L += _md_redaccion(*red) + [""]
    L.append(lectura or f"{MARCA_LECTURA}\n\n_Pendiente._\n")
    REPORTE.write_text("\n".join(L), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo", choices=["extraccion", "redaccion"])
    args = ap.parse_args()
    ext = red = None
    if args.solo in (None, "extraccion"):
        run = evaluar_extraccion()
        ext = (run, guardar_run("extraccion", run).name)
        for n in ("rules", "llm"):
            m = run["resultados"][n]["metricas"]
            print(f"{n:<6} " + " · ".join(f"{c} {pct(*m['por_campo'][c])}" for c in CAMPOS)
                  + f" · inyección {m['inyeccion']['detectadas']} FP {m['inyeccion']['falsos_positivos_normales']}")
    if args.solo in (None, "redaccion"):
        run = evaluar_redaccion()
        red = (run, guardar_run("redaccion", run).name)
        m = run["metricas"]
        print(f"redacción: aprobadas {m['aprobadas']} · motivos {m['motivos_rechazo']} · "
              f"p50 {m['latencia_ms']['p50']:.0f} ms · USD {m['costo_por_1000']:.2f}/1.000")
    escribir_reporte(ext, red)
    print(f"Reporte: {REPORTE.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
