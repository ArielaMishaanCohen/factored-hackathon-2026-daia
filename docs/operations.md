# Operación · LATAM Bank · Intake de disputas

**Dueño:** rol C (backend) · **Fase:** 7 · **Estado:** vigente para la demo del hackathon
**Cubre:** pilar 6 del reto, "ruta creíble a operación" (tracing, reintentos acotados, fallback seguro, setup reproducible).

Este documento explica cómo se corre, se vigila y se recupera el sistema, y qué falta para producción real. Todo lo que se afirma aquí está implementado y probado (`tests/`), salvo lo marcado explícitamente como **pendiente**.

---

## 1. Cómo está desplegado

| Pieza | Dónde | Notas |
| :-- | :-- | :-- |
| Imagen única | Render · Web Service · Docker · plan Free | `Dockerfile` multi-stage: build de React + FastAPI. Un solo link sirve la UI (`/`), la API (`/api/*`) y Swagger (`/docs`) |
| Despliegue | Automático en cada push a `main` | Receta en `render.yaml` |
| Salud | `GET /api/health` | Render lo usa como *health check*. Devuelve versión de política, modelo de intención, modelo LLM y fuente de datos (`stub` o `gold:…`) |
| Datos del banco | `data/gold/gold.duckdb` (solo lectura) | Si no existe, se usan los stubs (`backend/app/tools/stub_data.py`). La fuente activa se ve en `/api/health` → `data_manifest` |
| Estado operativo | `data/ops.sqlite` | Conversaciones, acciones pendientes, casos, bloqueos, handoffs, trazas, sesiones revocadas |

### Variables de entorno

| Variable | Valor en la demo | Para qué |
| :-- | :-- | :-- |
| `JWT_SECRET` | Generado por Render (aleatorio) | Firma los tokens de sesión y los de confirmación. **Nunca** en el repo |
| `JWT_TTL_MINUTES` | `15` | Vida de una sesión |
| `DEMO_MODE` | `true` | Habilita `/auth/demo/expire` (botón "expirar sesión") |
| `DEMO_OTP` | `123456` | OTP **de prueba**, documentado como tal |
| `DEMO_AGENT_ID` | `AGT-DEMO` | Login de la consola del agente humano |
| `FAULT_INJECTION` | `false` | En `true`, el header `X-Fault-Inject: <herramienta>` simula un timeout. **Siempre `false` en el link público** |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Rol B | Sin llave, el sistema funciona con reglas y plantillas (fallback) |
| `GOLD_DB_PATH` / `OPS_DB_PATH` | Por defecto `data/gold/gold.duckdb` y `data/ops.sqlite` | Rutas de datos |

---

## 2. Cómo correrlo (setup reproducible)

### Local, sin Docker (Windows · PowerShell)

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env          # completar JWT_SECRET
uvicorn app.main:app --app-dir backend --reload --port 8000
```

- API y Swagger: http://localhost:8000/docs
- Tests: `python -m pytest -v`

### Local, con Docker (igual que en Render)

```bash
docker compose up --build       # http://localhost:8000
```

### Empezar de cero

Apagar el servidor y borrar `data/ops.sqlite`. Al arrancar se crea vacío. Los tests usan una base en memoria y nunca tocan ese archivo.

---

## 3. Trazabilidad (tracing)

Cada conversación tiene un `trace_id`, y cada turno guarda:

| Campo | Contenido |
| :-- | :-- |
| `spans` | Cada paso con nombre, latencia, resultado resumido y error: `nlu.understand`, `tool.*`, `policy.evaluate`, `verify.*` |
| `state_from` → `state_to` | Transición de la máquina de estados |
| `input_kind`, `language` | Si el turno fue un mensaje o un botón, y el idioma |
| `intent`, `intent_confidence` | Salida del NLU |
| `rule_id` | Regla de política aplicada (R1–R12) |
| `actions` | Acciones del turno con `verified` / `failed` |
| `case_id`, `handoff_id` | Lo que se creó en el turno |
| `latency_ms`, `tokens_in/out`, `cost_usd` | Eficiencia. Tokens y costo suman los spans del LLM (0 mientras no se use Gemini) |
| `versions` | `policy_version`, `intent_model`, `llm_model`, `data_source`, para reproducir cualquier resultado |

**Dónde se ve:**
- `GET /api/traces/{trace_id}`. El cliente solo ve sus trazas y **sin** el span de riesgo (`get_transaction_risk`). El agente las ve completas.
- **Log estructurado:** una línea JSON por turno (logger `latam.trace`), visible en Render → *Logs*. **No incluye el texto del cliente.**

```json
{"event": "turn", "trace_id": "TR-9515ab", "turn_id": 1, "state_from": "INICIO",
 "state_to": "CONFIRMAR_ACCION", "rule_id": "R12", "actions": [], "handoff": false,
 "latency_ms": 4, "tool_errors": [], "cost_usd": 0.0}
```

La evaluación (Fase 6) califica los casos leyendo estos campos. **Su forma no cambia sin avisar al equipo.**

---

## 4. Fallas y recuperación

| Situación | Qué hace el sistema | Test |
| :-- | :-- | :-- |
| Herramienta lenta o caída (`TIMEOUT`) | Reintenta hasta **2 veces** con espera creciente (0.05 s, 0.1 s). Solo en `TIMEOUT` y solo en operaciones idempotentes | `test_reintentos_quedan_en_la_traza` |
| Sigue fallando tras los reintentos | **Nunca** dice "listo". Registra la acción como `failed` y hace handoff con `TOOL_FAILURE` y una pregunta abierta para el humano | `test_timeout_al_crear_caso_hace_handoff_y_no_miente` |
| La acción "se hizo" pero no se ve al releer | Igual que arriba: la verificación posterior manda sobre la respuesta de la herramienta | `_execute_case`, `_execute_block` |
| Falla hasta el handoff | Mensaje seguro al cliente, sin inventar números de caso | `_handoff` |
| Gemini no responde (rol B) | Extracción por reglas y respuestas por plantilla (`source: "template"`) | Contrato de B |
| Sesión expirada o token inválido | `401` sin revelar nada | `test_expired_session` |
| Reinicio del servidor | Todo el estado se recarga desde SQLite; una confirmación pendiente sigue siendo válida | `test_persistencia.py` |
| Doble clic en "Confirmar" | Token de un solo uso + creación idempotente: un solo caso | `test_happy_path_creates_verified_case` |

**Inyección de fallas** (solo con `FAULT_INJECTION=true`): header `X-Fault-Inject: create_dispute_case` (o varias herramientas separadas por coma). Herramientas: `search_transactions`, `get_transaction`, `get_transaction_risk`, `get_open_cases`, `get_case`, `create_dispute_case`, `get_card_status`, `block_card`, `create_handoff`.

---

## 5. Monitoreo

`GET /api/ops/metrics` (solo rol agente) devuelve el tablero de operación:

| Métrica | Por qué se vigila | Alerta sugerida |
| :-- | :-- | :-- |
| `handoff_rate` y `handoffs_by_reason` | Si sube, o el NLU entiende peor o la política es muy estricta | `TOOL_FAILURE` > 2 % de conversaciones |
| `tool_errors` por herramienta | Detecta una dependencia caída | Cualquier herramienta con errores en 3 turnos seguidos |
| `actions.failed` | Acciones que no se pudieron verificar | > 0 → revisar de inmediato |
| `latency_ms.p50 / p95` | Experiencia del cliente | p95 > 3 s |
| `rules` | Distribución de decisiones: un cambio brusco indica datos o política distintos | R8 (score nulo) muy por encima del ~20 % esperado |
| `intents`, `languages` | Mezcla de demanda ES/PT | — |
| `cost_usd` | Gasto en LLM | Presupuesto diario |

En la demo las alertas se revisan a mano. En producción se exportarían a una herramienta de monitoreo (**pendiente**, §8).

---

## 6. Control de acceso y datos

- **Roles:** `customer` (chat, sus casos y sus trazas) y `agent` (cola de handoffs, trazas completas, métricas). Se validan en el backend con el JWT, nunca en el frontend ni en el LLM.
- **El `customer_id` sale siempre del token.** Toda consulta de datos del cliente lleva `WHERE customer_id = ?` dentro del SQL (`tools/data_source.py`).
- **Transacción de otro cliente = "no encontrada"**, el mismo mensaje que si no existiera (R1).
- **Minimización:** gold no tiene documento, dirección, teléfono ni correo. `fraud_score` nunca llega al cliente ni al LLM de redacción.
- **Secretos:** solo en variables de entorno (`.env` local, panel de Render). `.env` está en `.gitignore`, y el historial se revisó sin llaves (`git log -S "AKIA"` vacío).
- **Acciones con efecto** (crear caso, bloquear tarjeta): exigen un token de confirmación firmado (HMAC), ligado a acción + objeto + sesión, de un solo uso y con vencimiento a los 5 minutos. El LLM nunca lo ve.

---

## 7. Capacidad y límites conocidos

| Límite | Impacto | Mitigación en la demo |
| :-- | :-- | :-- |
| Render Free se duerme tras 15 min sin uso | El primer request tarda ~1 min | Aviso en el README; opción de plan pago durante la evaluación |
| Disco efímero en Render Free | Al dormir o redesplegar, `ops.sqlite` vuelve a vacío | Aceptable: cada demo empieza limpia. En producción, Postgres o disco persistente |
| SQLite + un proceso | Un solo worker de uvicorn; el estado se guarda al final de cada request | Suficiente para la demo. Para escalar: Postgres y varios workers |
| 512 MB de RAM, 0.1 CPU | Gold debe ser un subconjunto (clientes de demo), no los 4,4 M de transacciones | Rol A genera gold reducido para el deploy |
| Capa gratuita de Gemini (rol B) | Límite de requests por minuto | Fallback a plantillas; caché y control de ritmo en la evaluación |

---

## 8. Pendiente antes de producción real

1. **Identidad real:** OAuth/OTP enviado por SMS o correo, en lugar del OTP fijo de prueba.
2. **Core bancario real:** las herramientas hoy leen gold y escriben en SQLite. En producción serían APIs del core, con sus propios SLA.
3. **Base de datos gestionada** (Postgres) con respaldos, en lugar de SQLite.
4. **Monitoreo y alertas** exportados (OpenTelemetry → Grafana/Datadog) y retención definida: por ejemplo, trazas 90 días con enmascaramiento de IDs.
5. **Revisión legal** de la política de disputas (ventanas, montos, SLA) con el área de riesgo.
6. **Pruebas de carga y red teaming** del canal (inyección de prompts, abuso).
7. **Portugués con datos reales:** hoy el PT se valida con datos generados por el equipo.
