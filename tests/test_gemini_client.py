"""Cliente de Gemini (backend/app/llm/gemini_client.py) con un cliente falso: sin red."""
import logging
from dataclasses import replace
from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors

from app.config import get_settings
from app.llm.gemini_client import PRECIOS, GeminiClient, LLMUnavailable, LLMUsage

MODELO = "gemini-3.8-flash"
ESQUEMA = {"type": "object", "properties": {"amount": {"type": "number"}}, "required": ["amount"]}
TEXTO = "No reconozco un cargo de 350 en Oxxo"


def _resp(texto, entrada=100, salida=10, razonamiento=5):
    uso = SimpleNamespace(prompt_token_count=entrada, candidates_token_count=salida, thoughts_token_count=razonamiento)
    return SimpleNamespace(text=texto, usage_metadata=uso)


def _error(code, status, detalle=""):
    cls = errors.ServerError if code >= 500 else errors.ClientError
    return cls(code, {"error": {"code": code, "status": status, "message": detalle}})


class FakeGenAI:
    """Imita client.models.generate_content: cada llamada consume la siguiente salida."""

    def __init__(self, *salidas):
        self.salidas = list(salidas)
        self.llamadas = []
        self.models = self

    def generate_content(self, model, contents, config):
        self.llamadas.append({"model": model, "contents": contents, "config": config})
        s = self.salidas.pop(0)
        if isinstance(s, Exception):
            raise s
        return s


def _cliente(fake, clave="clave-falsa"):
    s = replace(get_settings(), gemini_model=MODELO, gemini_api_key=clave)
    esperas = []
    return GeminiClient(settings=s, client=fake, sleep=esperas.append), esperas


def test_respuesta_valida_json():
    fake = FakeGenAI(_resp('{"amount": 350}'))
    c, esperas = _cliente(fake)
    r, uso = c.generate_json("extrae", TEXTO, ESQUEMA)
    assert r == {"amount": 350}
    p = PRECIOS[MODELO]
    assert uso == LLMUsage(MODELO, 100, 15, (100 * p["entrada"] + 15 * p["salida"]) / 1e6)
    assert esperas == []
    cfg = fake.llamadas[0]["config"]
    assert cfg.temperature == 0
    assert cfg.response_mime_type == "application/json" and cfg.response_json_schema == ESQUEMA
    assert cfg.thinking_config.thinking_level == "LOW"


def test_generate_text():
    c, _ = _cliente(FakeGenAI(_resp("Tu caso es DSP-000001.")))
    texto, uso = c.generate_text("redacta", "hechos")
    assert texto == "Tu caso es DSP-000001." and uso.tokens_out == 15


def test_503_y_luego_exito():
    fake = FakeGenAI(_error(503, "UNAVAILABLE"), _resp('{"amount": 350}'))
    c, esperas = _cliente(fake)
    r, uso = c.generate_json("extrae", TEXTO, ESQUEMA)
    assert r == {"amount": 350} and uso.tokens_in == 100
    assert len(fake.llamadas) == 2 and len(esperas) == 1


def test_timeout_agotado():
    fake = FakeGenAI(*[httpx.ReadTimeout("timeout")] * 3)
    c, esperas = _cliente(fake)
    with pytest.raises(LLMUnavailable):
        c.generate_json("extrae", TEXTO, ESQUEMA)
    assert len(fake.llamadas) == 3  # 1 + 2 reintentos
    assert len(esperas) == 2 and esperas[0] < esperas[1]  # backoff creciente


def test_no_transitorio_no_reintenta():
    fake = FakeGenAI(_error(429, "RESOURCE_EXHAUSTED", "GenerateRequestsPerDayPerProjectPerModel"))
    c, _ = _cliente(fake)
    with pytest.raises(LLMUnavailable):
        c.generate_json("extrae", TEXTO, ESQUEMA)
    assert len(fake.llamadas) == 1


def test_json_invalido():
    c, _ = _cliente(FakeGenAI(_resp("no es json")))
    with pytest.raises(LLMUnavailable):
        c.generate_json("extrae", TEXTO, ESQUEMA)


def test_sin_llave():
    s = replace(get_settings(), gemini_model=MODELO, gemini_api_key=None)
    c = GeminiClient(settings=s)
    assert not c.disponible
    with pytest.raises(LLMUnavailable):
        c.generate_json("extrae", TEXTO, ESQUEMA)


def test_acierto_de_cache():
    fake = FakeGenAI(_resp('{"amount": 350}'))
    c, _ = _cliente(fake)
    r1, u1 = c.generate_json("extrae", TEXTO, ESQUEMA)
    r1["amount"] = 999  # mutar lo devuelto no ensucia la caché
    r2, u2 = c.generate_json("extrae", TEXTO, ESQUEMA)
    assert r2 == {"amount": 350}
    assert len(fake.llamadas) == 1
    assert u1.cost_usd > 0 and not u1.cached
    assert u2 == LLMUsage(MODELO, 0, 0, 0.0, cached=True)


def test_cache_distingue_prompt_y_texto():
    fake = FakeGenAI(*[_resp('{"amount": 1}')] * 3)
    c, _ = _cliente(fake)
    c.generate_json("extrae", TEXTO, ESQUEMA)
    c.generate_json("extrae v2", TEXTO, ESQUEMA)
    c.generate_json("extrae", TEXTO + " ayer", ESQUEMA)
    assert len(fake.llamadas) == 3


def test_log_sin_texto_del_cliente(caplog):
    fake = FakeGenAI(_error(503, "UNAVAILABLE", TEXTO), _resp('{"amount": 350}'))
    c, _ = _cliente(fake)
    with caplog.at_level(logging.DEBUG, logger="latam.llm"):
        c.generate_json("extrae", TEXTO, ESQUEMA)
        c.generate_json("extrae", TEXTO, ESQUEMA)
    assert caplog.records
    assert all("Oxxo" not in r.getMessage() for r in caplog.records)
