# Entregables por rol · qué entrega cada quien para la unificación

**Para:** rol C (backend), que integra todo en una sola imagen y un solo link.
**Basado en:** `roadmap_fases_1_a_8.md` (fases 1 a 8), `design.md` v1.0 (contratos) y el código actual del repo.
**Fecha:** 28 de septiembre de 2026

---

## 0. Idea general

El backend es el punto donde todo se junta. Cada rol entrega **un producto terminado que se conecta en un lugar fijo**, sin que C tenga que reescribir nada:

| Rol | Entrega final | Se conecta al backend por | C lo consume en |
| :-- | :-- | :-- | :-- |
| **A · Datos** | `data/gold/gold.duckdb` + umbrales calibrados | Archivo DuckDB (solo lectura) con tablas y columnas fijas | `backend/app/tools/*.py`, `config/policy.yaml` |
| **B · ML** | Clasificador de intención + cliente de Gemini (extracción y redacción) | Una función `understand(text, ...) → NLUResult` y una función de redacción con verificador | `backend/app/nlu/`, `backend/app/llm/`, `backend/app/responder/` |
| **C · Backend** | API FastAPI completa, desplegada | — (es el integrador) | — |
| **D · Frontend** | Build de React (`frontend/dist/`) | HTTP contra `/api/*` según `design.md` §6 | FastAPI sirve `frontend/dist` como estáticos |
| **A + B · Evaluación** | `make eval` + `docs/eval_report.md` | Llama al orquestador del backend | `eval/runner.py` importa el backend |

**Regla de oro:** si cada quien respeta los contratos de `design.md` y `backend/app/schemas.py`, la integración es cambiar imports y rutas de archivo, no lógica. Cualquier cambio de contrato va por PR que toque `design.md` y `schemas.py` al mismo tiempo, con aviso en el grupo.

---

## 1. Rol A · Datos (Fases 2 y 6)

### 1.1 Producto terminado

1. **`data/gold/gold.duckdb`**, generado con `make data` desde cero, con estas tablas (nombres y columnas de `design.md` §4.5):

   | Tabla | Columnas mínimas | Para qué la usa el backend |
   | :-- | :-- | :-- |
   | `dispute_transactions` | `transaction_id`, `customer_id`, `product_id`, `business_date`, `amount`, `currency`, `amount_usd`, `merchant_name`, `transaction_type`, `channel`, `status`, `fraud_score` | `search_transactions`, `get_transaction`, `get_transaction_risk` |
   | `cards` | `product_id`, `customer_id`, `card_mask`, `status` | `get_card_status`, `block_card` (estado base) |
   | `customer_profile` | `customer_id`, `segment`, `country`, `prior_complaints_90d` | R11 y el bloque `customer` del handoff |
   | `demo_customers` | `customer_id`, `display_name` (ficticio), `segment`, `country`, `suggested_language`, `scenario` | `GET /auth/demo-customers` y login |
   | `service_agents` *(o columna equivalente)* | idiomas del agente | `suggested_agent_language` del handoff |
   | `baseline_metrics` | métricas históricas | Solo narrativa y evaluación, el backend no la necesita |

   Garantías que A le da a C:
   - `amount_usd` **sin nulos** (el contrato de silver falla si queda alguno).
   - `fraud_score` puede ser nulo (~20 %). Eso es esperado y dispara R8.
   - `is_fraud` **no** está en gold. Gold tampoco lleva documento, dirección, teléfono ni correo.
   - Hay al menos **un cliente de demo por escenario obligatorio** (normal, ambiguo, fraude/escalamiento, fuera de alcance, PT). Reemplazan a `CUS-DEMO-01..03` de los stubs.
   - `business_date` ≤ `reference_date` (2026-06-17).

2. **`config/policy.yaml` con los umbrales calibrados** (τ_alto, τ_bajo, τ_monto, ventana de reclamo), cada uno con su evidencia comentada. C no cambia código cuando cambian los números: solo se relee el YAML.
3. **`docs/data_contracts.md`**: nombres finales de columnas, política de frescura (T+1) e incrementalidad.
4. **`reports/quality_report.json` y `data/manifest.json`** por corrida (calidad y linaje). No los consume el backend, pero van al README y a las slides.
5. **`analysis/metricas_problema.json`**: fuente única de los números del problema, para las slides.
6. **Casos de evaluación** (con B): `eval/cases/*.jsonl` derivados de `transactions` (ver §5).

### 1.2 Qué tiene que hacer C para integrarlo

- Cambiar los stubs de `backend/app/tools/transactions.py` y `cards.py` para que lean DuckDB (`settings.gold_db_path`) con `customer_id = ?` **dentro de la consulta**.
- Cambiar `stub_data` por `demo_customers` en el login.
- Si A cambia un nombre de columna, A avisa y actualiza `design.md` §4.5 y `data_contracts.md` el mismo día.

### 1.3 Cuándo

| Hito | Fecha |
| :-- | :-- |
| Primer `gold.duckdb` usable (aunque sea con un subconjunto de clientes) | **Martes 29** |
| Umbrales calibrados en `policy.yaml` | Martes 29 – miércoles 30 |
| `demo_customers` final (uno por escenario) | **Miércoles 30**, antes del checkpoint |

---

## 2. Rol B · ML (Fases 4 y 6)

### 2.1 Producto terminado

1. **NLU que reemplaza `backend/app/nlu/stub.py`** con la **misma salida**: `schemas.NLUResult`.
   - Entrada: el texto del cliente (y, si hace falta, el estado actual de la conversación, para interpretar un "sí" solo en `CONFIRMAR_ACCION`).
   - Salida: `language`, `intent`, `intent_confidence`, `abstain` (= confianza < `tau_intencion`), `amount`, `currency`, `date_from`, `date_to`, `merchant_hint`, `selected_option`, `confirmation`, `suspected_injection`, `extractor` (`"llm"` o `"rules"`), `model_version`.
   - Por dentro: clasificador elegido (intención + abstención) + extracción con Gemini (JSON validado con Pydantic). Si Gemini falla o devuelve JSON inválido → 1 reintento → extracción por reglas, con `extractor = "rules"`. **La función nunca lanza excepción por culpa del LLM.**
   - El modelo entrenado vive en el repo como artefacto liviano (p. ej., `ml/intent/model/`), se carga una sola vez al arrancar y **no mete PyTorch en la imagen** (preferir `fastembed`/ONNX o la API de embeddings de Gemini).
2. **Cliente de Gemini en `backend/app/llm/gemini_client.py`**: timeout, máximo 2 reintentos con backoff, caché de respuestas, conteo de tokens y costo (para la traza), modelo fijado en `GEMINI_MODEL`.
3. **Redacción en `backend/app/responder/`**: recibe la plantilla que eligió el orquestador + los hechos verificados y devuelve el texto final en ES o PT. Incluye el **verificador de hechos**: todo número, fecha, ID y comercio del texto debe estar en los hechos; si no, devuelve la plantilla tal cual y marca `source = "template"`. También redacta el `summary` del handoff (solo texto, sin decisiones).
4. **`tau_intencion` calibrado** en `config/policy.yaml` (sección `intent`), elegido en val y reportado en test.
5. **Prompts versionados** en `prompts/` (versión en el nombre del archivo).
6. **Documentación de su parte:** `ml/intent/model_card.md`, tabla comparativa de los 5 candidatos por idioma, corridas en `ml/intent/runs/`, set etiquetado en `ml/intent/data/`, `make train` reproducible.

### 2.2 Lo que B **no** entrega (lo hace C)

- El LLM no elige herramientas, no aplica la política, no ve `customer_id` de otros, no ve ni genera `confirmation_token` ni `pending_action_id`. Todo eso es del orquestador.
- El LLM nunca recibe nombre, documento ni contacto del cliente.

### 2.3 Qué tiene que hacer C para integrarlo

- En el orquestador, cambiar `from .nlu.stub import understand` por el módulo de B.
- Llamar a la función de redacción de B en vez de devolver la plantilla directo; si la función falla, usar la plantilla.
- Pasar a la traza lo que B devuelva de latencia, tokens, costo y `model_version`.

### 2.4 Cuándo

| Hito | Fecha |
| :-- | :-- |
| Extracción con Gemini + fallback funcionando detrás de `understand()` | **Martes 29 – miércoles 30** |
| Clasificador elegido e integrado con `tau_intencion` | **Miércoles 30**, antes del checkpoint |
| Redacción + verificador | Miércoles 30 |

---

## 3. Rol C · Backend (Fases 3 y 7) · lo que integra

Para que quede claro qué es de C y qué recibe de los demás:

### 3.1 Producto terminado

1. **API FastAPI** con los endpoints de `design.md` §6.2, formato único de errores (§6.1) y las garantías al frontend (§6.4). `tests/test_api_contract.py` en verde.
2. **Auth de prueba** (JWT de 15 min, OTP fijo, rol agente, revocación con `/auth/demo/expire`).
3. **Herramientas** contra el `gold.duckdb` de A y SQLite operativo (`cases`, `card_blocks`, `pending_actions`, `handoffs`, `traces`, `conversations`), con filtro por cliente en la consulta, idempotencia y verificación posterior a cada acción.
4. **Motor de política** (`policy/engine.py`): función pura R0–R12 que lee `policy.yaml`, con tests por regla y bordes.
5. **Orquestador** (máquina de estados de `design.md` §3.5), que llama al NLU y a la redacción de B.
6. **Plantillas ES/PT** (red de seguridad si Gemini falla).
7. **Handoff** validado con Pydantic (`design.md` §5).
8. **Operación:** tracing por turno, reintentos acotados, inyección de fallas (`FAULT_INJECTION`), una sola imagen Docker multi-stage (build de React + FastAPI + gold), deploy estable y `docs/operations.md`.

### 3.2 Lo que C necesita recibir (resumen)

| De | Qué | Dónde lo espera |
| :-- | :-- | :-- |
| A | `gold.duckdb` | `data/gold/gold.duckdb` (`GOLD_DB_PATH`) |
| A | Umbrales de política | `config/policy.yaml` |
| B | `understand(...) → NLUResult` | `backend/app/nlu/` |
| B | Cliente Gemini | `backend/app/llm/gemini_client.py` |
| B | Redacción + verificador | `backend/app/responder/` |
| B | `tau_intencion` | `config/policy.yaml` → `intent` |
| D | Build de React | `frontend/dist/` (`FRONTEND_DIST`) |

---

## 4. Rol D · Frontend y narrativa (Fases 5 y 8)

### 4.1 Producto terminado

1. **App React (Vite)** que compila con `npm run build` a `frontend/dist/`. FastAPI la sirve en el mismo dominio, así que las llamadas van a rutas relativas `/api/...` (sin URL fija de backend en producción).
2. **Cuatro vistas** que consumen solo la API de `design.md` §6:
   - **Login de demo:** `GET /auth/demo-customers` → OTP → `POST /auth/login`. Login de agente con `POST /auth/agent-login`. Botón "expirar sesión" (`POST /auth/demo/expire`).
   - **Chat del cliente:** `POST /chat`; transacciones candidatas como tarjetas seleccionables; botones Confirmar/Cancelar que mandan el `pending_action_id`; indicador del idioma.
   - **Consola del agente:** `GET /handoffs` y `GET /handoffs/{id}` con hechos verificados, regla, acciones, preguntas abiertas y agente sugerido.
   - **Panel de auditoría:** `GET /traces/{trace_id}`.
3. **Manejo de errores según el contrato:** 401 `SESSION_EXPIRED` → vuelve al login; el resto como mensaje de fallback.
4. **Sin textos fijos en español:** la UI funciona completa en PT; los mensajes del bot ya vienen traducidos del backend (la UI no traduce).
5. **Tipos en `frontend/src/api/types.ts`** alineados con `schemas.py`, y un mock (`api/mock.ts`) que se apaga con una variable de entorno cuando el backend real está listo.
6. **Narrativa (Fase 8, con todos):** 4–6 slides en PDF, video de 3–5 min, README con la matriz requisito → evidencia.

### 4.2 Qué tiene que hacer C para integrarlo

- Montar `frontend/dist` como estáticos en FastAPI (con fallback a `index.html` para las rutas del SPA).
- Etapa de build de Node en el `Dockerfile`.
- En desarrollo, el proxy de Vite (`/api → :8000`) ya resuelve el CORS.

### 4.3 Cuándo

| Hito | Fecha |
| :-- | :-- |
| Chat contra el backend real (camino feliz) | **Martes 29** |
| Las 4 vistas contra el backend real | **Miércoles 30**, checkpoint |
| UI desplegada recorriendo los 5 escenarios | Jueves 1 |

---

## 5. Evaluación (A + B, con todos · Fase 6)

### 5.1 Producto terminado

1. **`eval/cases/*.jsonl`**: ~190 casos held-out + ~40 de desarrollo. Cada caso: cliente de demo, turnos del cliente (guion fijo) y resultado esperado (transacción, regla, acción final, si escala, acciones prohibidas).
2. **`eval/runner.py`** (`make eval`): corre los casos contra **S** (sistema completo) y **B1** (`eval/baselines/rules_bot.py`), 3 corridas.
3. **`eval/graders.py`**: califica con código leyendo la traza.
4. **`docs/eval_report.md`** con métricas (numerador, denominador y n), desagregación ES/PT y por segmento, variabilidad, errores y limitaciones.

### 5.2 Lo que la evaluación necesita del backend (acuerdo con C)

- **Un punto de entrada invocable sin HTTP**, por ejemplo `orchestrator.handle_turn(session, conversation_id, message) → ChatResponse`, o bien un `TestClient` de FastAPI. Hay que decidir cuál el miércoles; el TestClient no le pide nada nuevo a C.
- **Crear sesiones de prueba** para cualquier cliente de demo sin pasar por la UI.
- **Traza completa por turno** con: estado, intención y confianza, regla disparada, herramientas llamadas con resultado, acciones con `verified`/`failed`, latencia, tokens y costo. Los graders dependen de estos campos, así que su forma no cambia sin avisar.
- **Inyección de fallas** activable por caso (`FAULT_INJECTION` + header o parámetro) para simular `TIMEOUT` en `create_dispute_case`.
- **Base operativa reiniciable** entre casos (SQLite limpio o `conversation_id` y cliente distintos) para que un caso no contamine al siguiente.

---

## 6. Calendario de integración

| Día | Qué se integra | Quién |
| :-- | :-- | :-- |
| **Lun 28** | Esqueleto: `make up` levanta backend con stubs + frontend con mock | C, D |
| **Mar 29** | Gold real en las herramientas · chat real (camino feliz ES) · **esqueleto desplegado** | A → C, D → C |
| **Mié 30** | NLU de B detrás de `understand()` · redacción · `demo_customers` final · **checkpoint: los 5 escenarios end-to-end** | Todos |
| **Jue 1** | Primera corrida de la evaluación completa · correcciones · **feature freeze 20:00** | A, B, C |
| **Vie 2** | 3 corridas finales · docs · deploy final · **code freeze** | Todos |
| Sáb 3 – Lun 5 | Slides, video, prueba desde un clon limpio, envío | D, con todos |

---

## 7. Checklist de "unificado"

La integración está lista cuando:

- [ ] `make data && make train && make up` funciona desde un clon limpio con solo `.env`.
- [ ] El backend lee `gold.duckdb` real (no hay imports de `stub_data` ni de `nlu/stub.py` en el camino de producción).
- [ ] Con `GEMINI_API_KEY` vacía, el sistema sigue funcionando con reglas y plantillas.
- [ ] Los 5 escenarios obligatorios (normal, ambiguo/no soportado, escalamiento, ES, PT) se recorren desde el link desplegado.
- [ ] La consola del agente muestra un handoff completo y el panel de auditoría muestra la traza.
- [ ] `make test` y `make eval` pasan y generan `eval/reports/`.
- [ ] `policy.yaml` tiene los umbrales calibrados por A y B, con su evidencia.
- [ ] Nada de `.env`, llaves ni datos crudos en el repo.
