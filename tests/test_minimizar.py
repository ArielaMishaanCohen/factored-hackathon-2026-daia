"""Minimización antes de mandar texto a Gemini (backend/app/llm/minimizar.py)."""
import pytest

from app.llm.minimizar import CORREO, DOCUMENTO, TARJETA, minimizar


@pytest.mark.parametrize("texto", [
    "No reconozco un cargo de 1.200.000 pesos",
    "Me cobraron 350,50 en Oxxo",
    "Não reconheço uma compra de 3.500",
    "un cargo de 350.50 USD",
    "120 mil en Rappi",
    "mi tarjeta terminada en 1234",
    "o cartão •••• 4321",
    "el 3/6 me cobraron 49.99",
    "caso DSP-000123",
    "me cobraron 2 veces 12.345.678,90",  # monto grande con miles y decimales
])
def test_montos_y_referencias_pasan_intactos(texto):
    assert minimizar(texto) == texto


@pytest.mark.parametrize("texto, esperado", [
    ("mi tarjeta 4111111111111111 tiene un cargo", f"mi tarjeta {TARJETA} tiene un cargo"),
    ("cartão 4111 1111 1111 1111.", f"cartão {TARJETA}."),
    ("tarjeta 5500-0000-0000-0004 cargo de 350", f"tarjeta {TARJETA} cargo de 350"),
    ("amex 3782 822463 10005", f"amex {TARJETA}"),
    ("son 13 dígitos 4222222222222", f"son 13 dígitos {TARJETA}"),
    ("19 dígitos: 6011000990139424123", f"19 dígitos: {TARJETA}"),
])
def test_enmascara_tarjetas(texto, esperado):
    assert minimizar(texto) == esperado


def test_doce_digitos_no_es_tarjeta():
    assert minimizar("pedido 123456789012") == "pedido 123456789012"


def test_enmascara_correos():
    assert minimizar("escríbanme a ana.perez+banco@mail.com.ar por favor") == \
        f"escríbanme a {CORREO} por favor"


@pytest.mark.parametrize("texto, esperado", [
    ("meu CPF é 123.456.789-09", f"meu CPF é {DOCUMENTO}"),
    ("CPF: 12345678909 e cobrança de 350", f"CPF: {DOCUMENTO} e cobrança de 350"),
    ("mi DNI 30.123.456 y un cargo de 1.200.000", f"mi DNI {DOCUMENTO} y un cargo de 1.200.000"),
    ("mi cédula 1020304050", f"mi cédula {DOCUMENTO}"),
    ("CUIT 20-30123456-7", f"CUIT {DOCUMENTO}"),
    ("empresa 12.345.678/0001-95", f"empresa {DOCUMENTO}"),
    ("sin palabra 123.456.789-09", f"sin palabra {DOCUMENTO}"),
])
def test_enmascara_documentos(texto, esperado):
    assert minimizar(texto) == esperado


def test_vacio():
    assert minimizar("") == ""
    assert minimizar(None) == ""
