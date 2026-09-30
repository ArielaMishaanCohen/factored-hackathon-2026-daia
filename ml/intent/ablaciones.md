# Ablaciones · clasificador de intención (Fase 4.2, Paso 11)

Generado con `.venv/bin/python -m ml.intent.ablaciones`. Runs en `ml/intent/runs/ablaciones/`.

- **Modelo fijo:** el ganador de val, tfidf_lr (C=10), τ = 0.81. Solo cambia el train.
- **Val y test no cambian** entre filas: val trae Banking77 + suplemento con su ruido; test son las 200 frases del equipo. Nada de esto se usa para elegir: el modelo y τ ya estaban fijados.
- Macro-F1 y F1 por idioma: sin `ambiguo` y sin abstención. Cobertura y precisión: todas las frases, con el τ del ganador.
- Banking77 no tiene frases `mix` ni de `estado_disputa`: (a) nunca vio mezcla y no puede predecir esa clase (su F1 es 0 y le pone un techo de 0,8 al macro-F1).

## Fuentes

### Val

| Train | n train | **macro-F1** | F1 es | F1 pt | F1 mix | Cobertura (τ) | Precisión (τ) |
| :-- | --: | --: | --: | --: | --: | --: | --: |
| (a) solo Banking77 | 1379 | **0,646** | 0,684 | 0,631 | 0,412 | 58,4% | 88,2% |
| (b) solo suplemento | 485 | **0,606** | 0,569 | 0,584 | 0,960 | 20,9% | 95,3% |
| (c) ambos, con ruido | 1864 | **0,908** | 0,929 | 0,878 | 0,919 | 63,3% | 95,3% |

### Test

| Train | n train | **macro-F1** | F1 es | F1 pt | F1 mix | Cobertura (τ) | Precisión (τ) |
| :-- | --: | --: | --: | --: | --: | --: | --: |
| (a) solo Banking77 | 1379 | **0,399** | 0,335 | 0,412 | 0,521 | 32,5% | 52,3% |
| (b) solo suplemento | 485 | **0,557** | 0,534 | 0,542 | 0,693 | 24,0% | 85,4% |
| (c) ambos, con ruido | 1864 | **0,702** | 0,698 | 0,673 | 0,693 | 35,5% | 84,5% |

## Ruido

### Val

| Train | n train | **macro-F1** | F1 es | F1 pt | F1 mix | Cobertura (τ) | Precisión (τ) |
| :-- | --: | --: | --: | --: | --: | --: | --: |
| (c) ambos, con ruido | 1864 | **0,908** | 0,929 | 0,878 | 0,919 | 63,3% | 95,3% |
| (c) ambos, sin ruido | 1864 | **0,909** | 0,929 | 0,882 | 0,920 | 64,5% | 95,4% |

### Test

| Train | n train | **macro-F1** | F1 es | F1 pt | F1 mix | Cobertura (τ) | Precisión (τ) |
| :-- | --: | --: | --: | --: | --: | --: | --: |
| (c) ambos, con ruido | 1864 | **0,702** | 0,698 | 0,673 | 0,693 | 35,5% | 84,5% |
| (c) ambos, sin ruido | 1864 | **0,712** | 0,708 | 0,690 | 0,693 | 35,0% | 82,9% |
