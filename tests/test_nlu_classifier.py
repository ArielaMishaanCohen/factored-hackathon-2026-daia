"""NLU con el clasificador de la 4.2: carga, umbral desde policy.yaml y caída al stub."""
import logging

import pytest

import app.nlu as nlu
from app.config import get_policy
from app.nlu import classifier, stub

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
    assert r.model_version == classifier.get_classifier().model_version


@pytest.mark.parametrize("tau, abstiene", [(0.0, False), (1.01, True)])
def test_abstain_sigue_al_tau(monkeypatch, tau, abstiene):
    monkeypatch.setattr(nlu, "get_policy", lambda: {"intent": {"tau_intencion": tau}})
    assert nlu.understand("No reconozco un cargo de 350").abstain is abstiene


def test_resto_de_campos_sigue_en_el_stub():
    texto = "Não reconheço uma compra de 3.500"
    r, s = nlu.understand(texto), stub.understand(texto)
    keep = {"intent", "intent_confidence", "abstain", "model_version"}
    assert r.model_dump(exclude=keep) == s.model_dump(exclude=keep)
    assert r.amount == 3500 and r.language == "pt" and r.extractor == "rules"


def test_si_el_modelo_no_carga_cae_al_stub_y_lo_registra(monkeypatch, sin_cache, caplog):
    monkeypatch.setenv("INTENT_MODEL_PATH", "/no/existe/intent_model.joblib")
    with caplog.at_level(logging.WARNING, logger="latam.nlu"):
        r = nlu.understand("Me robaron la tarjeta")
    assert r == stub.understand("Me robaron la tarjeta")
    assert r.model_version == "stub-keywords-0"
    assert "no cargó" in caplog.text
