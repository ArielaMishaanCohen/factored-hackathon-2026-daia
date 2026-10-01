los mensajes y la ui mostrados, y el tipo de ui_action o de confirmación (ya pedidos a Alina)[los mensajes y la ui mostrados, y el tipo de ui_action o de confirmación (ya pedidos a Alina)]()

# Guía paso a paso · Fase 6.2 a 6.5 · Correr, calificar y reportar

**Dueños:** Ariela (B, ML) y Diego (A, Datos) · **Plan:** `docs/roadmap_fases_1_a_8.md` §6.2 a §6.5 · **Qué necesita del backend:** `docs/entregables_por_rol.md` §5.2 (Alina, rol C) · **Entrada:** el set de la 6.1 (`eval/cases/`, held-out congelado en el Paso 10 de `guia_fase_6_1_casos.md`)

> Cómo usar esta guía: igual que la de la 6.1, pero aquí cada paso dice **quién lo hace**: **[Ariela]**, **[Diego]** o **[Ambos]**. Busca los tuyos. Cada paso dice **qué es**, **qué haces tú** y **qué le escribes a Claude**. Marca la casilla `[x]` al terminar. Los pasos de mañana (9 a 12) son cortos a propósito: se detallan después de la primera corrida, cuando sepamos qué falló.

---

## Mapa (léelo una vez, 5 min)

### Quién hace qué

| Etapa del roadmap        | Qué es                                                               | Quién | Pasos |
| :----------------------- | :-------------------------------------------------------------------- | :----- | :---- |
| **6.2 · S**       | El runner: corre los casos contra nuestro sistema                     | Ariela | 2     |
| **6.2 · B0**      | Status quo: números históricos del gold (no es la misma carga)      | Diego  | 4     |
| **6.2 · B1**      | Bot de reglas: misma política, sin ML ni LLM, sobre los mismos casos | Diego  | 5     |
| **6.3 · Graders** | Califican cada caso con código leyendo la traza                      | Ariela | 3     |
| **6.3 · Handoff** | Completitud del handoff: los hechos coinciden con el gold             | Diego  | 6     |
| **6.4 · Errores** | Por qué falló cada caso del held-out                                | Ariela | 10    |
| **6.5 · Impacto** | Proyección de negocio, rotulada como tal                             | Diego  | 7     |
| **Reporte**        | `docs/eval_report.md`                                               | Ambos  | 12    |

### Qué va en paralelo y qué espera

```
Jueves 1 (hoy)                                                             feature freeze 20:00
───────────────────────────────────────────────────────────────────────────────────────────────
[Ambos]  Paso 0 · formato de salida + cómo es B1 ──┐
                                                  │
[Ariela] Paso 1 · 6.1 Pasos 10-12 (congelar) ─────┼─► Paso 2 · runner S ─► Paso 3 · graders ─┐
                                                  │                                          │
[Diego]  Paso 1b · data/runs al repo ─────────────┼─► Paso 4 · B0 ─► Paso 5 · B1 ────────────┤
                                                  └─► Paso 6 · handoff ─► Paso 7 · impacto ──┤
                                                                                             ▼
                                                        Paso 8 · depurar S y B1 en dev (Ariela)
                                                                                             ▼
                                                        Paso 9 · 1.ª corrida held-out (antes de 20:00)
Viernes 2                                                                           code freeze
───────────────────────────────────────────────────────────────────────────────────────────────
[Ariela] Paso 10 · errores (6.4)      [Diego] Paso 7 · impacto con la tasa real
[Ambos]  Paso 11 · 3 corridas finales ─► Paso 12 · eval_report.md ─► Paso 13 · subir
```

Lo que **espera** al otro:

1. **Todo espera al Paso 0.** B1 tiene que dejar su salida en el mismo formato que S para que los graders lo califiquen sin cambios.
2. **Calificar B1 espera a los graders** (Paso 3 de Ariela). Diego puede construir B1 antes.
3. **El Paso 8 espera a los Pasos 2, 3 y 5.**
4. **El 6.4 espera a la primera corrida** (Paso 9).
5. **El número final del 6.5 espera la tasa de resolución automática segura** de la corrida. Diego deja el cálculo listo con la tasa como parámetro.

### Tres reglas de oro

1. **Se depura en dev, se mide en held-out.** Todo arreglo del runner, de los graders o de B1 se prueba con `dev.jsonl`. El held-out solo se corre en el Paso 9 y en el 11.
2. **Si se cambia el sistema después de mirar el held-out, se declara.** El roadmap prevé correcciones entre la primera corrida (jueves) y las finales (viernes). Son válidas, pero el reporte muestra **los dos números** (primera corrida y final) y la lista de cambios. Así no se presenta como «nunca visto» algo que se ajustó mirando.
3. **Todo se califica con código desde la salida del runner.** Nada de «se ve bien». Si algo no se puede calificar con código, va como limitación, no como métrica.

---

## Paso 0 · [Ambos] Formato de salida y cómo es B1 (20 min, antes de separarse)

**Qué es:** lo único que conecta el trabajo de los dos. El runner escribe un archivo por corrida; los graders, el reporte y el impacto lo leen. B1 escribe **lo mismo**. Si esto cambia después, se rompe todo lo de abajo.

**La propuesta (revísenla juntos):**

- Cada corrida escribe `eval/reports/<run_id>/` con:
  - `manifest.json`: sistema (`S` | `B1`), configuración (`with_gemini` | `without_gemini`), número de corrida (1–3), split, hash del commit, hash del held-out, versiones (política, modelo de intención, modelo LLM, `data_run`) y hora.
  - `results.jsonl`: **una línea por caso**: `case_id`, los turnos (petición, código HTTP, `ChatResponse`), la traza completa, los casos (`GET /cases`), los handoffs completos, las banderas (`identification_failed`, `max_turns_reached`), latencia y costo.
- Los graders escriben `grades.jsonl` (un veredicto por caso y por campo) y `metrics.json` (números con numerador, denominador y n).

**Cómo es B1 (decidir hoy):**

| Opción                   | Qué es                                                                                                                                                                    | A favor                                                                       | En contra                                                                                                 |
| :------------------------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------------- |
| **A (recomendada)** | El mismo backend con el NLU forzado a palabras clave (`nlu/stub.py`) y sin Gemini. Se activa con una variable, por ejemplo `NLU_MODE=keywords`, que se le pide a Alina | Corre con el mismo runner y la misma traza: comparación limpia. Poco trabajo | Comparte el orquestador con S: mide lo que aportan el ML y el LLM, no el orquestador. Se declara          |
| B                         | Un bot aparte en`eval/baselines/rules_bot.py` que usa las herramientas y la política directo, con un formulario fijo (pide monto, fecha y comercio)                     | Más fiel a «formulario fijo»                                               | Tiene que fabricar la misma salida que S, con su traza. Mucho más trabajo y más riesgo antes del freeze |

**Escríbele a Claude (Ariela):**

```
Paso 0 de docs/Rol B - ML/guia_fase_6_2_a_6_5.md. Escribe
eval/FORMATO_RESULTADOS.md con el formato de salida del runner (manifest.json,
results.jsonl, grades.jsonl, metrics.json), un ejemplo de cada uno armado con
la salida real de dev-normal-001, y un modelo Pydantic en eval/formato.py.
Agrega una sección "B1" con la opción que elegimos con Diego: [A o B].
Si es A, escríbeme el mensaje para Alina con la variable que necesitamos.
```

- [X] Formato acordado entre los dos (`eval/FORMATO_RESULTADOS.md`)
- [X] B1: opción **A** (si es A, pedido a Alina)

---

## Paso 1 · [Ariela] Terminar la 6.1 (30 min)

Pasos 10, 11 y 12 de `guia_fase_6_1_casos.md`: congelar el held-out, README + D6.1 y subir. **Nada del Paso 2 en adelante toca el held-out hasta que esté el commit del Paso 10.**

- [X] Held-out congelado (hash: `90bccf2`)

## Paso 1b · [Diego] `data/runs/` de vuelta en el repo (15 min)

**Qué es:** el commit «revisión datos» sacó `data/runs/` del repo. En un clon limpio fallan `construir_casos.py` (necesita `demo_scenarios.json` y `manifest.json`), el reporte (que separa los casos con transacciones de la demo) y el 6.5 (`metricas_problema.json`). Los `manifest.json` pesan ~5 MB cada uno; los demás son chicos.

**Qué haces tú:** decide una de dos:

1. Volver a versionar los archivos chicos de la corrida que usa el set (`20260929T234658Z-7cf922c1`): `demo_scenarios.json`, `metricas_problema.json`, `policy_calibration.json`, `backend_acceptance.json` y `policy.yaml`, con excepciones `!` en `.gitignore`. El `manifest.json` puede quedar fuera si Ariela cambia `construir_casos.py` para que no lo pida.
2. O documentar en el README cómo se regenera todo con `make data`, y probarlo desde un clon limpio.

**Escríbele a Claude (Diego):**

```
Paso 1b de docs/Rol B - ML/guia_fase_6_2_a_6_5.md. Quiero volver a versionar
solo los archivos chicos de data/runs/20260929T234658Z-7cf922c1/ (todo menos
manifest.json) con excepciones en .gitignore. Muéstrame el cambio a
.gitignore y verifica con git status que no entre nada pesado ni de data/gold/.
```

**Avísale a Ariela** si el `manifest.json` queda fuera: ella cambia `ultima_corrida()` en `construir_casos.py` para que busque `demo_scenarios.json`.

- [ ] `data/runs` resuelto (opción ____)

---

## Paso 2 · [Ariela] El runner de S (60 min)

**Qué es:** `eval/runner.py`, el que llama `make eval`. Parte de la prueba de humo del Paso 9 de la 6.1 (`humo_paso9.py`, en el scratchpad de Claude), que ya implementa las reglas de respuesta, las fallas y la base limpia.

**Qué le falta a la prueba de humo:** `setup.open_cases` (sembrar casos para R5 y R11), `expire_session` (con y sin `resume`), la confirmación por texto (`via = text`), las dos configuraciones (`with_gemini`, `without_gemini`), las 3 corridas y escribir el formato del Paso 0.

**Escríbele a Claude:**

```
Paso 2 de la guía de la 6.2-6.5. Escribe eval/runner.py a partir de
humo_paso9.py del Paso 9 de la 6.1, con el formato de eval/FORMATO_RESULTADOS.md.
Implementa todas las reglas de respuesta de eval/cases/SCHEMA.md §1.3, siembra
setup.open_cases, expira la sesión según setup.expire_session, y corre por
configuración de LLM según setup.llm. Argumentos: --split (dev por defecto),
--system (S | B1), --llm, --runs, --cases (para correr unos pocos). Que
make eval corra el held-out completo. Base operativa limpia entre casos y
OPS_DB_PATH en memoria. Córrelo sobre dev sin Gemini y muéstrame cuántos casos
terminaron, cuántos llegaron a max_turns y cuántos dieron error.
```

- [X] `eval/runner.py` corre todo dev sin errores del runner

---

## Paso 3 · [Ariela] Los graders (60 min)

**Qué es:** `eval/graders.py`. Lee `results.jsonl` y compara cada campo del esperado y cada `forbidden` contra la traza (SCHEMA.md §1.4 y §1.5). Después calcula las métricas del roadmap §6.3.

| Métrica (roadmap §6.3)       | Numerador ÷ denominador                                                                                                            |
| :----------------------------- | :---------------------------------------------------------------------------------------------------------------------------------- |
| Resolución automática segura | casos en alcance con todos los campos correctos, 0 prohibidos y sin handoff ÷ casos en alcance (+ % donde se intentó automatizar) |
| Contención                    | casos sin handoff ÷ total (se aclara que no prueba resolución)                                                                    |
| Calidad de escalamiento        | escalamientos faltantes y escalamientos innecesarios contra`should_escalate` (+ completitud del handoff, Paso 6)                  |
| Resultados inseguros           | conteo por tipo de`forbidden` ÷ casos donde aplica (0/N no prueba riesgo cero)                                                   |
| Eficiencia                     | latencia p50/p95 por turno y por caso; costo por caso intentado y por resolución exitosa («no definido» si no hay éxitos)       |
| Desagregación                 | todo lo anterior por idioma y por segmento, con advertencia si n < 10                                                               |
| Variabilidad                   | media y rango de las 3 corridas                                                                                                     |

**Escríbele a Claude:**

```
Paso 3 de la guía de la 6.2-6.5. Escribe eval/graders.py: un grader por cada
campo de expected y por cada valor de forbidden (eval/cases/SCHEMA.md §1.4 y
§1.5), que lea results.jsonl y escriba grades.jsonl y metrics.json según
eval/FORMATO_RESULTADOS.md. Calcula las métricas de la tabla del Paso 3 con
numerador, denominador y n, desagregadas por idioma, segmento y categoría.
Deja un punto para enchufar el grader de handoff de Diego
(eval/graders_handoff.py). Agrega tests en tests/ con resultados armados a
mano: un caso perfecto, uno con la transacción equivocada, uno con acción sin
confirmación y uno con "registré" sin ActionRecord. Córrelo sobre la salida de
dev del Paso 2 y muéstrame la tabla.
```

- [X] `eval/graders.py` con tests en verde
- [X] Métricas de dev sin Gemini: resolución automática segura 12 / 38

---

## Paso 4 · [Diego] B0 · status quo (30 min)

**Qué es:** la línea base histórica: hoy todo va a un humano. Sale de la tabla `baseline_metrics` del gold (FCR por categoría, días de resolución, SLA incumplido) y se rotula **«no es la misma carga»**: son datos históricos de todos los contactos, no nuestros casos.

**Escríbele a Claude (Diego):**

```
Paso 4 de docs/Rol B - ML/guia_fase_6_2_a_6_5.md. Escribe
eval/baselines/status_quo.py, que lea baseline_metrics de data/gold/gold.duckdb
y escriba eval/reports/b0.json con: FCR de la categoría Queja y global, días
de resolución (media y mediana) de las disputas, % de SLA incumplido, cada uno
con numerador, denominador y la nota "datos históricos, no es la misma carga
que el set de evaluación". Muéstrame los números.
```

- [ ] `eval/reports/b0.json` listo

---

## Paso 5 · [Diego] B1 · bot de reglas (45-60 min)

**Qué es:** el baseline que **sí** corre sobre los mismos casos. Depende de lo que eligieron en el Paso 0.

- **Opción A:** cuando Alina agregue la variable, B1 es `python -m eval.runner --system B1`. Tu trabajo es verificar que de verdad no use ML ni LLM (en la traza: `extractor = rules`, intención del stub, `cost_usd = 0`) y escribir en `eval/baselines/README.md` qué es B1 y qué comparte con S.
- **Opción B:** escribir `eval/baselines/rules_bot.py`, que produzca `results.jsonl` en el formato del Paso 0.

**Escríbele a Claude (Diego):**

```
Paso 5 de la guía de la 6.2-6.5. Elegimos la opción [A o B] para B1.
[A] Corre python -m eval.runner --system B1 --split dev y verifica en la traza
que ningún turno use el clasificador entrenado ni Gemini. Escribe
eval/baselines/README.md explicando B0 y B1 y qué comparte B1 con S.
[B] Escribe eval/baselines/rules_bot.py con palabras clave, formulario fijo
(pide monto, fecha y comercio) y la misma política, que escriba results.jsonl
según eval/FORMATO_RESULTADOS.md.
```

- [ ] B1 corre sobre dev y pasa por los graders

---

## Paso 6 · [Diego] Grader de completitud del handoff (30 min)

**Qué es:** el roadmap pide «completitud del handoff (campos obligatorios presentes y hechos correctos, verificado con código)». Cada `HandoffPackage` trae `verified_facts` (hecho, valor y fuente): hay que cruzarlos contra el gold. Va en su propio archivo para no editar el mismo que Ariela.

**Escríbele a Claude (Diego):**

```
Paso 6 de la guía de la 6.2-6.5. Escribe eval/graders_handoff.py con una
función que reciba un HandoffPackage (backend/app/schemas.py) y el case_id, y
devuelva: campos obligatorios presentes (design.md §5), y para cada
verified_fact si su valor coincide con data/gold/gold.duckdb según su source.
Pruébalo con los handoffs de la salida de dev del Paso 2. Tests en tests/.
```

- [ ] `eval/graders_handoff.py` con tests en verde

---

## Paso 7 · [Diego] Impacto de negocio, 6.5 (30 min hoy + 10 min mañana)

**Qué es:** volumen anual de disputas × tasa de resolución automática segura (medida offline) × AHT ahorrado. Sale de `metricas_problema.json` (disputas, duración media de los contactos de queja). Siempre rotulado **«proyección offline, no medición en producción»**.

**Hoy:** el cálculo con la tasa como parámetro. **Mañana:** se corre con la tasa del held-out (Paso 11) y con su rango entre corridas.

**Escríbele a Claude (Diego):**

```
Paso 7 de la guía de la 6.2-6.5. Escribe eval/impacto.py que lea
metricas_problema.json de data/runs/ y, dada una tasa de resolución
automática segura (parámetro, con mínimo y máximo), calcule: disputas al año
que se resolverían sin humano, horas de agente ahorradas (con la duración
media de los contactos de queja) y casos que hoy quedan abiertos o vencen el
SLA. Escribe cada supuesto con su fuente. Rotula todo como "proyección
offline". Pruébalo con tasa 0,30 a 0,40.
```

- [ ] Cálculo listo (falta la tasa real)
- [ ] Con la tasa real del Paso 11

---

## Paso 8 · [Ariela] Depurar S y B1 en dev (30 min)

**Qué es:** correr todo de punta a punta en dev (S con y sin Gemini, y B1) y arreglar lo que falle **en el runner o en los graders**. Si falla el sistema, se anota para el 6.4 o se le pasa a Alina; no se ajusta el set.

**Escríbele a Claude:**

```
Paso 8 de la guía de la 6.2-6.5. Corre el runner sobre dev para S
(with_gemini y without_gemini) y B1, una corrida cada uno, y los graders.
Separa: errores del runner o de los graders (arréglalos), fallas del sistema
(lista con caso, campo y traza) y casos donde el esperado parece mal (no lo
cambies: dime por qué). Dime cuánto costó la corrida con Gemini y estima el
costo de 3 corridas del held-out.
```

- [ ] Dev corre limpio para S y B1
- [ ] Costo estimado de las 3 corridas del held-out: ____ USD

---

## Paso 9 · [Ariela] Primera corrida del held-out (antes de las 20:00)

**Qué es:** `make eval`, una corrida por sistema y configuración. **Solo después del commit del held-out (Paso 1).** No se cambia nada mirando estos números antes de anotarlos.

```
Paso 9 de la guía de la 6.2-6.5. Verifica que heldout.jsonl coincide con el
commit del Paso 10 de la 6.1. Corre make eval (S con y sin Gemini, B1; una
corrida) y los graders. Guarda la salida como "primera corrida" y muéstrame
la tabla principal sin interpretarla todavía.
```

- [ ] Primera corrida (run_id: `________`). Resolución automática segura S: ____ · B1: ____

---

## Pasos de mañana (se detallan después del Paso 9)

### Paso 10 · [Ariela] Análisis de errores, 6.4

Cada falla del held-out se clasifica: NLU, identificación de transacción, política, herramienta o redacción. Se eligen 5–10 ejemplos con su traza para el reporte y una slide. Lo que se arregle en el sistema se anota (regla de oro 2).

### Paso 11 · [Ambos] 3 corridas finales

S con y sin Gemini, y B1: 3 corridas cada uno, con media y rango. Diego corre el 6.5 con la tasa resultante.

### Paso 12 · [Ambos] `docs/eval_report.md`

- **Ariela:** métricas, desagregación por idioma y segmento, variabilidad, errores y la comparación primera corrida → final.
- **Diego:** B0, B1, impacto de negocio y limitaciones de datos: los 4 casos con transacciones de la demo (R7 por score y R9), Student con n chica, ningún cliente de Brasil, política sintética.
- **Los dos:** versiones de modelo, prompts, política y datos (sale del `manifest.json` de cada corrida).

### Paso 13 · [Ariela] Subir y marcar la Fase 6

Commit de `eval/` y `docs/eval_report.md`, sin `data/` ni `.env`. Marcar en el roadmap la Fase 6 cuando `make eval` corra los 3 sistemas.

---

## Si te trabas

| Te pasa esto                               | Escríbele a Claude                                                                                           |
| :----------------------------------------- | :------------------------------------------------------------------------------------------------------------ |
| El runner se cuelga o se queda en un bucle | "El caso X llega a max_turns. Muéstrame los turnos y dime qué regla de respuesta se aplicó en cada uno"    |
| Un grader da algo raro                     | "El grader de [campo] marca mal el caso X. Muéstrame el esperado, lo que leyó de la traza y por qué"       |
| B1 no sale en el mismo formato             | "Compara la salida de B1 y de S para el caso X contra eval/formato.py y dime qué falta"                      |
| Gemini da 429 o se acaba la cuota          | "Agrega reintentos con espera al runner solo para errores de cuota y dime cuántos casos quedaron sin correr" |
| Un número parece demasiado bueno          | "Verifica a mano 5 casos que el grader marcó como correctos: el esperado, la traza y el veredicto"           |

---

## Decisiones de esta guía (1-oct, revísalas antes de empezar)

1. **Un solo formato de salida para S y B1** (Paso 0). Los graders no saben qué sistema calificaron.
2. **B1 recomendado = mismo backend con NLU de palabras clave y sin LLM.** Mide lo que aportan el ML y el LLM sobre la misma política y el mismo orquestador; se declara que no mide el orquestador.
3. **B2 (LLM sin capa de control) queda fuera.** Es opcional en el roadmap y no hay tiempo antes del freeze.
4. **Se reportan la primera corrida y la final.** Las correcciones entre las dos se listan.
5. **El grader de handoff va aparte** (`eval/graders_handoff.py`) para que los dos no editen el mismo archivo.
