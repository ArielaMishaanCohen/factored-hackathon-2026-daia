"""NLU con el clasificador de la 4.2: carga, umbral desde policy.yaml y caída al stub (intención)."""
import logging

import pytest

import app.nlu as nlu
from app.config import get_policy
from app.nlu import classifier, rules, stub

CLASES = {"cargo_no_reconocido", "cobro_incorrecto", "tarjeta_comprometida", "estado_disputa", "fuera_de_alcance"}


@pytest.fixture
def sin_cache():
    classifier.get_classifier.cache_clear()
    yield
    classifier.get_classifier.cache_clear()


def test_modelo_carga_una_vez():
    clf = classifier.get_classifier()
    assert clf is not None and clf is classifier.get_classifier()
    assert set(clf.clases) == CLASES
    assert clf.model_version.startswith("tfidf_lr-C10-")


def test_predict_devuelve_intent_y_confianza():
    intent, conf = classifier.get_classifier().predict("No reconozco un cargo de 350 en Oxxo")
    assert type(intent) is str and intent == "cargo_no_reconocido"
    assert 0.0 <= conf <= 1.0


def test_understand_usa_clasificador_y_tau_de_policy():
    r = nlu.understand("Me cobraron dos veces 120000")
    intent, conf = classifier.get_classifier().predict("Me cobraron dos veces 120000")
    assert (r.intent, r.intent_confidence) == (intent, conf)
    assert r.abstain == (conf < get_policy()["intent"]["tau_intencion"])
    assert r.model_version == f"{classifier.get_classifier().model_version}+rules"  # sin llave en tests


@pytest.mark.parametrize("tau, abstiene", [(0.0, False), (1.01, True)])
def test_abstain_sigue_al_tau(monkeypatch, tau, abstiene):
    monkeypatch.setattr(nlu, "get_policy", lambda: {"intent": {"tau_intencion": tau}})
    assert nlu.understand("No reconozco un cargo de 350").abstain is abstiene


def test_resto_de_campos_sale_de_las_reglas_sin_gemini():
    texto = "Não reconheço uma compra de 3.500"
    r = nlu.understand(texto)
    assert r.model_dump(include=set(rules.CAMPOS)) == rules.extract(texto)
    assert r.amount == 3500 and r.language == "pt" and r.extractor == "rules"


def test_si_el_modelo_no_carga_cae_al_stub_y_a_las_reglas(monkeypatch, sin_cache, caplog):
    monkeypatch.setenv("INTENT_MODEL_PATH", "/no/existe/intent_model.joblib")
    with caplog.at_level(logging.WARNING, logger="latam.nlu"):
        r = nlu.understand("Me robaron la tarjeta")
    s = stub.understand("Me robaron la tarjeta")
    assert (r.intent, r.intent_confidence, r.abstain) == (s.intent, s.intent_confidence, s.abstain)
    assert r.model_dump(include=set(rules.CAMPOS)) == rules.extract("Me robaron la tarjeta")
    assert r.model_version == "stub-keywords-0+rules" and r.extractor == "rules"
    assert "no cargó" in caplog.text
