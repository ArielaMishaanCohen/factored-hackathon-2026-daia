"""Cliente de Gemini del backend (integracion_backend.md §1.5).

Una sola forma de llamar a Gemini para extraer (generate_json) y redactar (generate_text):

- Modelo y llave desde app.config.get_settings() (GEMINI_MODEL, GEMINI_API_KEY).
- Timeout de 8 s por llamada; hasta 2 reintentos con backoff, solo en errores transitorios
  (503/504, 429 por minuto, timeout o conexión). Un 429 por día o un 4xx no se reintentan.
- Temperatura 0 y razonamiento al mínimo que acepta gemini-3.8-flash (thinking_level=LOW) para
  bajar la latencia. MINIMAL da 400 "not supported for this model" (probado el 29-sep-2026).
- Caché LRU en memoria por modelo + md5 del prompt + esquema + texto. Un acierto devuelve
  LLMUsage con tokens y costo en 0 (no se llamó a la API).
- Sin llave, o si se agotan los reintentos, lanza LLMUnavailable. Lo atrapan understand y
  compose (que caen a reglas o plantilla), no el orquestador.
- El log nunca lleva el texto del cliente ni el prompt: solo modelo, intento, código y tokens.
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable

import httpx
from google import genai
from google.genai import errors, types

from app.config import Settings, get_settings

log = logging.getLogger("latam.llm")

TIMEOUT_S = 8
# El SDK manda el timeout también como X-Server-Timeout, y la API rechaza < 10 s con un 400
# ("Minimum allowed deadline is 10s"). Se fija aparte: el cliente corta a los 8 s igual.
SERVER_TIMEOUT_S = 10
MAX_REINTENTOS = 2
BACKOFF_S = (0.5, 1.5)  # espera antes del reintento 1 y del 2
TEMPERATURA = 0.0
CACHE_MAX = 512
CODIGOS_TRANSITORIOS = {503, 504}

# USD por 1M de tokens, capa pagada. Los tokens de razonamiento se cobran como salida.
# Fuente: ai.google.dev/gemini-api/docs/pricing, consultado el 29-sep-2026 (docs/decisions.md, D1.12).
# Copia de PRECIOS en ml/intent/candidates/gemini_zeroshot.py: si cambia uno, cambia el otro.
PRECIOS = {
    "gemini-3.5-flash": {"entrada": 1.50, "salida": 9.00},
    "gemini-3.8-flash": {"entrada": 0.75, "salida": 3.75},  # hasta el 31-dic-2026; después 1,50 y 7,50
}


class LLMUnavailable(RuntimeError):
    """Gemini no está disponible para esta llamada: sin llave, error no transitorio,
    reintentos agotados o respuesta que no es JSON válido."""


@dataclass
class LLMUsage:
    model: str
    tokens_in: int
    tokens_out: int     # salida + razonamiento (se cobran igual)
    cost_usd: float     # con PRECIOS de arriba; 0 si el modelo no tiene precio anotado
    cached: bool = False


def costo_usd(modelo: str, tokens_in: int, tokens_out: int) -> float:
    p = PRECIOS.get(modelo)
    if p is None:
        return 0.0
    return (tokens_in * p["entrada"] + tokens_out * p["salida"]) / 1e6


def _es_transitorio(e: Exception) -> bool:
    if isinstance(e, (httpx.TimeoutException, httpx.ConnectError)):
        return True
    if isinstance(e, errors.APIError):
        if e.code in CODIGOS_TRANSITORIOS:
            return True
        # 429 por minuto sí; 429 por día (cuota agotada) no se arregla reintentando.
        return e.code == 429 and "PerDay" not in str(e.details)
    return False


def _describir(e: Exception) -> str:
    """Descripción del error sin cuerpo de la respuesta (podría traer eco del texto)."""
    if isinstance(e, errors.APIError):
        return f"{e.code} {e.status}"
    return type(e).__name__


class GeminiClient:
    def __init__(self, settings: Settings | None = None, client: Any = None,
                 sleep: Callable[[float], None] = time.sleep):
        s = settings or get_settings()
        self.modelo = s.gemini_model
        self._clave = s.gemini_api_key
        self._client = client  # inyectable en tests; si no, se crea al primer uso
        self._sleep = sleep
        self._cache: OrderedDict[str, Any] = OrderedDict()
        if self.modelo not in PRECIOS:
            log.warning("gemini: sin precio para el modelo %r; cost_usd saldrá en 0", self.modelo)

    @property
    def disponible(self) -> bool:
        return bool(self._clave) or self._client is not None

    def _api(self):
        if self._client is None:
            if not self._clave:
                raise LLMUnavailable("GEMINI_API_KEY vacía")
            # attempts=1: el SDK no reintenta solo; los reintentos los controla esta clase.
            self._client = genai.Client(api_key=self._clave, http_options=types.HttpOptions(
                timeout=TIMEOUT_S * 1000, headers={"X-Server-Timeout": str(SERVER_TIMEOUT_S)},
                retry_options=types.HttpRetryOptions(attempts=1)))
        return self._client

    # --- API pública ---

    def generate_json(self, prompt_sistema: str, texto_usuario: str, esquema: dict) -> tuple[dict, LLMUsage]:
        crudo, uso = self._generar(prompt_sistema, texto_usuario, esquema)
        if uso.cached:
            return crudo, uso
        try:
            resultado = json.loads(crudo)
        except (json.JSONDecodeError, TypeError) as e:
            raise LLMUnavailable("respuesta que no es JSON válido") from e
        self._guardar(self._clave_cache(prompt_sistema, texto_usuario, esquema), resultado)
        return copy.deepcopy(resultado), uso

    def generate_text(self, prompt_sistema: str, texto_usuario: str) -> tuple[str, LLMUsage]:
        texto, uso = self._generar(prompt_sistema, texto_usuario, None)
        if not uso.cached:
            if not texto or not texto.strip():
                raise LLMUnavailable("respuesta vacía")
            self._guardar(self._clave_cache(prompt_sistema, texto_usuario, None), texto)
        return texto, uso

    # --- Caché ---

    def _clave_cache(self, prompt_sistema: str, texto_usuario: str, esquema: dict | None) -> str:
        prompt_md5 = hashlib.md5(prompt_sistema.encode()).hexdigest()
        esq = json.dumps(esquema, sort_keys=True) if esquema is not None else "texto"
        return hashlib.md5(f"{self.modelo}\n{prompt_md5}\n{esq}\n{texto_usuario}".encode()).hexdigest()

    def _guardar(self, clave: str, valor: Any) -> None:
        self._cache[clave] = copy.deepcopy(valor)
        self._cache.move_to_end(clave)
        while len(self._cache) > CACHE_MAX:
            self._cache.popitem(last=False)

    # --- Llamada con reintentos ---

    def _generar(self, prompt_sistema: str, texto_usuario: str, esquema: dict | None) -> tuple[Any, LLMUsage]:
        clave = self._clave_cache(prompt_sistema, texto_usuario, esquema)
        if clave in self._cache:
            self._cache.move_to_end(clave)
            log.info("gemini: acierto de caché (modelo=%s)", self.modelo)
            return copy.deepcopy(self._cache[clave]), LLMUsage(self.modelo, 0, 0, 0.0, cached=True)

        api = self._api()
        config = types.GenerateContentConfig(
            system_instruction=prompt_sistema, temperature=TEMPERATURA,
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW))
        if esquema is not None:
            config.response_mime_type = "application/json"
            config.response_json_schema = esquema

        for intento in range(MAX_REINTENTOS + 1):
            t0 = time.perf_counter()
            try:
                resp = api.models.generate_content(model=self.modelo, contents=texto_usuario, config=config)
            except Exception as e:  # noqa: BLE001 — cualquier fallo del SDK termina en LLMUnavailable
                ms = (time.perf_counter() - t0) * 1000
                transitorio = _es_transitorio(e)
                log.warning("gemini: intento %d falló (%s, %.0f ms, transitorio=%s)",
                            intento + 1, _describir(e), ms, transitorio)
                if not transitorio:
                    raise LLMUnavailable(f"error no transitorio: {_describir(e)}") from e
                if intento == MAX_REINTENTOS:
                    raise LLMUnavailable(f"reintentos agotados: {_describir(e)}") from e
                self._sleep(BACKOFF_S[intento])
                continue

            u = resp.usage_metadata
            tokens_in = (u.prompt_token_count or 0) if u else 0
            tokens_out = ((u.candidates_token_count or 0) + (u.thoughts_token_count or 0)) if u else 0
            uso = LLMUsage(self.modelo, tokens_in, tokens_out, costo_usd(self.modelo, tokens_in, tokens_out))
            log.info("gemini: ok (modelo=%s, intento=%d, %.0f ms, in=%d, out=%d)",
                     self.modelo, intento + 1, (time.perf_counter() - t0) * 1000, tokens_in, tokens_out)
            return resp.text, uso
        raise AssertionError("inalcanzable")


_cliente: GeminiClient | None = None


def get_client() -> GeminiClient:
    """Cliente compartido del proceso (la caché vive aquí)."""
    global _cliente
    if _cliente is None:
        _cliente = GeminiClient()
    return _cliente


def generate_json(prompt_sistema: str, texto_usuario: str, esquema: dict) -> tuple[dict, LLMUsage]:
    return get_client().generate_json(prompt_sistema, texto_usuario, esquema)


def generate_text(prompt_sistema: str, texto_usuario: str) -> tuple[str, LLMUsage]:
    return get_client().generate_text(prompt_sistema, texto_usuario)
