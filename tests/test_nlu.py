"""understand() integrado (integracion_backend.md §1.1 y §1.8): clasificador + Gemini + reglas.

Sin red: conftest.py vacía GEMINI_API_KEY; los casos con Gemini usan un cliente falso.
"""
import pytest

import app.nlu as nlu
from app.llm import gemini_client
from app.llm.gemini_client import LLMUnavailable, LLMUsage
from app.nlu import classifier, extract_llm
from app.schemas import NLUResult

DISPUTAS = {"cargo_no_reconocido", "cobro_incorrecto"}
USO = LLMUsage("gemini-3.8-flash", 1000, 50, 0.001)
VACIO = {"language": "es", "amount": None, "currency": None, "date_from": None, "date_to": None,
         "merchant_hint": None, "selected_option": None, "confirmation": None, "suspected_injection": False}


class FakeCliente:
    def __init__(self, salida):
        self.salida = salida

    def generate_json(self, prompt_sistema, texto_usuario, esquema):
        if isinstance(self.salida, Exception):
            raise self.salida
        return self.salida, USO


@pytest.fixture
def gemini(monkeypatch):
    """gemini(salida): understand() usa un Gemini falso que devuelve esa salida (o lanza esa excepción)."""
    def usar(salida):
        monkeypatch.setattr(gemini_client, "get_client", lambda: FakeCliente(salida))
    return usar


# §1.2 Montos
@pytest.mark.parametrize("texto,esperado", [
    ("de 350 en Oxxo", 350.0),
    ("3.500", 3500.0),
    ("350,50", 350.5),
    ("350.50", 350.5),
    ("1.200.000", 1200000.0),
    ("$350", 350.0),
    ("R$ 350", 350.0),
    ("USD 350", 350.0),
    ("120 mil", 120000.0),
    ("hola", None),
])
def test_montos_1_2(texto, esperado):
    assert nlu.understand(texto).amount == esperado


# §1.4 Frases que ya usan los tests del backend
@pytest.mark.parametrize("texto,intents,idioma,monto,comercio", [
    ("No reconozco un cargo de 350 en Oxxo", {"cargo_no_reconocido"}, "es", 350.0, "Oxxo"),
    ("Não reconheço uma compra de 3.500", DISPUTAS, "pt", 3500.0, None),
    ("Não reconheço uma cobrança de 350", DISPUTAS, "pt", 350.0, None),
    ("Me cobraron dos veces 120000", {"cobro_incorrecto"}, "es", 120000.0, None),
    ("No reconozco un cargo de 777", DISPUTAS, "es", 777.0, None),
])
def test_frases_1_4(texto, intents, idioma, monto, comercio):
    r = nlu.understand(texto)
    assert r.intent in intents and not r.abstain
    assert (r.language, r.amount, r.merchant_hint) == (idioma, monto, comercio)


def test_fuera_de_alcance_sin_abstencion():
    # §1.4 pide esto con "Quiero un préstamo", pero con el clasificador de la 4.2 esa frase se abstiene
    # (conf 0,48; "préstamo" no está en train/val). Pendiente de hablar con Alina; ver test_api_contract.
    r = nlu.understand("Cómo cambio mi PIN")
    assert r.intent == "fuera_de_alcance" and r.abstain is False


def test_prestamo_se_abstiene_con_el_clasificador_actual():
    assert nlu.understand("Quiero un préstamo").abstain is True


@pytest.mark.parametrize("texto", ["hola", "mmm", "no sé"])
def test_abstiene_1_4(texto):
    assert nlu.understand(texto).abstain is True


# §1.3 Confirmaciones
def test_frase_nueva_en_confirmar_accion_no_es_un_no():
    assert nlu.understand("No reconozco otro cargo", "CONFIRMAR_ACCION").confirmation is None


def test_confirmacion_corta():
    assert nlu.understand("sí", "CONFIRMAR_ACCION").confirmation == "yes"
    assert nlu.understand("não", "CONFIRMAR_ACCION").confirmation == "no"


def test_firma_sin_state_sigue_funcionando():
    assert isinstance(nlu.understand("No reconozco un cargo de 350"), NLUResult)


# §1.8 Sin llave y con Gemini fallando
def test_sin_llave_usa_reglas():
    r, uso = nlu.understand_con_uso("No reconozco un cargo de 350")
    assert r.extractor == "rules" and r.amount == 350.0 and uso is None
    assert r.model_version == f"{classifier.get_classifier().model_version}+rules"


@pytest.mark.parametrize("error", [LLMUnavailable("caída"), RuntimeError("bug"), ValueError("x")])
def test_gemini_lanzando_no_lanza(gemini, error):
    gemini(error)
    r, uso = nlu.understand_con_uso("No reconozco un cargo de 350 en Oxxo")
    assert r.extractor == "rules" and uso is None
    assert (r.intent, r.amount, r.merchant_hint) == ("cargo_no_reconocido", 350.0, "Oxxo")


def test_gemini_devolviendo_basura_no_lanza(gemini):
    gemini(["no", "es", "un", "objeto"])
    assert nlu.understand("No reconozco un cargo de 350").extractor == "rules"


def test_con_gemini_extrae_llm_y_devuelve_el_uso(gemini):
    gemini({**VACIO, "amount": 350, "merchant_hint": "Oxxo"})
    r, uso = nlu.understand_con_uso("No reconozco un cargo de 350 en Oxxo")
    assert r.extractor == "llm" and uso == USO
    assert (r.amount, r.merchant_hint) == (350.0, "Oxxo")
    assert r.model_version == f"{classifier.get_classifier().model_version}+{extract_llm.PROMPT_VERSION}"
    assert nlu.understand("No reconozco un cargo de 350 en Oxxo") == r  # understand descarta el uso


def test_gemini_nunca_cambia_la_intencion(gemini):
    texto = "Quiero un préstamo"
    sin = nlu.understand(texto)
    gemini({**VACIO, "intent": "cargo_no_reconocido", "amount": 5000})
    con = nlu.understand(texto)
    assert (con.intent, con.intent_confidence, con.abstain) == (sin.intent, sin.intent_confidence, sin.abstain)


def test_clasificador_sin_cargar_no_usa_gemini(gemini, monkeypatch):
    gemini({**VACIO, "amount": 1})
    monkeypatch.setattr(nlu, "get_classifier", lambda: None)
    r = nlu.understand("No reconozco un cargo de 350")
    assert r.extractor == "rules" and r.amount == 350.0 and r.model_version == "stub-keywords-0+rules"


def test_nunca_lanza_aunque_falle_el_clasificador(monkeypatch):
    class Roto:
        model_version = "roto"

        def predict(self, text):
            raise RuntimeError("boom")
    monkeypatch.setattr(nlu, "get_classifier", lambda: Roto())
    r = nlu.understand("No reconozco un cargo de 350")
    assert r.abstain is True and r.extractor == "rules"


@pytest.mark.parametrize("texto", ["", " ", "a" * 5000, None])
def test_textos_raros(texto):
    assert isinstance(nlu.understand(texto), NLUResult)
