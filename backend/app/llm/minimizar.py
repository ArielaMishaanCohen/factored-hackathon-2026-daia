"""Minimización de datos antes de mandar texto del cliente a Gemini.

Enmascara lo que el extractor no necesita y no debe salir del backend:
- números de tarjeta: 13 a 19 dígitos seguidos, o en grupos (4-4-4-4, 4-4-4-4-N, Amex 4-6-5);
- correos;
- documentos con formato propio (CPF, CNPJ, CUIT/CUIL) y cualquier número que venga detrás
  de "DNI", "CPF", "RG", "cédula", "CC", "documento", etc.

Los montos pasan intactos ("1.200.000", "350,50", "3.500"), igual que los últimos 4 dígitos de
la tarjeta ("terminada en 1234"), que el cliente usa para identificar el cargo.
"""
from __future__ import annotations

import re

TARJETA = "[TARJETA]"
CORREO = "[CORREO]"
DOCUMENTO = "[DOCUMENTO]"

_TARJETA = re.compile(
    r"(?<![\d.,])(?:"
    r"\d{13,19}"                                  # seguidos
    r"|\d{4}(?:[ -]\d{4}){3}(?:[ -]\d{1,3})?"     # 4-4-4-4 (hasta 19 dígitos)
    r"|\d{4}[ -]\d{6}[ -]\d{5}"                   # Amex 4-6-5
    r")(?![\d.,]?\d)")
_CORREO = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_DOC_FORMATO = re.compile(
    r"(?<![\d.])(?:"
    r"\d{3}\.\d{3}\.\d{3}-\d{2}"                  # CPF
    r"|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}"           # CNPJ
    r"|\d{2}-\d{7,8}-\d"                          # CUIT / CUIL
    r")(?![\d.])")
# número detrás de la palabra del documento: "DNI 30.123.456", "CPF: 12345678900", "cédula 1020304050"
_DOC_PALABRA = re.compile(
    r"(?P<pre>\b(?:DNI|CPF|CNPJ|RG|CUIT|CUIL|RUT|CI|CC|C\.C\.|c[eé]dula|documento|identidad)\b"
    r"\s*(?:n[º°o.]?|n[uú]mero|de\s+identidad)?\s*[:#]?\s*)"
    r"(?P<num>\d[\d.\-/ ]{4,16}\d)", re.I)


def minimizar(texto: str) -> str:
    """Devuelve el texto con tarjetas, correos y documentos enmascarados. Nunca lanza."""
    if not texto:
        return texto or ""
    t = _CORREO.sub(CORREO, texto)
    t = _DOC_FORMATO.sub(DOCUMENTO, t)
    t = _DOC_PALABRA.sub(lambda m: m["pre"] + DOCUMENTO, t)
    t = _TARJETA.sub(TARJETA, t)
    return t
