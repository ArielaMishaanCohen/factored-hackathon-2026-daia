"""understand() integrado (integracion_backend.md §1.1 y §1.8): clasificador + Gemini + reglas.

Sin red: conftest.py vacía GEMINI_API_KEY; los casos con Gemini usan un cliente falso.
"""
import pytest

import app.nlu as nlu
from app.llm import gemini_client
from app.llm.gemini_client import LLMUnavailable, LLMUsage
from app.nlu import classifier, extract_llm, intent_llm
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
    r = nlu.understand("Cómo cambio mi PIN")
    assert r.intent == "fuera_de_alcance" and r.abstain is False


def test_prestamo_sin_gemini():
    # Con el lote de fuera de alcance (D4.6) el clasificador ya dice fuera_de_alcance, pero bajo τ
    # (conf ~0,62): sin Gemini pide aclaración. Con Gemini, ver test_prestamo_con_segunda_opinion.
    r = nlu.understand("Quiero un préstamo")
    assert r.intent == "fuera_de_alcance" and r.abstain is True


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


def test_la_extraccion_nunca_cambia_la_intencion(gemini):
    # Un "intent" dentro de la respuesta de extracción se ignora (y la segunda opinión, sin
    # "confidence", no es válida): el turno queda como sin Gemini.
    texto = "Quiero un préstamo"
    sin = nlu.understand(texto)
    gemini({**VACIO, "intent": "cargo_no_reconocido", "amount": 5000})
    con = nlu.understand(texto)
    assert (con.intent, con.intent_confidence, con.abstain) == (sin.intent, sin.intent_confidence, sin.abstain)


# D4.5: segunda opinión de Gemini sobre la intención, solo bajo tau_intencion
class FakeDoble:
    """Responde a la extracción y a la intención por separado (según el esquema) y cuenta las llamadas."""
    def __init__(self, intencion, campos=None):
        self.intencion, self.campos, self.llamadas_intencion = intencion, campos or VACIO, 0

    def generate_json(self, prompt_sistema, texto_usuario, esquema):
        if "intent" in esquema["properties"]:
            self.llamadas_intencion += 1
            assert texto_usuario.startswith("<frase>") and "confidence" in esquema["required"]
            if isinstance(self.intencion, Exception):
                raise self.intencion
            return self.intencion, USO
        return self.campos, USO


@pytest.fixture
def doble(monkeypatch):
    def usar(intencion, campos=None):
        f = FakeDoble(intencion, campos)
        monkeypatch.setattr(gemini_client, "get_client", lambda: f)
        return f
    return usar


def test_prestamo_con_segunda_opinion(doble):
    doble({"intent": "fuera_de_alcance", "confidence": 0.95})
    r, uso = nlu.understand_con_uso("Quiero un préstamo")
    assert (r.intent, r.intent_confidence, r.abstain) == ("fuera_de_alcance", 0.95, False)
    assert intent_llm.PROMPT_VERSION in r.model_version
    assert uso.tokens_in == 2 * USO.tokens_in  # extracción + intención


def test_segunda_opinion_resuelve_la_frase_de_la_demo(doble):
    texto = "Ayer me cobraron USD 350 en Oxxo y no fui yo"
    assert nlu.understand(texto).abstain is True  # sin Gemini: conf ~0,52 < τ
    doble({"intent": "cargo_no_reconocido", "confidence": 0.9}, {**VACIO, "amount": 350, "currency": "USD"})
    r = nlu.understand(texto)
    assert (r.intent, r.abstain, r.amount, r.currency) == ("cargo_no_reconocido", False, 350.0, "USD")


@pytest.mark.parametrize("intencion", [
    {"intent": "ambiguo", "confidence": 0.99},
    {"intent": "cargo_no_reconocido", "confidence": 0.5},   # bajo tau_gemini
    {"intent": "prestamo", "confidence": 0.99},             # fuera del esquema
    {"intent": "cargo_no_reconocido"},                      # sin confidence
    LLMUnavailable("caído"),
    RuntimeError("boom"),
])
def test_segunda_opinion_que_no_sirve_deja_la_abstencion(doble, intencion):
    texto = "hola"
    sin = nlu.understand(texto)
    doble(intencion)
    r = nlu.understand(texto)
    assert r.abstain is True and (r.intent, r.intent_confidence) == (sin.intent, sin.intent_confidence)
    assert intent_llm.PROMPT_VERSION not in r.model_version


def test_sin_abstencion_no_se_pide_segunda_opinion(doble):
    f = doble({"intent": "fuera_de_alcance", "confidence": 1.0})
    r = nlu.understand("No reconozco un cargo de 350 en Oxxo")
    assert r.intent == "cargo_no_reconocido" and f.llamadas_intencion == 0


def test_sin_tau_gemini_no_hay_segunda_opinion(doble, monkeypatch):
    from app import config
    politica = config.get_policy()
    intent_sin = {k: v for k, v in politica["intent"].items() if k != "tau_gemini"}
    monkeypatch.setattr(nlu, "get_policy", lambda: {**politica, "intent": intent_sin})
    f = doble({"intent": "fuera_de_alcance", "confidence": 1.0})
    assert nlu.understand("Quiero un préstamo").abstain is True and f.llamadas_intencion == 0


def test_la_segunda_opinion_minimiza_el_texto(doble):
    f = doble({"intent": "tarjeta_comprometida", "confidence": 0.9})
    visto = []
    original = f.generate_json
    f.generate_json = lambda p, t, e: (visto.append(t), original(p, t, e))[1]
    nlu.understand("hola mi tarjeta 4111 1111 1111 1111")
    assert visto and all("4111 1111 1111 1111" not in t for t in visto)


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


@pytest.mark.parametrize("texto", ["", " ", "a" * 5000, None], ids=["vacio", "espacio", "5000_caracteres", "None"])
def test_textos_raros(texto):
    assert isinstance(nlu.understand(texto), NLUResult)
