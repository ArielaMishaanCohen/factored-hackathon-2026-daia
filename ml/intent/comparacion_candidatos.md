# Comparación de candidatos · clasificador de intención (Fase 4.2)

Generado con `.venv/bin/python -m ml.intent.comparar_candidatos` a partir de `ml/intent/runs/*_val.json`. No editar a mano: volver a generar cuando haya runs nuevos.

Todo es en **val** (507 frases, 45 `ambiguo`). El test no se abrió. Este archivo solo compara: la elección del modelo y de τ es el Paso 9 y sigue `criterio_seleccion.md` al pie de la letra.

## Cómo leer la tabla

- **macro-F1**: promedio simple del F1 de las 5 clases, sin las frases `ambiguo` y sin abstención. Cada clase pesa igual, aunque tenga pocas frases.
- **F1 es / pt / mix**: el mismo macro-F1, separado por idioma de la frase.
- **τ, cobertura, precisión**: el umbral de confianza con mayor cobertura que da precisión ≥ 95 % (`criterio_seleccion.md` §4). Cobertura = % de frases que el modelo contesta en vez de pedir aclaración; precisión = % de esas respuestas que son correctas. Contestar una frase `ambiguo` cuenta como error.
- **ambiguo abstenidas**: con ese τ, qué % de las frases `ambiguo` de val no contesta (lo deseable es 100 %).
- **Latencia p50**: mediana por frase. Los modelos locales se midieron en una laptop, sin red; Gemini incluye la red y la cola de la API.
- **Costo**: USD por 1.000 frases clasificadas. Los modelos locales cuestan 0 por llamada.
- **Tamaño**: MB en disco del modelo (solo registrado para embeddings).

## Todos los runs

| Candidato | Variante | macro-F1 | F1 es | F1 pt | F1 mix | τ | Cobertura | Precisión | ambiguo abstenidas | Latencia p50 (ms) | Costo por 1.000 (USD) | Tamaño (MB) |
| :-- | :-- | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: |
| Baseline 0 · clase mayoritaria | – | **0,099** | 0,103 | 0,099 | 0,057 | 0,00 | 100,0% | 29,8% | 0,0% | 0,0 | 0,00 | – |
| Baseline 1 · palabras clave | – | **0,646** | 0,661 | 0,620 | 0,574 | 0,00 | 100,0% | 58,8% | 0,0% | 0,0 | 0,00 | – |
| TF-IDF + regresión logística | C=0.1 | **0,845** | 0,866 | 0,806 | 0,920 | 0,39 | 39,8% | 95,5% | 95,6% | 0,6 | 0,00 | – |
| TF-IDF + regresión logística | C=1 | **0,902** | 0,930 | 0,871 | 0,880 | 0,60 | 60,6% | 95,1% | 86,7% | 0,6 | 0,00 | – |
| TF-IDF + regresión logística | C=10 | **0,908** | 0,929 | 0,878 | 0,919 | 0,81 | 63,3% | 95,3% | 80,0% | 0,6 | 0,00 | – |
| Embeddings + regresión logística | modelo=e5s, C=0.1, clases=5 | **0,723** | 0,734 | 0,714 | 0,644 | 0,28 | 30,6% | 96,1% | 100,0% | 12,0 | 0,00 | 487,4 |
| Embeddings + regresión logística | modelo=e5s, C=1, clases=5 | **0,802** | 0,800 | 0,804 | 0,731 | 0,47 | 48,1% | 95,1% | 97,8% | 11,8 | 0,00 | 487,4 |
| Embeddings + regresión logística | modelo=e5s, C=10, clases=5 | **0,857** | 0,875 | 0,845 | 0,731 | 0,66 | 57,8% | 95,6% | 93,3% | 11,6 | 0,00 | 487,4 |
| Embeddings + regresión logística | modelo=minilm, C=0.1, clases=5 | **0,780** | 0,821 | 0,736 | 0,700 | 0,75 | 35,5% | 95,0% | 91,1% | 10,4 | 0,00 | 252,2 |
| Embeddings + regresión logística | modelo=minilm, C=1, clases=5 | **0,814** | 0,830 | 0,790 | 0,824 | 0,91 | 35,9% | 95,6% | 93,3% | 9,4 | 0,00 | 252,2 |
| Embeddings + regresión logística | modelo=minilm, C=10, clases=5 | **0,822** | 0,830 | 0,814 | 0,823 | 0,98 | 36,7% | 95,7% | 93,3% | 10,4 | 0,00 | 252,2 |
| Embeddings + regresión logística | modelo=e5s, C=0.1, clases=6 | **0,729** | 0,741 | 0,715 | 0,679 | 0,24 | 30,4% | 95,5% | 100,0% | 11,6 | 0,00 | 487,4 |
| Embeddings + regresión logística | modelo=e5s, C=1, clases=6 | **0,792** | 0,792 | 0,788 | 0,758 | 0,45 | 44,0% | 96,4% | 100,0% | 11,4 | 0,00 | 487,4 |
| Embeddings + regresión logística | modelo=e5s, C=10, clases=6 | **0,856** | 0,871 | 0,845 | 0,768 | 0,61 | 58,6% | 96,0% | 100,0% | 11,6 | 0,00 | 487,4 |
| Gemini zero-shot | gemini-3.8-flash, intent_zeroshot_v1 | **0,904** | 0,917 | 0,870 | 1,000 | 0,96 | 41,8% | 97,6% | 93,3% | 2.036 | 2,02 | – |

`clases=6` en embeddings: entrenado también con `ambiguo` como clase; si la predice, se abstiene.

## F1 por clase (mejor variante de cada candidato)

| Candidato | Variante | no_rec | cobro_inc | tarjeta | estado | fuera |
| :-- | :-- | --: | --: | --: | --: | --: |
| Baseline 0 · clase mayoritaria | – | 0,000 | 0,000 | 0,000 | 0,000 | 0,493 |
| Baseline 1 · palabras clave | – | 0,601 | 0,627 | 0,559 | 0,780 | 0,664 |
| TF-IDF + regresión logística | C=10 | 0,908 | 0,824 | 0,921 | 0,990 | 0,897 |
| Embeddings + regresión logística | modelo=e5s, C=10, clases=5 | 0,868 | 0,843 | 0,831 | 0,923 | 0,822 |
| Gemini zero-shot | gemini-3.8-flash, intent_zeroshot_v1 | 0,937 | 0,833 | 0,946 | 0,936 | 0,865 |

## Detalle de Gemini

**gemini-3.8-flash** (`20260929-183041_gemini_zeroshot_val.json`)

- Frases: 507 (val completo) · errores de la API: 0 · con reintento: 3 · respondió `ambiguo`: 46.
- Latencia p50 2.036 ms · p95 6.231 ms (solo la API, sin las esperas por límite de ritmo).
- Tokens por frase: 909 de entrada · 20 de salida · 338 de razonamiento (se cobran como salida).
- Costo: USD 1,03 por toda la corrida · USD 2,02 por 1.000 frases, con USD 0,75 entrada y USD 3,75 salida por 1M de tokens (ai.google.dev/gemini-api/docs/pricing, consultado el 29-sep-2026 (docs/decisions.md, D1.11)).

Cuando Gemini responde `ambiguo` o la API falla, la frase queda sin respuesta: cuenta como fallo en macro-F1 y se abstiene con cualquier τ > 0 (`evaluate.metricas`). Su confianza es la que él mismo declara en el JSON, no una probabilidad calibrada.
