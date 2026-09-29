# Reporte de datos · set de intenciones (Fase 4.1)

**Dueño:** B · **Fecha:** 29-sep-2026 · **Guía de etiquetado:** `labeling_guide.md` 1.4 · **Decisión:** D4.2 en `docs/decisions.md`
**Se regenera con:** `make dataset` (semilla 42; la salida es idéntica en cada corrida)

## Resumen

| | Frases | Familias |
| :-- | --: | --: |
| train | 2.041 | 1.526 |
| val | 507 | 383 |
| test | 200 | 50 |
| **Total** | **2.748** | **1.959** |

Seis etiquetas (`cargo_no_reconocido`, `cobro_incorrecto`, `tarjeta_comprometida`, `estado_disputa`, `fuera_de_alcance`, `ambiguo`), tres idiomas (`es` 50 %, `pt` 42 %, `mix` 8 %). Train/val y test salen de **fuentes distintas**: ninguna frase de Banking77 ni del suplemento está en test.

## 1. Fuentes

| Fuente | `origin` | Qué es | Frases | Split |
| :-- | :-- | :-- | --: | :-- |
| Banking77 | `externo_traducido` | Consultas reales de clientes de un banco, en inglés, filtradas, traducidas a ES o PT con Claude y re-etiquetadas con nuestras reglas | 1.749 | train/val |
| Suplemento | `llm` | Generado con Claude y revisado por el equipo; cubre lo que Banking77 no tiene | 799 (160 familias) | train/val |
| Test | `llm_externo` | Generado con ChatGPT a partir del plan de familias y revisado por el equipo; PT y mezcla traducidos después con Claude | 200 (50 familias) | test |

### 1.1 Banking77

Casanueva, I., Temčinas, T., Gerz, D., Henderson, M. y Vulić, I. (2020). *Efficient Intent Detection with Dual Sentence Encoders*. NLP4ConvAI (ACL 2020). arXiv:2003.04807. Licencia **CC-BY-4.0**. https://huggingface.co/datasets/PolyAI/banking77

El CSV original (`data/external/banking77.csv`) no se versiona; lo baja `ml/intent/sources/banking77_prepare.py`.

1. **Mapeo de clases** (`b77_mapeo.csv`, columna `decision`). Las 77 clases se asignaron a nuestras etiquetas:

   | Nuestra etiqueta | Clases de Banking77 |
   | :-- | :-- |
   | `cargo_no_reconocido` | `card_payment_not_recognised`, `cash_withdrawal_not_recognised`, `direct_debit_payment_not_recognised` |
   | `cobro_incorrecto` | `transaction_charged_twice`, `extra_charge_on_statement`, `card_payment_wrong_exchange_rate`, `wrong_amount_of_cash_received`, `wrong_exchange_rate_for_cash_withdrawal` |
   | `tarjeta_comprometida` | `compromised_card`, `lost_or_stolen_card` |
   | `cobro_incorrecto` o `fuera_de_alcance` (frase por frase) | `card_payment_fee_charged`, `cash_withdrawal_charge` |
   | `fuera_de_alcance`, negativos difíciles | `Refund_not_showing_up`, `request_refund`, `pending_card_payment`, `declined_card_payment`, `reverted_card_payment?`, `card_swallowed` |
   | `fuera_de_alcance`, resto | las 57 clases restantes (activar tarjeta, PIN, transferencias, recargas, verificación, etc.) |
   | por decidir → `fuera_de_alcance` | `lost_or_stolen_phone` (muestra de 30, revisada a mano) |

   `estado_disputa` y `ambiguo` no existen en Banking77; salen del suplemento (y 23 frases de Banking77 terminaron en `ambiguo` al re-etiquetar).

2. **Muestreo** (`sources/banking77_select.py`): quita duplicados exactos y muestrea con semilla 42 hasta un tope por grupo, estratificando por clase original. Resultado: 1.777 frases.

3. **Re-etiquetado con las reglas de `labeling_guide.md`**, en dos rondas:
   - **Paso 4, al seleccionar:** una heurística marcó 223 frases como sospechosas; se revisaron todas y **82 cambiaron** de etiqueta (p. ej., 27 `cargo_no_reconocido` → `tarjeta_comprometida` por mencionar clonación o varios cargos seguidos; 29 `cobro_incorrecto` → `fuera_de_alcance` por preguntar por una comisión o un tipo de cambio sin decir que esté mal).
   - **Paso 5, al traducir:** Claude marcó 100 frases con dudas de etiqueta; se revisaron y **94 cambiaron** (p. ej., 41 `cargo_no_reconocido` → `tarjeta_comprometida` por la regla 1; 23 frases → `ambiguo` por la regla 6).
   - **Neto:** 153 de 1.747 frases (**8,8 %**) terminaron con una etiqueta distinta a la que daba su clase original. Se sumaron las 30 de `lost_or_stolen_phone`, sin etiqueta inicial.

   La trazabilidad está en `b77_seleccion.csv` (`label_inicial`, `sospechosa`, `motivo`, `label_final`) y `b77_traducido.csv` (`revisar`, `resolucion`, `label`). Cada frase guarda su clase original en `source_ref`.

4. **Traducción:** cada frase se tradujo a **un solo** idioma (957 ES neutro, 792 PT-BR) con Claude, en registro de chat informal y con localización mínima. Nunca con Gemini, porque Gemini es candidato en la 4.2.

### 1.2 Suplemento

160 familias (idea base + ~5 paráfrasis) según `plan_familias.md`: 50 de `estado_disputa`, 40 de `ambiguo`, 40 de localización y portuñol (Oxxo, Pix, Nubank, "lana", "grana", "guita") y 30 de casos límite entre clases e inyecciones con intención real. Idiomas: 320 ES, 280 PT, 199 mezcla; variantes MX, CO, AR, BR y neutro.

### 1.3 Test

50 familias × 4 frases, con subtemas que **no se repiten** en el suplemento (`plan_familias.md`, sección 2). Lo generó ChatGPT, que no se usa en ninguna otra parte del set, y lo revisó el equipo (ver Limitaciones). No lleva ruido artificial.

## 2. Limpieza y validaciones (`build_dataset.py`)

- **Deduplicación:** se quitaron 29 frases repetidas con la misma etiqueta (28 de Banking77 y 1 del suplemento), listadas en la salida de `make dataset`.
- **Split:** Banking77 + suplemento se dividen 80/20 en train/val **por familia**, estratificando por fuente × etiqueta × idioma. El test va aparte.
- **Chequeos que detienen el armado si fallan:** ninguna familia en dos splits; ningún `origin` prohibido en test; ningún duplicado normalizado; valores dentro de los permitidos; números y montos intactos después del ruido; similitud TF-IDF test vs. train/val ≤ 0,9. **Máxima observada: 0,648.**

## 3. Ruido (`noise.py`)

Solo en train/val; el test conserva su redacción. Cada frase recibe cero o más transformaciones con semilla fija por `id` (agregar o quitar frases no cambia el ruido de las demás), y se registran en el campo `noise`. Los números y montos están protegidos. El texto sin ruido queda en `data/sin_ruido.csv` para la ablación de la 4.2.

| Transformación | Objetivo | Real (2.548 frases) |
| :-- | --: | --: |
| sin ruido | 30 % | 32,1 % |
| `sin_tildes` | 50 % | 38,7 % |
| `minusculas` | 40 % | 38,6 % |
| `sin_puntuacion` | 40 % | 35,7 % |
| `abreviaturas` ("xq", "vc", "q") | 30 % | 16,4 % |
| `typo` | 25 % | 25,3 % |
| `repetidos` ("holaaa") | 10 % | 9,3 % |
| `emoji` | 10 % | 9,2 % |

Las tasas reales de `sin_tildes` y `abreviaturas` quedan bajo el objetivo porque una transformación solo cuenta si cambió el texto (muchas frases no tienen tildes ni palabras abreviables). En promedio, 1,7 transformaciones por frase.

## 4. Conteos

### Split × etiqueta × idioma

| split | etiqueta | es | pt | mix | total |
| :-- | :-- | --: | --: | --: | --: |
| train | `ambiguo` | 65 | 68 | 44 | 177 |
| | `cargo_no_reconocido` | 193 | 150 | 15 | 358 |
| | `cobro_incorrecto` | 200 | 175 | 15 | 390 |
| | `estado_disputa` | 90 | 75 | 50 | 215 |
| | `fuera_de_alcance` | 312 | 260 | 20 | 592 |
| | `tarjeta_comprometida` | 164 | 130 | 15 | 309 |
| val | `ambiguo` | 18 | 17 | 10 | 45 |
| | `cargo_no_reconocido` | 46 | 38 | 5 | 89 |
| | `cobro_incorrecto` | 49 | 41 | 5 | 95 |
| | `estado_disputa` | 20 | 20 | 10 | 50 |
| | `fuera_de_alcance` | 81 | 65 | 5 | 151 |
| | `tarjeta_comprometida` | 39 | 33 | 5 | 77 |
| test | `ambiguo` | 12 | 8 | 4 | 24 |
| | `cargo_no_reconocido` | 20 | 16 | 4 | 40 |
| | `cobro_incorrecto` | 20 | 16 | 4 | 40 |
| | `estado_disputa` | 16 | 12 | 4 | 32 |
| | `fuera_de_alcance` | 16 | 12 | 0 | 28 |
| | `tarjeta_comprometida` | 16 | 16 | 4 | 36 |
| **Total** | | **1.377** | **1.152** | **219** | **2.748** |

### Split × fuente (`origin`)

| split | banking77 (`externo_traducido`) | suplemento (`llm`) | test (`llm_externo`) | total |
| :-- | --: | --: | --: | --: |
| train | 1.397 | 644 | 0 | 2.041 |
| val | 352 | 155 | 0 | 507 |
| test | 0 | 0 | 200 | 200 |

### Etiqueta × fuente

| etiqueta | banking77 | suplemento | test | total |
| :-- | --: | --: | --: | --: |
| `ambiguo` | 23 | 199 | 24 | 246 |
| `cargo_no_reconocido` | 367 | 80 | 40 | 487 |
| `cobro_incorrecto` | 400 | 85 | 40 | 525 |
| `estado_disputa` | 0 | 265 | 32 | 297 |
| `fuera_de_alcance` | 653 | 90 | 28 | 771 |
| `tarjeta_comprometida` | 306 | 80 | 36 | 422 |

## 5. Acuerdo entre personas (kappa de Cohen)

**Pendiente.** La muestra ya está lista: 100 frases con semilla 42, estratificadas por etiqueta (55 de Banking77, 25 del suplemento, 20 del test) en `kappa/muestra_para_etiquetar.csv`, con las respuestas aparte en `kappa/muestra_respuestas.csv`. Falta que una segunda persona del equipo la etiquete con `labeling_guide.md` sin ver las etiquetas. Objetivo: kappa > 0,8 en total y por fuente. Los desacuerdos se resolverán con las reglas de la guía; si una regla no alcanza, se agregará y subirá la versión.

Mientras tanto, la única evidencia de consistencia de etiquetas es la revisión en dos rondas de Banking77 (sección 1.1) y la revisión del suplemento y el test por el equipo.

## 6. Limitaciones

- **Otro dominio:** Banking77 viene de un neobanco británico (recargas, transferencias, tarjetas virtuales). El vocabulario y los productos no son los de un banco latinoamericano; la traducción localiza lo mínimo.
- **Portugués traducido, no nativo:** todo el PT (Banking77, parte del suplemento y del test) lo produjo Claude; nadie del equipo escribe portugués. Puede sonar menos natural que un cliente brasileño real.
- **Test generado con ChatGPT, no escrito a mano.** Es otro autor que el del suplemento (Claude), así que el modelo no puede aprenderse el estilo del test desde train. Pero tiene el estilo limpio de un LLM y no el de clientes reales: **puede sobrestimar el desempeño**. Pendiente: reemplazarlo por un test escrito a mano con el mismo `plan_familias.md`. Si un candidato de la 4.2 es un modelo de OpenAI, este reemplazo es obligatorio.
- **Val viene de la misma distribución que train** (Banking77 + suplemento) y test de otra. El umbral de abstención elegido en val puede quedar optimista al aplicarlo en test.
- **Kappa pendiente** (sección 5).
- **Set sintético o traducido:** ninguna frase es un mensaje real de un cliente de este banco (los textos del banco no sirven: D4.1). Las métricas miden la separación de intenciones en este lenguaje y no reemplazan una validación con mensajes reales.
