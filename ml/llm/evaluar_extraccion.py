"""Exactitud por campo de un extractor sobre ml/llm/extraccion_casos.jsonl.

Uso:  python ml/llm/evaluar_extraccion.py --extractor rules|llm [--split dev]

Con --extractor llm llama a Gemini (app.nlu.extract_llm) con caché en disco en ml/llm/.cache/gemini/
(fuera de git): una respuesta por modelo + md5 del prompt, el esquema y el texto enviado. La latencia
que se reporta es la de la llamada real, guardada en la caché. Si Gemini falla en un caso, cuenta
como fallback y ese caso se puntúa con las reglas (lo mismo que hará understand()).

Solo se ajusta mirando dev. El test se abre una sola vez (Paso 8 de la guía de la 4.3).
Los casos con `pendiente` no cuentan en las métricas: se listan aparte.
Compara merchant_hint sin mayúsculas ni tildes, y los montos con tolerancia de 0,005.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path

AQUI = Path(__file__).parent
RAIZ = AQUI.parents[1]
sys.path.insert(0, str(RAIZ / "backend"))

CASOS = AQUI / "extraccion_casos.jsonl"
CACHE_DIR = AQUI / ".cache" / "gemini"
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


class CacheDisco:
    """Envuelve al GeminiClient del backend con una caché en disco y mide la latencia real."""

    def __init__(self):
        from app.llm.gemini_client import get_client
        self.cliente = get_client()
        self.latencias_ms: list[float] = []  # una por llamada (la de la llamada original si vino de caché)
        self.llamadas_api = 0

    def generate_json(self, prompt_sistema, texto_usuario, esquema):
        from app.llm.gemini_client import LLMUsage
        clave = hashlib.md5(f"{prompt_sistema}\n{json.dumps(esquema, sort_keys=True)}\n{texto_usuario}"
                            .encode()).hexdigest()
        ruta = CACHE_DIR / self.cliente.modelo / f"{clave}.json"
        if ruta.exists():
            r = json.loads(ruta.read_text(encoding="utf-8"))
            self.latencias_ms.append(r["latencia_ms"])
            return r["resultado"], LLMUsage(**{**r["uso"], "cached": True})
        t0 = time.perf_counter()
        resultado, uso = self.cliente.generate_json(prompt_sistema, texto_usuario, esquema)
        ms = (time.perf_counter() - t0) * 1000
        self.llamadas_api += 1
        self.latencias_ms.append(ms)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps({"resultado": resultado, "latencia_ms": ms, "uso": {
            "model": uso.model, "tokens_in": uso.tokens_in, "tokens_out": uso.tokens_out,
            "cost_usd": uso.cost_usd}}, ensure_ascii=False), encoding="utf-8")
        return resultado, uso


class ExtractorLLM:
    def __init__(self):
        from app.nlu import extract_llm, rules
        self.extract_llm, self.rules = extract_llm, rules
        self.cache = CacheDisco()
        self.fallbacks: list[tuple[str, str]] = []  # (texto, motivo)
        self.reintentos = 0
        self.descartados: list[tuple[str, list[str]]] = []
        self.costo_usd = 0.0
        self.tokens_in = self.tokens_out = 0

    def __call__(self, texto, state):
        from app.llm.gemini_client import LLMUnavailable
        try:
            d = self.extract_llm.extract_con_detalle(texto, state, client=self.cache)
        except LLMUnavailable as e:
            self.fallbacks.append((texto, str(e)))
            return self.rules.extract(texto, state)
        self.reintentos += d.intentos - 1
        if d.descartados:
            self.descartados.append((texto, d.descartados))
        self.costo_usd += d.uso.cost_usd
        self.tokens_in += d.uso.tokens_in
        self.tokens_out += d.uso.tokens_out
        return d.campos

    def resumen(self, n: int) -> str:
        lat = sorted(self.cache.latencias_ms)
        p = lambda q: lat[min(len(lat) - 1, int(q * len(lat)))] if lat else 0.0  # noqa: E731
        lineas = [
            f"Prompt: {self.extract_llm.PROMPT_VERSION} · modelo: {self.cache.cliente.modelo}",
            f"Llamadas: {len(lat)} ({self.cache.llamadas_api} a la API, el resto de la caché en disco)",
            f"Latencia por llamada: p50 {statistics.median(lat) if lat else 0:.0f} ms · p95 {p(0.95):.0f} ms"
            f" · máx {max(lat) if lat else 0:.0f} ms",
            f"Fallback a reglas: {len(self.fallbacks)}/{n} · reintentos por JSON inválido: {self.reintentos}",
            f"Tokens (con los de la caché): entrada {self.tokens_in} · salida {self.tokens_out}"
            f" · costo USD {self.costo_usd:.4f} ({self.costo_usd / max(n, 1) * 1000:.2f} por 1.000 frases)",
        ]
        for texto, motivo in self.fallbacks:
            lineas.append(f"  fallback: {motivo} · {texto!r}")
        for texto, campos in self.descartados:
            lineas.append(f"  campos descartados {campos} · {texto!r}")
        return "\n".join(lineas)


def cargar_extractor(nombre: str):
    if nombre == "rules":
        from app.nlu import rules
        return lambda texto, state: rules.extract(texto, state)
    if nombre == "llm":
        return ExtractorLLM()
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
    extractor = cargar_extractor(args.extractor)
    metricas, errores, pendientes = evaluar(extractor, args.split)

    print(f"Extractor: {args.extractor} · split: {args.split}\n")
    print(f"{'campo':<22}{'aciertos':>10}{'exactitud':>11}")
    for c, (a, t) in metricas.items():
        print(f"{c:<22}{f'{a}/{t}':>10}{(a / t if t else 0):>10.1%}")
    print(f"\nErrores ({len(errores)} casos):")
    for caso, mal in errores:
        detalle = " · ".join(f"{c}: esperado {e!r}, salió {s!r}" for c, (e, s) in mal.items())
        print(f"  {caso['id']:<6} [{caso['state'] or '-'}] {caso['text']!r}\n         {detalle}")
    if hasattr(extractor, "resumen"):
        print("\n" + extractor.resumen(metricas["language"][1] + len(pendientes)))
    if pendientes:
        print(f"\nPendientes (no cuentan): {len(pendientes)}")
        for caso, mal in pendientes:
            print(f"  {caso['id']:<6} {caso['text']!r} → {'OK' if not mal else mal}")


if __name__ == "__main__":
    main()
