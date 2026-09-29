# Criterio de selección · clasificador de intenciones (Fase 4.2)

**Dueño:** B · **Fecha:** 29-sep-2026 · **Datos:** set de la 4.1 (`data_report.md`, D4.2)

Este criterio se escribe y se sube a git **antes** de entrenar candidatos y **antes** de ver el test. La fecha del commit es la prueba. Se aplica tal cual está escrito.

## 1. Clases de salida

- El modelo devuelve una de las 5 intenciones de `docs/design.md` §2: `cargo_no_reconocido`, `cobro_incorrecto`, `tarjeta_comprometida`, `estado_disputa`, `fuera_de_alcance`, más una confianza.
- `ambiguo` **no es una salida**. En la variante principal no se entrena con esas frases.
- En evaluación, toda frase `ambiguo` cuenta como "debería abstenerse".

## 2. Métricas

| Métrica | Sobre qué frases | Para qué |
| :-- | :-- | :-- |
| **Macro-F1 de 5 clases** | Sin `ambiguo` y sin abstención (se toma el argmax siempre) | Métrica de selección (§3) |
| F1 por clase y por idioma (`es`, `pt`, `mix`) | Mismas que arriba | Ver dónde falla cada candidato |
| Cobertura vs. precisión con abstención | Todas, incluidas `ambiguo` | Elegir τ (§4) |
| Latencia p50 por frase | — | Desempate (§3) |
| Costo por 1.000 frases (USD) | — | Desempate (§3) |

Con abstención, para un τ dado:

- **Cobertura** = frases contestadas (confianza ≥ τ) / total de frases.
- **Precisión** = contestadas correctas / contestadas. Una frase `ambiguo` contestada es **error**.

## 3. Selección del modelo

1. Gana el candidato con mejor **macro-F1 en val**.
2. Si la diferencia con el siguiente es **< 2 puntos** de macro-F1, gana el **más barato y rápido** (costo por 1.000 frases y latencia p50).

**Sesgo conocido:** val sale de la misma distribución que train (Banking77 traducido + suplemento), lo que favorece a los modelos entrenados frente a Gemini zero-shot. Se declara; no se corrige.

## 4. Umbral τ_intención

- Se elige **en val**, con el modelo ya elegido.
- τ_intención = el τ con **mayor cobertura** que da **precisión ≥ 95 %**.
- Si ningún τ llega a 95 %: el τ con la **mayor precisión** entre los que dan **cobertura ≥ 50 %**, y se declara en la model card y en D4.3.

## 5. Test

- Se evalúa **una sola vez**, con el modelo y el τ ya fijados.
- Se reportan **todos** los candidatos en test, no solo el elegido.
- Nada se cambia después de ver el test. Si algo se cambia, se declara y se reporta también el número anterior.

## 6. Ablaciones (fuentes y ruido)

- Se corren con el modelo ya elegido.
- Se reportan en val y en test.
- No cambian la elección del modelo ni el τ.
