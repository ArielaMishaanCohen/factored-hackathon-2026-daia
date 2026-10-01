# Set de casos end-to-end · Fase 6.1

**Held-out congelado en el commit `90bccf2`** (1-oct-2026), antes de correr el sistema sobre él. Desde ese commit, `heldout.jsonl` no se mira ni se cambia hasta la corrida de la Fase 6; cualquier cambio posterior se anota aquí con su motivo y su commit.

**Política:** `config/policy.yaml` v1.3.0 · **Gold:** corrida `20260929T234658Z-7cf922c1` · **Formato:** `SCHEMA.md` v1.0.0 · **Decisión:** D6.1 en `docs/decisions.md` · **Plan:** `docs/roadmap_fases_1_a_8.md` §6.1

Cada caso es una conversación con guion determinista (mensajes fijos y reglas de respuesta fijas, sin LLM que simule al cliente) y con el resultado esperado derivado de los datos y de la política, no de lo que opine alguien. El runner, los baselines y las métricas son de la 6.2 y la 6.3.

## Archivos

| Archivo | Qué es | Se edita a mano |
| :-- | :-- | :-: |
| `dev.jsonl` | 41 casos para depurar. Se pueden mirar y correr todas las veces que haga falta | No (lo genera `construir_casos.py`) |
| `heldout.jsonl` | 189 casos para la medición final. No se mira hasta la corrida | No (lo genera `construir_casos.py`) |
| `SCHEMA.md` | Formato de un caso: campos, reglas de respuesta del runner, contra qué se compara cada esperado, un ejemplo por categoría | Sí |
| `schema.py` | Modelo Pydantic `Case` con las validaciones del formato. No importa nada de `backend/` | Sí |
| `inventario.md` | Inventario del gold por regla (cuántas transacciones caen en R2…R12, por segmento), el reparto propuesto y las categorías que quedan por debajo del mínimo | Sí |
| `esperado.py` | Primera regla que aplica, con acción, prioridad y cola, calculada con SQL propio sobre el gold y los umbrales de `policy.yaml`. No usa el motor del backend | Sí |
| `mensajes_fuente.py` | Los mensajes de los clientes, con la transacción meta, el split, lo que cita el cliente y la preparación. Solo datos | Sí |
| `verificar_mensajes.py` | Cruza cada mensaje contra el gold (lo citado apunta a una sola candidata, la transacción es del cliente, similitud con `ml/`) y genera `mensajes.jsonl` y `mensajes_revision.csv` | Sí |
| `mensajes.jsonl` | Mensajes verificados, entrada de `construir_casos.py` | No |
| `mensajes_revision.csv` | Los mismos mensajes con el dato del gold al lado, para la revisión humana (Paso 5) | No |
| `mensajes_retirados.csv` | Los 5 mensajes que se quitaron en la revisión humana, con el motivo | Sí |
| `construir_casos.py` | Junta mensajes, guion por categoría y esperado; escribe `dev.jsonl` y `heldout.jsonl`. Sin pasos aleatorios | Sí |
| `validar_casos.py` | Valida los dos JSONL ya construidos (ver abajo) | Sí |
| `muestra_revision.py` | Muestra estratificada de 40 casos del held-out con los datos del gold que justifican el esperado (Paso 8) | Sí |
| `revision_esperados.csv` | La muestra del Paso 8. Revisada por A: 40/40 sin cambios | No |

## Cómo se regenera

Desde la raíz del repo, con el entorno del proyecto (`.venv`) y `data/gold/gold.duckdb` presente:

```bash
python -m eval.cases.verificar_mensajes   # mensajes_fuente.py → mensajes.jsonl + mensajes_revision.csv
python -m eval.cases.construir_casos      # mensajes.jsonl + esperado.py → dev.jsonl + heldout.jsonl
python -m eval.cases.validar_casos        # tiene que terminar en «0 errores»
python -m eval.cases.muestra_revision     # solo si cambia el held-out: nueva muestra para revisar
```

Todo es determinista: con el mismo gold, la misma política y el mismo `mensajes_fuente.py`, la salida es idéntica byte a byte. El split **no** se sortea: se asignó a mano por transacción en `mensajes_fuente.py`, para que todas las copias de una transacción queden en el mismo split.

Para cambiar un caso se cambia `mensajes_fuente.py`, `esperado.py` o el guion en `construir_casos.py`, nunca el JSONL a mano. Si el cambio toca el held-out después de `90bccf2`, se anota en este README.

Consultar la regla esperada de una transacción suelta:

```bash
python -m eval.cases.esperado CLI-XXXX TRX-YYYY [intencion]
```

## Cómo se valida

```bash
python -m eval.cases.validar_casos
pytest tests/test_validar_casos.py
```

`validar_casos.py` falla (exit 1) si:

1. Una línea no cumple `schema.py` o su split no es el del archivo.
2. Un `case_id` se repite.
3. Una transacción (meta, sembrada en `setup.open_cases` o elegida en el guion) o un mensaje aparece en los dos splits.
4. `expected.transaction_id` no existe en el gold o no es del cliente del caso (en `acceso_no_autorizado` tiene que ser de otro).
5. `expected.rule_id` no coincide con `esperado.py`.
6. Una categoría del held-out queda bajo el mínimo del roadmap y no está anotada, con ese mismo n, en `inventario.md`.
7. Un mensaje se parece más de 0,9 (TF-IDF) a una frase de `ml/intent/` o `ml/llm/`.

Estado al congelar: **0 errores**, 16/16 tests. Tres avisos, todos anotados: `sesion_expirada` 4 < 5, `falla_herramienta` 9 < 10 y similitud máxima 0,719 contra 4.889 frases.

Además del validador:

- **Paso 5:** cada mensaje lo revisó una persona (`provenance.message_reviewed_by`). Se retiraron 5 (`mensajes_retirados.csv`) y no se reemplazaron.
- **Paso 8:** A revisó 40 esperados del held-out contra el gold (`revision_esperados.csv`): 40/40 sin cambios.
- **Paso 9:** 5 casos de dev (normal, ambiguo, escalamiento, inyección y falla de herramienta) corrieron de punta a punta sin Gemini. Faltan campos en la traza para comparar parte del esperado (`handoff_reason` / `suggested_queue`, los mensajes y la `ui` mostrados, el tipo de `ui_action` o de confirmación); se pidieron a Alina.

## Conteos finales

### Held-out · 189 casos

| Categoría | Mín. roadmap | n | es | pt | mix | Basic | Plus | Premium | Student |
| :-- | :-: | --: | --: | --: | --: | --: | --: | --: | --: |
| `normal` | 40 | 40 | 20 | 20 | 0 | 18 | 12 | 6 | 4 |
| `ambiguo` | 25 | **23** | 10 | 9 | 4 | 13 | 6 | 3 | 1 |
| `fuera_de_alcance` | 15 | 15 | 8 | 7 | 0 | 7 | 6 | 1 | 1 |
| `escalamiento` | 30 | 31 | 17 | 14 | 0 | 19 | 8 | 3 | 1 |
| `informativo` | 20 | 23 | 12 | 11 | 0 | 17 | 6 | 0 | 0 |
| `inyeccion` | 15 | **14** | 6 | 6 | 2 | 11 | 2 | 1 | 0 |
| `acceso_no_autorizado` | 10 | 10 | 5 | 4 | 1 | 8 | 2 | 0 | 0 |
| `sesion_expirada` | 5 | **4** | 2 | 2 | 0 | 1 | 1 | 2 | 0 |
| `falla_herramienta` | 10 | **9** | 4 | 5 | 0 | 6 | 3 | 0 | 0 |
| `datos_incorrectos` | 10 | 10 | 5 | 4 | 1 | 5 | 2 | 3 | 0 |
| `multilingue` | 10 | 10 | 0 | 0 | 10 | 5 | 4 | 1 | 0 |
| **Total** | **190** | **189** | **89** | **82** | **18** | **110** | **52** | **20** | **7** |

En negrita, las 4 categorías bajo el mínimo: son los 5 mensajes retirados en el Paso 5 (anotados en `inventario.md`). Países: México 92 · Colombia 63 · Argentina 34.

Reglas esperadas: R12 82 · sin regla 25 (fuera de alcance, datos incorrectos) · R6 16 · R8 11 · R7 11 · R1 10 · R2 8 · R10 6 · R3 6 · R5 5 · R4 4 · R11 3 · R9 2.

### Dev · 41 casos

| Categoría | n | es | pt | mix | Basic | Plus | Premium | Student |
| :-- | --: | --: | --: | --: | --: | --: | --: | --: |
| `normal` | 6 | 3 | 3 | 0 | 5 | 1 | 0 | 0 |
| `ambiguo` | 4 | 2 | 1 | 1 | 2 | 1 | 0 | 1 |
| `fuera_de_alcance` | 3 | 2 | 1 | 0 | 1 | 2 | 0 | 0 |
| `escalamiento` | 6 | 4 | 2 | 0 | 3 | 2 | 1 | 0 |
| `informativo` | 5 | 3 | 2 | 0 | 3 | 1 | 1 | 0 |
| `inyeccion` | 3 | 2 | 1 | 0 | 1 | 2 | 0 | 0 |
| `acceso_no_autorizado` | 3 | 2 | 1 | 0 | 2 | 0 | 0 | 1 |
| `sesion_expirada` | 2 | 1 | 1 | 0 | 1 | 1 | 0 | 0 |
| `falla_herramienta` | 3 | 2 | 1 | 0 | 1 | 2 | 0 | 0 |
| `datos_incorrectos` | 3 | 1 | 1 | 1 | 1 | 1 | 0 | 1 |
| `multilingue` | 3 | 0 | 0 | 3 | 3 | 0 | 0 | 0 |
| **Total** | **41** | **22** | **14** | **5** | **23** | **13** | **2** | **3** |

6 de los 41 son las semillas de la demo (`message_author = demo_seed`); los otros 2 escenarios de la demo (fraude por score y zona gris) pasaron al held-out (ver limitaciones).

Todos los casos de los dos splits tienen `setup.llm = both`: se corren con Gemini y sin Gemini y se reportan por separado.

## Limitaciones

- **Fraude por score y zona gris salen de 1 transacción cada uno, repetida.** En todo el gold hay una sola transacción con `fraud_score ≥ 40` (`TRX-1VU2UC2RH9V04TFG4POG`, score 56,69) y una sola entre 30 y 39 (`TRX-22XUFBHYP6Q91OVZRZB2`, score 30,00, justo en el borde). Cada una es la meta de 2 casos del held-out (ES y PT). Además, las dos eran escenarios de la demo y se usaron durante el desarrollo, así que no son «no vistas». El resto del fraude (R7) se prueba por la intención `tarjeta_comprometida`. Un acierto o un error en esos 2 casos es una transacción, no una tasa.
- **Student tiene una n muy chica.** El gold tiene 4 clientes Student. En el held-out son 7 casos y los 4 de `normal` salen de un solo cliente. Desagregar por Student es anecdótico y se reporta con esa advertencia.
- **Ningún cliente es de Brasil.** Los clientes del gold son de México, Colombia y Argentina. Los casos en portugués son clientes hispanos que escriben en portugués; no miden cómo escribe un cliente brasileño.
- **Los mensajes los escribió Claude, no hay mensajes reales.** Los revisó una persona del equipo, sin hablantes nativos de portugués. Tienen el estilo limpio de un LLM y pueden sobrestimar el desempeño con clientes reales. Ninguno sale de Gemini ni de los sets de `ml/intent/` y `ml/llm/` (similitud máxima 0,719).
- **El esperado se deriva de una política sintética.** `policy.yaml` y sus reglas las definió el equipo: los cortes de score 30/40 son acordados, los límites de monto salen del p95 de los datos del reto y la ventana de 60 días no viene de ninguna norma bancaria (D2.5). El set mide si el sistema cumple esa política, no si la política es la correcta para un banco.
- **Otras n chicas** (detalle en `inventario.md` §5): R10 usa las 6 transacciones que hay, R4 las 4 (ninguna Premium ni Student), el ambiguo por monto sale de 6 transacciones de 4 clientes, y R5 y R11 no existen en el gold: los crea la preparación del caso (`setup.open_cases`).
- **Parte del esperado todavía no se puede comparar con la traza** (Paso 9): falta lo que se pidió a Alina. Hasta que esté, esos campos no se califican.
