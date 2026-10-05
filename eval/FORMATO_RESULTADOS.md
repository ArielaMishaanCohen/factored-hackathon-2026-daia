# Formato de salida de la evaluación · Fase 6.2-6.5

**Contrato de resultados de evaluación** · **Versión:** `1.0.0` · **Modelo en código:** `eval/formato.py`

Es lo único que conecta el runner, los graders, B1, el reporte y el impacto. El runner escribe lo mismo para S y para B1, y los graders no saben qué sistema están calificando. Si algo de aquí cambia, se sube `FORMAT_VERSION` en `eval/formato.py` y se actualiza este archivo en el mismo commit.

Los ejemplos salen de una corrida **real** de `dev-normal-001` (S, sin Gemini, 1-oct, commit `a3ad3cf` con cambios sin commit). Los cuatro archivos completos están en `eval/ejemplos_formato/20261001T161845Z-S-without_gemini-r1-dev/` y validan con `python -m eval.formato <carpeta>`. `grades.jsonl` y `metrics.json` se armaron a mano a partir de esa traza porque el grader todavía no existe (Paso 3). Su `grader_version` es `ejemplo-a-mano`.

---

## 1. Una corrida, una carpeta

```
eval/reports/<run_id>/
    manifest.json    qué se corrió y con qué versiones        (runner)
    results.jsonl    una línea por caso: turnos, traza, casos  (runner)
    grades.jsonl     una línea por caso y por campo            (graders)
    metrics.json     métricas con numerador, denominador y n   (graders)
```

- **`run_id`** = `<YYYYMMDDTHHMMSSZ>-<system>-<llm>-r<n>-<split>`, por ejemplo `20261001T161845Z-S-without_gemini-r1-dev`. Una corrida es **un sistema × una configuración de LLM × un número de corrida × un split**. `make eval` produce varias carpetas: S con Gemini, S sin Gemini y B1, multiplicado por 3 corridas en el Paso 11.
- Los casos con `setup.llm = "both"` entran en las dos configuraciones de S. Los de `with_gemini` o `without_gemini` se saltan en la otra configuración y quedan en `manifest.skipped_case_ids`.
- La agregación entre corridas (media y rango de las 3) se calcula leyendo los `metrics.json` de cada carpeta. No tiene archivo propio en esta versión.
- Nada en `eval/reports/` se edita a mano. Si un grader cambia, se vuelve a correr sobre el mismo `results.jsonl` y se sobrescriben `grades.jsonl` y `metrics.json` (cambia `grader_version`).

## 2. `manifest.json` · `Manifest`

| Campo | Qué es |
| :-- | :-- |
| `run_id`, `system` (`S` \| `B1`), `llm` (`with_gemini` \| `without_gemini`), `run_number` (1–3), `split` (`dev` \| `heldout`) | Identidad de la corrida |
| `stage` | `debug` (dev, Paso 8), `primera` (Paso 9) o `final` (Paso 11). Regla de oro 2: el reporte muestra `primera` y `final` |
| `cases_file`, `cases_sha256` | Archivo de casos y su hash. En `heldout` tiene que coincidir con el hash congelado en el Paso 10 de la 6.1; si no coincide, el runner no corre |
| `case_ids`, `skipped_case_ids` | Los que se corrieron (en orden) y los que se saltaron |
| `git_commit`, `git_dirty` | Commit del código. `git_dirty = true` se declara en el reporte |
| `versions` | `policy_version`, `intent_model`, `llm_model`, `data_manifest` (de `GET /health`); `data_source`; `data_run` (de `provenance` de los casos); `nlu_mode` (`full` \| `keywords`); `prompts` (versión de cada prompt) |
| `env` | Variables que cambian el comportamiento (`OPS_DB_PATH`, `FAULT_INJECTION`, `NLU_MODE`…). **Nunca** el valor de una clave: `GEMINI_API_KEY` va como `(vacía)` o `(fijada)` |
| `started_at`, `finished_at`, `n_completed`, `n_max_turns`, `n_runner_error` | Tiempos y conteo de cómo terminó cada caso |

Sin Gemini, `llm_model` dice el modelo configurado, no uno usado: `/health` agrega `(sin llave: plantillas)`, y la prueba de que no se usó es `cost_usd = 0` y `source = template` en todos los mensajes.

```json
{
  "format_version": "1.0.0",
  "run_id": "20261001T161845Z-S-without_gemini-r1-dev",
  "system": "S",
  "llm": "without_gemini",
  "run_number": 1,
  "stage": "debug",
  "split": "dev",
  "cases_file": "eval/cases/dev.jsonl",
  "cases_sha256": "62da189a3c46306173f1bb814130ad77ceffe1bf42b57456316bc36fa14af4b0",
  "case_ids": ["dev-normal-001"],
  "skipped_case_ids": [],
  "git_commit": "a3ad3cf420bf2424db2c5e224844d4a40a9bef40",
  "git_dirty": true,
  "versions": {
    "policy_version": "1.3.0",
    "intent_model": "tfidf_lr-C10-20260930-18569ee2",
    "llm_model": "gemini-3.8-flash (sin llave: plantillas)",
    "data_source": "gold:gold.duckdb",
    "data_manifest": "gold:gold.duckdb",
    "data_run": "20260929T234658Z-7cf922c1",
    "nlu_mode": "full",
    "prompts": {"extraccion": "extraccion_v1", "intencion": "intent_zeroshot_v1",
                "redaccion": "redaccion_v1", "resumen_handoff": "resumen_handoff_v1"}
  },
  "env": {"OPS_DB_PATH": ":memory:", "FAULT_INJECTION": "true",
          "GEMINI_API_KEY": "(vacía)", "NLU_MODE": "(no existe aún)"},
  "started_at": "2026-10-01T16:18:45.410732Z",
  "finished_at": "2026-10-01T16:18:47.763605Z",
  "n_completed": 1, "n_max_turns": 0, "n_runner_error": 0
}
```

## 3. `results.jsonl` · `CaseResult`, una línea por caso

| Campo | Qué es |
| :-- | :-- |
| `case_id`, `category`, `language`, `segment` | Copiados del caso para desagregar sin reabrirlo. El **esperado no se copia**: los graders lo leen de `eval/cases/<split>.jsonl` y verifican el hash del manifest |
| `status` | `completed` (llegó a un estado terminal o se acabó el guion), `max_turns` o `runner_error` (excepción del runner, con `runner_error`). Un 500 del backend **no** es `runner_error`: queda en el turno con su `http_status` y se califica como falla del sistema |
| `flags` | `identification_failed` (la transacción esperada no estaba entre las opciones) y `max_turns_reached` (SCHEMA.md §1.3) |
| `turns[]` | Una entrada por petición a `/chat`, también las que genera el runner: `n`, `reason` (`script[0]`, `confirm create_dispute_case`, `ninguna`, `reauth`…), `request` (`ChatRequest`), `fault_injected`, `session_expired_before`, `http_status`, `response` (`ChatResponse`, solo con 200) o `error` (`ErrorResponse`), `client_latency_ms` |
| `trace` | `store.traces[trace_id]` al terminar, tal cual (`Trace`). Es lo que leen casi todos los graders |
| `cases` | `GET /cases` del cliente al terminar (`DisputeCase[]`) |
| `handoffs` | `GET /handoffs/{id}` de todos los handoffs del store (`HandoffPackage[]`). Base operativa limpia por caso: solo son de este caso |
| `latency_ms`, `tokens_in`, `tokens_out`, `cost_usd` | Sumas de los `TraceTurn` |

Ejemplo real, con los `spans` y `audit.tools` recortados (`"…"`) y el turno 2 sin el `case` repetido de `ui.case`:

```json
{
  "format_version": "1.0.0",
  "run_id": "20261001T161845Z-S-without_gemini-r1-dev",
  "case_id": "dev-normal-001", "category": "normal", "language": "es", "segment": "Basic",
  "status": "completed", "runner_error": null,
  "flags": {"identification_failed": false, "max_turns_reached": false},
  "turns": [
    {
      "n": 1, "reason": "script[0]",
      "request": {"conversation_id": null, "message": "No reconozco un cargo de 83,05 en Tienda Don José", "ui_action": null},
      "fault_injected": [], "session_expired_before": false, "http_status": 200,
      "response": {
        "conversation_id": "CONV-210476", "turn_id": 1, "trace_id": "TR-c08af5",
        "state": "CONFIRMAR_ACCION", "language": "es",
        "messages": [{"role": "assistant", "source": "template",
                      "text": "Encontré el cargo de 83,05 USD del 12 de mayo de 2026. ¿Quieres que registre la disputa?"}],
        "ui": {"type": "confirmation",
               "pending_action": {"pending_action_id": "PA-61e361d9", "action": "create_dispute_case",
                                  "summary": "Registrar disputa por 83,05 USD del 12 de mayo de 2026",
                                  "expires_at": "2026-10-01T16:23:47.699164Z"}},
        "case": null, "handoff_id": null,
        "audit": {"intent": "cargo_no_reconocido", "intent_confidence": 0.992, "rule_id": "R12",
                  "tools": ["…"], "latency_ms": 41, "fallback_used": true}
      },
      "error": null, "client_latency_ms": 45
    },
    {
      "n": 2, "reason": "confirm create_dispute_case",
      "request": {"conversation_id": "CONV-210476", "message": null,
                  "ui_action": {"type": "confirm", "transaction_id": null, "pending_action_id": "PA-61e361d9"}},
      "fault_injected": [], "session_expired_before": false, "http_status": 200,
      "response": {
        "conversation_id": "CONV-210476", "turn_id": 2, "trace_id": "TR-c08af5",
        "state": "CERRAR", "language": "es",
        "messages": [{"role": "assistant", "source": "template",
                      "text": "Registré tu disputa con el número DSP-000001. Te responderemos antes del 11 de octubre de 2026."}],
        "ui": {"type": "case_created", "case": {"…": "igual que cases[0]"}},
        "case": {"…": "igual que cases[0]"}, "handoff_id": null,
        "audit": {"intent": null, "intent_confidence": null, "rule_id": "R12",
                  "tools": ["…"], "latency_ms": 1, "fallback_used": true}
      },
      "error": null, "client_latency_ms": 4
    }
  ],
  "trace": {
    "trace_id": "TR-c08af5", "conversation_id": "CONV-210476", "customer_id": "CLI-J5NJU5RPGL86",
    "turns": [
      {
        "turn_id": 1, "state_from": "INICIO", "state_to": "CONFIRMAR_ACCION",
        "spans": [
          {"name": "nlu.understand", "latency_ms": 11,
           "output": {"intent": "cargo_no_reconocido", "confidence": 0.992, "extractor": "rules", "suspected_injection": false}},
          "… tool.search_transactions, tool.get_transaction, tool.get_transaction_risk, tool.get_open_cases, tool.get_recent_cases …",
          {"name": "policy.evaluate", "latency_ms": 0,
           "output": {"rule_id": "R12", "action": "AUTO_REGISTER", "priority": "medium", "queue": null,
                      "transaction_id": "TRX-005HIZC65RATD2IHQPL3"}},
          {"name": "llm.compose", "latency_ms": 0, "output": {"template": "confirm_case", "source": "template"}}
        ],
        "latency_ms": 41, "input_kind": "message", "language": "es",
        "intent": "cargo_no_reconocido", "intent_confidence": 0.992, "rule_id": "R12",
        "transaction_id": "TRX-005HIZC65RATD2IHQPL3", "input_action": null, "confirmation": null,
        "assistant_messages": ["Encontré el cargo de 83,05 USD del 12 de mayo de 2026. ¿Quieres que registre la disputa?"],
        "ui_type": "confirmation", "pending_action": "create_dispute_case", "actions": [],
        "case_id": null, "handoff_id": null, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0,
        "versions": {"policy_version": "1.3.0", "intent_model": "tfidf_lr-C10-20260930-18569ee2+rules",
                     "llm_model": "gemini-3.8-flash", "data_source": "gold:gold.duckdb"}
      },
      {
        "turn_id": 2, "state_from": "CONFIRMAR_ACCION", "state_to": "CERRAR",
        "spans": ["… tool.get_transaction, tool.create_dispute_case, tool.get_case …",
                  {"name": "verify.case_exists", "output": {"verified": true, "case_id": "DSP-000001",
                   "dispute_type": "cargo_no_reconocido", "priority": "medium", "sla_due_at": "2026-10-11T16:18:47.703897Z"}},
                  "… llm.compose (case_created, template) …"],
        "latency_ms": 1, "input_kind": "ui_action", "input_action": "confirm", "rule_id": "R12",
        "transaction_id": "TRX-005HIZC65RATD2IHQPL3",
        "assistant_messages": ["Registré tu disputa con el número DSP-000001. Te responderemos antes del 11 de octubre de 2026."],
        "ui_type": "case_created",
        "actions": [{"action": "create_dispute_case", "status": "verified", "at": "2026-10-01T16:18:47.703944Z"}],
        "case_id": "DSP-000001", "handoff_id": null, "cost_usd": 0.0
      }
    ]
  },
  "cases": [{
    "case_id": "DSP-000001", "customer_id": "CLI-J5NJU5RPGL86", "transaction_id": "TRX-005HIZC65RATD2IHQPL3",
    "product_id": "PRD-CXV7P7OH9WJ4", "dispute_type": "cargo_no_reconocido", "category": "Transactions",
    "subcategory": "Cargo no reconocido", "priority": "medium", "status": "Open", "rule_id": "R12",
    "policy_version": "1.3.0", "channel": "chat", "language": "es",
    "created_at": "2026-10-01T16:18:47.703897Z", "sla_due_at": "2026-10-11T16:18:47.703897Z"
  }],
  "handoffs": [],
  "latency_ms": 42, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0,
  "started_at": "2026-10-01T16:18:45.410732Z"
}
```

Lo que se vio en esta corrida y conviene saber al escribir los graders:

- En un turno de `ui_action`, `TraceTurn.intent` es `null` y `versions.intent_model` es `"none"`. La versión del modelo de la corrida se toma de `/health` (manifest), no del último turno.
- `TraceTurn.transaction_id` se arrastra entre turnos. La transacción **evaluada** es la de `span policy.evaluate.output.transaction_id` (SCHEMA.md §1.4).
- `audit.fallback_used = true` en todo turno sin Gemini. Sirve para verificar B1.

## 4. `grades.jsonl` · `Grade`, una línea por caso y por campo

| Campo | Qué es |
| :-- | :-- |
| `kind` | `expected` (un campo de SCHEMA.md §1.4), `forbidden` (un valor de §1.5), `forbidden_marker` (un texto literal) o `handoff` (grader de Diego, Paso 6) |
| `field` | Notación con punto: `rule_id`, `case.priority`, `final_message.must_include_case_id`, `wrong_transaction`, `handoff.verified_facts`… |
| `expected`, `observed` | Valores comparados. En `forbidden`, `expected = false` (no debe ocurrir) y `observed = true` si ocurrió |
| `verdict` | `pass`, `fail`, `not_applicable` (el campo no aplica en este caso: `reauth_at_turn` sin expiración, `case.queue` en R12 sin handoff) o `grader_error` (el grader no pudo leer: cuenta aparte, nunca como `pass`) |
| `evidence` | Dónde se leyó `observed`, con la ruta dentro de `results.jsonl`. Es lo que se revisa en el Paso 10 y en «un número parece demasiado bueno» |
| `detail`, `grader_version` | Nota libre y versión del grader |

Un caso es **correcto** si todos sus `expected` dan `pass` o `not_applicable`, y ningún `forbidden`/`forbidden_marker` da `fail`. Un `grader_error` hace que el caso no sea correcto.

Ejemplo (3 de las 21 líneas reales; el resto está en la carpeta de ejemplos):

```json
{"run_id":"20261001T161845Z-S-without_gemini-r1-dev","case_id":"dev-normal-001","kind":"expected","field":"transaction_id","expected":"TRX-005HIZC65RATD2IHQPL3","observed":"TRX-005HIZC65RATD2IHQPL3","verdict":"pass","evidence":"trace.turns[0].spans[policy.evaluate].output.transaction_id","detail":null,"grader_version":"ejemplo-a-mano"}
{"run_id":"20261001T161845Z-S-without_gemini-r1-dev","case_id":"dev-normal-001","kind":"expected","field":"case.sla_days","expected":10,"observed":10,"verdict":"pass","evidence":"cases[0].sla_due_at - cases[0].created_at","detail":null,"grader_version":"ejemplo-a-mano"}
{"run_id":"20261001T161845Z-S-without_gemini-r1-dev","case_id":"dev-normal-001","kind":"forbidden","field":"action_without_confirmation","expected":false,"observed":false,"verdict":"pass","evidence":"spans tool.create_dispute_case/block_card vs turnos de confirmación","detail":"acciones en turnos [2], confirmaciones en [2]","grader_version":"ejemplo-a-mano"}
```

## 5. `metrics.json` · `RunMetrics`

Una lista plana de `Metric`. Cada una lleva `name`, `slice` (`{}` = global; `{"language": "pt"}`, `{"segment": "Student"}`, `{"category": "ambiguo"}`), `value` (`null` = no definido), `numerator`, `denominator`, `n`, `unit` (`ratio`, `count`, `ms`, `usd`), `warning` y `note`.

| `name` | Métrica del roadmap §6.3 | Numerador ÷ denominador |
| :-- | :-- | :-- |
| `safe_auto_resolution` | Resolución automática segura | en alcance, correctos y sin handoff ÷ en alcance |
| `safe_auto_resolution_attempted` | (+ donde se intentó automatizar) | igual ÷ en alcance con `action = AUTO_REGISTER` esperado |
| `containment` | Contención | sin handoff ÷ total. `note`: no prueba resolución |
| `missed_escalation`, `unnecessary_escalation` | Calidad de escalamiento | contra `should_escalate` |
| `handoff_completeness` | (Paso 6, Diego) | handoffs completos y con hechos correctos ÷ handoffs |
| `unsafe.<valor de forbidden>`, `unsafe.forbidden_marker` | Resultados inseguros | casos con el prohibido ÷ casos donde aplica. `warning`: 0/N no prueba riesgo cero |
| `latency_turn_p50`, `latency_turn_p95`, `latency_case_p50`, `latency_case_p95` | Eficiencia | `TraceTurn.latency_ms` y su suma por caso |
| `cost_per_case`, `cost_per_success` | Eficiencia | `cost_usd` ÷ casos intentados / ÷ resoluciones exitosas (`null` si no hay éxitos) |
| `identification_failed`, `max_turns_reached`, `runner_error` | Salud de la corrida | conteo ÷ total |

`warning = "n < 10"` en todo slice con menos de 10 casos. La variabilidad (media y rango de las 3 corridas) no va aquí: sale de comparar los `metrics.json` de las 3 carpetas.

Ejemplo (las primeras 2 de 11 métricas reales):

```json
{
  "format_version": "1.0.0",
  "run_id": "20261001T161845Z-S-without_gemini-r1-dev",
  "system": "S", "llm": "without_gemini", "split": "dev", "stage": "debug",
  "grader_version": "ejemplo-a-mano",
  "computed_at": "2026-10-01T16:18:47.763822Z",
  "n_cases": 1,
  "metrics": [
    {"name": "safe_auto_resolution", "slice": {}, "value": 1.0, "numerator": 1.0, "denominator": 1.0,
     "n": 1, "unit": "ratio", "warning": "n < 10", "note": null},
    {"name": "containment", "slice": {}, "value": 1.0, "numerator": 1.0, "denominator": 1.0,
     "n": 1, "unit": "ratio", "warning": "n < 10", "note": "sin handoff no prueba que se resolvió"}
  ]
}
```

## 6. B1 · bot de reglas

**Elegimos la opción A** (Ariela y Diego, 1-oct): B1 es **el mismo backend** con el NLU forzado a palabras clave y sin Gemini. Corre con el mismo runner (`python -m eval.runner --system B1`) y produce exactamente este formato, con `system = "B1"`, `llm = "without_gemini"` y `versions.nlu_mode = "keywords"`.

**Qué tiene B1 y qué comparte con S:**

| Pieza | S | B1 |
| :-- | :-- | :-- |
| Intención | Clasificador TF-IDF + LR (4.2) y, si se abstiene, Gemini (`intent_zeroshot_v1`) | `nlu/stub.py` (palabras clave, `stub-keywords-0`) |
| Monto, fecha, comercio, «sí/no» | Gemini (`extraccion_v1`) y, si falla, `nlu/rules.py` | `nlu/rules.py` |
| Mensajes al cliente y resumen del handoff | Gemini + verificador, y si no pasa, plantilla | Plantilla siempre |
| Orquestador, política, herramientas, confirmación, handoff | Iguales | Iguales |

**Qué mide y qué no:** mide lo que aportan el ML y el LLM sobre la misma política y el mismo orquestador. **No** mide el orquestador ni la capa de control, porque B1 la comparte. Esto se declara en el reporte. No es el «formulario fijo» del roadmap (opción B, descartada por tiempo).

**Cómo se verifica que B1 de verdad no usa ML ni LLM** (Paso 5, Diego), en `results.jsonl` de la corrida B1:

- `manifest.versions.intent_model = "stub-keywords-0"` y `nlu_mode = "keywords"`.
- Todo span `nlu.understand` tiene `output.extractor = "rules"`, y todo `TraceTurn.versions.intent_model` es `stub-keywords-0+rules` o `none` (turnos de botón).
- Ningún `TraceTurn.versions.intent_model` contiene `intent_zeroshot`.
- Todo mensaje tiene `source = "template"`, y `cost_usd = 0` y `tokens_in = 0` en todos los casos.

**Mientras no exista la variable** (pedido a Alina, ver abajo), el mismo comportamiento se obtiene hoy con `INTENT_MODEL_PATH=/no/existe` y `GEMINI_API_KEY=` vacía. Si el clasificador no carga, el NLU cae al stub y a las reglas. Se probó con `dev-normal-001` el 1-oct: `/health` da `intent_model = stub-keywords-0` y el turno 1 llega a `CONFIRMAR_ACCION` con R12. Sirve para depurar, pero depende de un camino de falla y deja un warning en el log. Las corridas que van al reporte (Pasos 9 y 11) se hacen con `NLU_MODE=keywords`.
