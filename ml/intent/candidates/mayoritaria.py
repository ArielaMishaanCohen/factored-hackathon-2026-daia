"""Baseline 0 (Paso 4 de la guía 4.2): predice siempre la clase más frecuente de train.

predict_proba devuelve la frecuencia de cada clase en train, igual para todas las
frases: el argmax es la mayoritaria y la confianza es su proporción.
"""

import numpy as np

from ml.intent.evaluate import CLASES


class Mayoritaria:
    costo_por_1000_usd = 0.0

    def fit(self, textos, labels):
        conteo = np.array([sum(l == c for l in labels) for c in CLASES], dtype=float)
        self.frecuencias_ = conteo / conteo.sum()
        self.clase_ = CLASES[int(conteo.argmax())]
        return self

    def predict_proba(self, textos):
        return np.tile(self.frecuencias_, (len(textos), 1))


def crear(**params):
    return Mayoritaria(**params)
