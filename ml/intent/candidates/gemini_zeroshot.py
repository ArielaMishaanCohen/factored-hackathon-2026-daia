"""Candidato 4 (Paso 7 de la guía 4.2): Gemini zero-shot, referencia de "solo LLM".

Prompt: prompts/intent_zeroshot_v1.txt (definiciones + reglas de labeling_guide.md v1.4) como
instrucción de sistema; la frase va aparte, como dato. Salida JSON {"intent", "confidence"},
donde intent puede ser también "ambiguo" (= abstenerse).

- Modelo: GEMINI_MODEL de .env (D1.11), temperatura 0, JSON con esquema y validado a mano.
- 1 reintento si la API falla o el JSON no es válido. Si el segundo intento también falla,
  la frase cuenta como error (fila en 0 = SIN_RESPUESTA en evaluate.metricas): no se salta.
- Control de ritmo para la capa gratuita: como mucho `rpm` llamadas por minuto. Un 429 por
  minuto espera lo que pide la API y no gasta el reintento; un 429 por día corta la corrida
  (lo ya respondido queda en caché y la próxima corrida sigue desde ahí).
- Caché en disco, fuera de git (ml/intent/.cache/gemini/): una respuesta por modelo + prompt +
  frase. Guarda tokens y latencia de la llamada original, así una corrida desde caché reporta
  el mismo costo y la misma latencia. Los errores no se guardan: se reintentan en la próxima.
- Latencia: solo el tiempo de la API (incluye el reintento), sin las esperas del control de ritmo.

    .venv/bin/python -m ml.intent.candidates.gemini_zeroshot              # val completo
    .venv/bin/python -m ml.intent.candidates.gemini_zeroshot --muestra 200  # muestra estratificada

Usar este main y no `evaluate --candidato gemini_zeroshot`: evaluate.evaluar cronometra
predict_proba entero, con las esperas del control de ritmo y los aciertos de caché.
"""

import argparse
import hashlib
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from ml.intent.evaluate import AMBIGUO, CLASES, INTENT_DIR, elegir_tau, guardar_run, load_split, metricas

ROOT = INTENT_DIR.parent.parent
PROMPTS_DIR = ROOT / "prompts"
CACHE_DIR = INTENT_DIR / ".cache" / "gemini"
SEED = 42
SALIDAS = CLASES + [AMBIGUO]
TEMPERATURA = 0.0
TIMEOUT_MS = 60_000
ESPERA_REINTENTO_S = 5
MAX_ESPERAS_429 = 6

# USD por 1M de tokens, capa pagada. Los tokens de razonamiento se cobran como salida.
PRECIOS = {
    "gemini-3.5-flash": {"entrada": 1.50, "salida": 9.00},
    "gemini-3.8-flash": {"entrada": 0.75, "salida": 3.75},  # hasta el 31-dic-2026; después 1,50 y 7,50
}
PRECIO_FUENTE = "ai.google.dev/gemini-api/docs/pricing, consultado el 29-sep-2026 (docs/decisions.md, D1.11 y D1.12)"

ESQUEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": SALIDAS},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["intent", "confidence"],
}


class CuotaDiariaAgotada(RuntimeError):
    pass


class RespuestaInvalida(ValueError):
    pass


def validar(texto: str) -> dict:
    try:
        d = json.loads(texto)
    except (json.JSONDecodeError, TypeError) as e:
        raise RespuestaInvalida(f"JSON inválido: {texto!r}") from e
    if not isinstance(d, dict) or d.get("intent") not in SALIDAS:
        raise RespuestaInvalida(f"intent inválido: {texto!r}")
    c = d.get("confidence")
    if isinstance(c, bool) or not isinstance(c, (int, float)) or not 0 <= c <= 1:
        raise RespuestaInvalida(f"confidence inválida: {texto!r}")
    return {"intent": d["intent"], "confidence": float(c)}


def _espera_429(e: errors.APIError) -> float:
    """Segundos que pide la API (RetryInfo.retryDelay); 60 si no lo dice."""
    m = re.search(r"retryDelay['\"]?\s*:\s*['\"]?(\d+(?:\.\d+)?)s", str(e.details))
    return float(m.group(1)) + 1 if m else 60.0


class GeminiZeroShot:
    def __init__(self, prompt: str = "intent_zeroshot_v1", rpm: float = 10):
        load_dotenv(ROOT / ".env")
        self.modelo = os.environ.get("GEMINI_MODEL", "").strip()
        clave = os.environ.get("GEMINI_API_KEY", "").strip()
        if not self.modelo or not clave:
            raise RuntimeError("Faltan GEMINI_MODEL o GEMINI_API_KEY en .env")
        if self.modelo not in PRECIOS:
            raise RuntimeError(f"Sin precio para {self.modelo!r}: agrégalo a PRECIOS con su fuente")
        self.prompt, self.rpm = prompt, rpm
        self.instruccion = (PROMPTS_DIR / f"{prompt}.txt").read_text(encoding="utf-8")
        self.prompt_md5 = hashlib.md5(self.instruccion.encode()).hexdigest()
        # attempts=1: el SDK no reintenta solo; los reintentos los controla esta clase.
        self.client = genai.Client(api_key=clave, http_options=types.HttpOptions(
            timeout=TIMEOUT_MS, retry_options=types.HttpRetryOptions(attempts=1)))
        self.config = types.GenerateContentConfig(
            system_instruction=self.instruccion, temperature=TEMPERATURA,
            response_mime_type="application/json", response_json_schema=ESQUEMA)
        self.registro: list[dict] = []  # una entrada por frase clasificada
        self._ultima_llamada = 0.0

    # --- Interfaz común ---

    def fit(self, textos, labels):
        return self  # zero-shot: no entrena

    def predict_proba(self, textos):
        """Columna de la intención = confidence. `ambiguo` o error → fila en 0 (sin respuesta)."""
        probs = np.zeros((len(textos), len(CLASES)))
        for i, texto in enumerate(textos):
            r = self.clasificar(texto)
            if r["intent"] in CLASES:
                probs[i, CLASES.index(r["intent"])] = max(r["confidence"], 1e-6)
        return probs

    @property
    def costo_por_1000_usd(self) -> float:
        costos = [r["costo_usd"] for r in self.registro]
        return 1000 * float(np.mean(costos)) if costos else 0.0

    # --- Llamadas ---

    def _ruta_cache(self, texto: str) -> Path:
        clave = hashlib.md5(f"{self.modelo}\n{self.prompt_md5}\n{TEMPERATURA}\n{texto}".encode()).hexdigest()
        return CACHE_DIR / self.modelo / f"{clave}.json"

    def _costo(self, tokens: dict) -> float:
        p = PRECIOS[self.modelo]
        return (tokens["entrada"] * p["entrada"] + (tokens["salida"] + tokens["razonamiento"]) * p["salida"]) / 1e6

    def _llamar(self, texto: str):
        """Una llamada a la API, con control de ritmo. Devuelve (respuesta, segundos de API)."""
        for _ in range(MAX_ESPERAS_429 + 1):
            espera = self._ultima_llamada + 60 / self.rpm - time.monotonic()
            if espera > 0:
                time.sleep(espera)
            self._ultima_llamada = time.monotonic()
            t0 = time.perf_counter()
            try:
                resp = self.client.models.generate_content(
                    model=self.modelo, contents=f"<frase>\n{texto}\n</frase>", config=self.config)
                return resp, time.perf_counter() - t0
            except errors.ClientError as e:
                if e.code != 429:
                    raise
                if "PerDay" in str(e.details):
                    raise CuotaDiariaAgotada(str(e)) from e
                s = _espera_429(e)
                print(f"    429 por minuto: espero {s:.0f} s", flush=True)
                time.sleep(s)
        raise RuntimeError(f"429 persistente tras {MAX_ESPERAS_429} esperas")

    def clasificar(self, texto: str) -> dict:
        ruta = self._ruta_cache(texto)
        if ruta.exists():
            r = {**json.loads(ruta.read_text()), "desde_cache": True}
            self.registro.append(r)
            return r

        tokens = {"entrada": 0, "salida": 0, "razonamiento": 0}
        latencia_s, fallos = 0.0, []
        for intento in (1, 2):  # 1 reintento
            try:
                resp, s = self._llamar(texto)
                latencia_s += s
                u = resp.usage_metadata
                if u is not None:
                    tokens["entrada"] += u.prompt_token_count or 0
                    tokens["salida"] += u.candidates_token_count or 0
                    tokens["razonamiento"] += u.thoughts_token_count or 0
                salida = validar(resp.text)
                r = {"texto": texto, **salida, "crudo": resp.text, "tokens": tokens,
                     "costo_usd": self._costo(tokens), "latencia_ms": latencia_s * 1000,
                     "intentos": intento, "modelo": self.modelo, "prompt": self.prompt,
                     "fecha": datetime.now().isoformat(timespec="seconds")}
                ruta.parent.mkdir(parents=True, exist_ok=True)
                ruta.write_text(json.dumps(r, ensure_ascii=False))
                r = {**r, "desde_cache": False}
                self.registro.append(r)
                return r
            except CuotaDiariaAgotada:
                raise
            except (errors.APIError, RespuestaInvalida, RuntimeError, OSError) as e:
                fallos.append(f"{type(e).__name__}: {str(e)[:300]}")
                if intento == 1:
                    time.sleep(ESPERA_REINTENTO_S)
        r = {"texto": texto, "intent": None, "confidence": 0.0, "error": " | ".join(fallos), "tokens": tokens,
             "costo_usd": self._costo(tokens), "latencia_ms": None, "intentos": 2, "desde_cache": False}
        self.registro.append(r)
        return r


def crear(**params):
    return GeminiZeroShot(**params)


# --- Evaluación en val (Paso 7) ----------------------------------------------------


def muestra_estratificada(df, n: int):
    """n frases de val, proporcionales por (label, language), con SEED fija."""
    grupos = df.groupby(["label", "language"], group_keys=False)
    return (grupos.apply(lambda g: g.sample(max(1, round(n * len(g) / len(df))), random_state=SEED))
            .sort_values("id").reset_index(drop=True))


def _resumen_gemini(cand: GeminiZeroShot, df) -> dict:
    reg = cand.registro
    ok = [r for r in reg if r["intent"] is not None]
    lat = [r["latencia_ms"] for r in ok]
    tok = {k: int(sum(r["tokens"][k] for r in reg)) for k in ("entrada", "salida", "razonamiento")}
    return {
        "modelo": cand.modelo, "prompt": f"prompts/{cand.prompt}.txt", "prompt_md5": cand.prompt_md5,
        "temperatura": TEMPERATURA, "rpm": cand.rpm, "reintentos": 1,
        "precio_usd_por_1M": {**PRECIOS[cand.modelo], "fuente": PRECIO_FUENTE,
                              "nota": "capa pagada; en la capa gratuita el costo real es 0"},
        "tokens_total": tok,
        "tokens_media_por_frase": {k: v / len(reg) for k, v in tok.items()},
        "costo_total_usd": float(sum(r["costo_usd"] for r in reg)),
        "latencia_ms_p95": float(np.percentile(lat, 95)) if lat else None,
        "n_errores": len(reg) - len(ok),
        "errores": [{"id": i, "error": r["error"]} for i, r in zip(df["id"], reg) if r["intent"] is None],
        "n_pred_ambiguo": sum(r["intent"] == AMBIGUO for r in reg),
        "n_con_reintento": sum(r["intentos"] > 1 for r in reg),
        "n_desde_cache": sum(r["desde_cache"] for r in reg),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rpm", type=float, default=10, help="llamadas por minuto (capa gratuita)")
    ap.add_argument("--prompt", default="intent_zeroshot_v1")
    ap.add_argument("--muestra", type=int, help="evalúa una muestra estratificada de val (se declara en el run)")
    a = ap.parse_args(argv)

    df = load_split("val")
    n_val = len(df)
    if a.muestra:
        df = muestra_estratificada(df, a.muestra)
    cand = crear(prompt=a.prompt, rpm=a.rpm)
    print(f"{cand.modelo} · {len(df)} frases de val · {a.rpm:g} rpm", flush=True)

    filas = []
    for i, texto in enumerate(df["text"], 1):
        filas.append(cand.predict_proba([texto])[0])
        if i % 25 == 0 or i == len(df):
            r = cand.registro
            print(f"  {i}/{len(df)} · errores {sum(x['intent'] is None for x in r)} · "
                  f"caché {sum(x['desde_cache'] for x in r)}", flush=True)

    res = metricas(df, np.vstack(filas))
    lat = [r["latencia_ms"] for r in cand.registro if r["intent"] is not None]
    res["latencia_ms_p50"] = float(np.median(lat)) if lat else None
    res["costo_por_1000_usd"] = cand.costo_por_1000_usd
    res["gemini"] = _resumen_gemini(cand, df)
    res["tau"] = elegir_tau(res["curva_cobertura_precision"])
    preds, conf = res.pop("_preds"), res.pop("_conf")
    res["predicciones"] = [
        {"id": i, "label": l, "pred": p, "conf": round(float(c), 4),
         "gemini": r["intent"] if r["intent"] is not None else "ERROR"}
        for i, l, p, c, r in zip(df["id"], df["label"], preds, conf, cand.registro)
    ]

    params = {"modelo": cand.modelo, "prompt": a.prompt, "temperatura": TEMPERATURA}
    datos = {"zero_shot": True, "train_n": 0, "val_n_total": n_val,
             "muestra": {"n": len(df), "estratificada_por": ["label", "language"], "seed": SEED}
             if a.muestra else None}
    ruta = guardar_run("gemini_zeroshot", "val", params, res, datos)

    g, t = res["gemini"], res["tau"]
    print(f"\nmacro-F1 {res['macro_f1']:.3f} · "
          + " · ".join(f"{k} {v['macro_f1']:.3f}" for k, v in res["por_idioma"].items()))
    print(f"τ={t['tau']:.2f}: cobertura {t['cobertura']:.1%} · precisión {t['precision'] or 0:.1%} · "
          f"ambiguo abstenidas {t['ambiguo_abstenidas'] or 0:.1%} ({t['regla']})")
    print(f"errores API {g['n_errores']} · dijo ambiguo {g['n_pred_ambiguo']} · con reintento {g['n_con_reintento']}")
    print(f"latencia p50 {res['latencia_ms_p50'] or 0:.0f} ms · p95 {g['latencia_ms_p95'] or 0:.0f} ms")
    print(f"tokens/frase: entrada {g['tokens_media_por_frase']['entrada']:.0f} · salida "
          f"{g['tokens_media_por_frase']['salida']:.0f} · razonamiento {g['tokens_media_por_frase']['razonamiento']:.0f}")
    print(f"costo USD {g['costo_total_usd']:.4f} total · {res['costo_por_1000_usd']:.3f} por 1.000 frases")
    print(f"run: {ruta.relative_to(ROOT)}")


if __name__ == "__main__":
    try:
        main()
    except CuotaDiariaAgotada as e:
        raise SystemExit(f"Cuota diaria agotada; lo respondido quedó en caché. Sigue mañana o con --muestra.\n{e}")
