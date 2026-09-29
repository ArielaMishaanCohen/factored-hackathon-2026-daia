# Integración con el backend · qué necesita el backend de cada quien

**De:** Alina (rol C, backend) · **Fecha:** martes 29 de septiembre de 2026
**Estado del backend:** Fases 3 y 7 completas, 65 tests en verde y desplegado en Render (`https://factored-hackathon-2026-daia.onrender.com`, salud en `/api/health`).
**Complementa:** `docs/entregables_por_rol.md`. Este documento dice **exactamente** qué forma debe tener lo que cada quien entrega, para que se enchufe sin reescribir nada.

> **Regla de oro:** si respetan las firmas y los nombres de este documento, integrar es copiar archivos y correr los tests. Si necesitan cambiar algo del contrato, **avísenme antes**, no después.

**Cómo entregar (todos):**
1. Subir sus cambios a GitHub (ideal en una rama propia con Pull Request a `main`).
2. Correr `python -m pytest -v` antes de subir. Tiene que quedar **todo en verde** (hoy: 65 passed).
3. Avisarme en el grupo qué subieron.

---

## 1. Ariela · ML (NLU, Gemini y redacción)

### 1.1 El NLU: la función `understand`

**Dónde:** reemplaza `backend/app/nlu/stub.py`. Pueden crear `backend/app/nlu/model.py` (o el nombre que quieran) y exponer la función. Yo cambio **una línea** del orquestador para importarla.

**Firma exacta:**

```python
from app.schemas import NLUResult

def understand(text: str, state: str | None = None) -> NLUResult:
    ...
```

- `text`: lo que escribió el cliente (máx. 2000 caracteres).
- `state`: estado actual de la conversación (por ejemplo `"CONFIRMAR_ACCION"`). Úsenlo si les sirve, o ignórenlo.

**Qué debe devolver:** un `NLUResult` (`backend/app/schemas.py`) con estos campos:

| Campo | Tipo | Reglas |
| :-- | :-- | :-- |
| `language` | `"es"` \| `"pt"` | Solo esos dos |
| `intent` | `"cargo_no_reconocido"` \| `"cobro_incorrecto"` \| `"tarjeta_comprometida"` \| `"estado_disputa"` \| `"fuera_de_alcance"` | Exactamente esos nombres |
| `intent_confidence` | float 0–1 | |
| `abstain` | bool | `True` si `intent_confidence < policy.yaml → intent.tau_intencion`. **Leer el umbral del YAML** (`from app.config import get_policy`), no escribirlo en el código |
| `amount` | float \| None | Ver §1.2 |
| `currency` | `"ARS"` \| `"COP"` \| `"USD"` \| None | No hay MXN en los datos. Si no es seguro, `None` |
| `date_from`, `date_to` | date \| None | |
| `merchant_hint` | str \| None | Ej. `"Oxxo"`. El backend busca por "contiene", sin importar mayúsculas |
| `selected_option` | int \| None | Si el cliente dice "la segunda" |
| `confirmation` | `"yes"` \| `"no"` \| None | Ver §1.3 ⚠️ |
| `suspected_injection` | bool | Solo se registra. La seguridad no depende de esto |
| `extractor` | `"llm"` \| `"rules"` | `"rules"` si Gemini falló y usaron el fallback |
| `model_version` | str | Ej. `"tfidf-lr-v2"`. Sale en `/api/health` y en cada traza |

**Reglas duras:**
1. **Nunca lanza una excepción.** Si Gemini falla, se cae, devuelve JSON inválido o no hay `GEMINI_API_KEY`: un reintento, y luego extracción por reglas con `extractor="rules"`. El sistema tiene que funcionar con `GEMINI_API_KEY` vacía.
2. **Nada de PyTorch** en `backend/requirements.txt`: la imagen de Render tiene 512 MB de RAM. Usen scikit-learn, `fastembed`/ONNX o la API de embeddings de Gemini.
3. El modelo entrenado se guarda en el repo como archivo liviano (ej. `ml/intent/model/`) y **se carga una sola vez** al importar el módulo, no en cada mensaje.
4. El NLU **no ve** `customer_id`, nombres ni datos del cliente. Solo el texto.

### 1.2 Montos: casos que tienen que salir bien

El stub actual tiene un bug que no deben copiar: convierte `"350.50"` en `35050`.

| Texto | `amount` esperado |
| :-- | :-- |
| `"de 350 en Oxxo"` | 350.0 |
| `"3.500"` (ES/PT: punto = miles) | 3500.0 |
| `"350,50"` (coma decimal) | 350.5 |
| `"350.50"` (dos decimales tras el punto) | 350.5 |
| `"1.200.000"` | 1200000.0 |
| `"$350"`, `"R$ 350"`, `"USD 350"` | 350.0 |
| `"120 mil"` | 120000.0 |
| `"hola"` | None |

### 1.3 ⚠️ Confirmaciones: cuidado con el "no"

El orquestador **solo** usa `confirmation` cuando la conversación está en `CONFIRMAR_ACCION`. Ahí, `"no"` **cancela** la acción.

- `"sí"`, `"si"`, `"sim"`, `"ok"`, `"dale"`, `"confirmo"` → `"yes"`
- `"no"`, `"não"`, `"nao"`, `"cancelar"` → `"no"`
- **`"No reconozco otro cargo"` → `None`**, no `"no"`. Es una frase nueva, no una respuesta. El stub hoy se equivoca aquí. Marquen `confirmation` solo para respuestas cortas de sí/no.

### 1.4 Frases que los tests ya usan (tienen que seguir funcionando)

| Frase | Lo que esperan los tests |
| :-- | :-- |
| `No reconozco un cargo de 350 en Oxxo` | `cargo_no_reconocido`, es, amount 350, merchant Oxxo |
| `Não reconheço uma compra de 3.500` | pt, amount 3500 (con intención de disputa, no fuera de alcance) |
| `Não reconheço uma cobrança de 350` | pt, amount 350 |
| `Me cobraron dos veces 120000` | `cobro_incorrecto`, amount 120000 |
| `Quiero un préstamo` | `fuera_de_alcance`, **sin** abstención |
| `hola`, `mmm`, `no sé` | `abstain=True` (el sistema pide aclarar) |
| `No reconozco un cargo de 777` | disputa con amount 777 |

Si su modelo cambia alguno de estos resultados y creen que el suyo es el correcto, hablamos y ajustamos el test. No lo cambien en silencio.

### 1.5 Cliente de Gemini

**Dónde:** `backend/app/llm/gemini_client.py`.

- Modelo desde `GEMINI_MODEL` y llave desde `GEMINI_API_KEY` (`from app.config import get_settings`). **Nunca** escribir la llave en el código.
- Timeout (sugerido 8 s), máximo 2 reintentos con backoff.
- **Devolver también el uso**, porque las trazas ya tienen dónde guardarlo (`Span.model`, `tokens_in`, `tokens_out`, `cost_usd`):

```python
@dataclass
class LLMUsage:
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float     # anotar los precios supuestos en un comentario
```

### 1.6 Redacción + verificador

**Dónde:** `backend/app/responder/` (un archivo nuevo, ej. `compose.py`). **No borren** `templates.py`: es la red de seguridad.

**Firma:**

```python
def compose(template_key: str, language: str, facts: dict) -> tuple[str, str, LLMUsage | None]:
    """Devuelve (texto, source, uso). source = "llm" si Gemini redactó y pasó el verificador;
    "template" si se usó la plantilla tal cual."""
```

- `template_key` y `facts` son exactamente lo que hoy recibe `templates.render(key, language, **facts)`. Ej.: `("case_created", "es", {"case_id": "DSP-000001", "sla": "2026-10-09"})`.
- **Verificador:** todo número, fecha, ID y comercio del texto de Gemini tiene que estar en `facts`. Si aparece algo que no está (un monto inventado, otro número de caso), se devuelve la plantilla.
- Nunca reciben `fraud_score`, `customer_id` ni nombres. Ya los filtro yo.
- Yo lo conecto en `Turn.say()` del orquestador. Si `compose` lanza cualquier excepción, uso la plantilla.

### 1.7 Umbral y documentación

- `tau_intencion` calibrado en `config/policy.yaml` → `intent`, con un comentario de cómo se eligió (val) y cómo rindió (test). Hoy vale `0.60`.
- `ml/intent/model_card.md`, tabla comparativa de candidatos, corridas en `ml/intent/runs/` y `make train`, como dice el roadmap.

### 1.8 Tests que les sugiero agregar (`tests/test_nlu.py`)

- Cada fila de §1.2 y §1.4.
- Con `GEMINI_API_KEY` vacía: `understand("No reconozco un cargo de 350")` funciona y dice `extractor="rules"`.
- Simulando que Gemini lanza un error: `understand` no lanza nada.

---

## 2. Diego · Datos (gold.duckdb)

### 2.1 El archivo

**Dónde:** `data/gold/gold.duckdb`. Con copiarlo ahí, el backend lo detecta solo. `/api/health` pasa de `"data_manifest": "stub"` a `"gold:gold.duckdb"`.

**Esquema exacto:** está en `scripts/make_demo_gold.py` (el `CREATE TABLE` de arriba). Ese script es la especificación: mismas **4 tablas**, mismos **nombres de columnas**, mismos **tipos**.

| Tabla | Columnas | Notas |
| :-- | :-- | :-- |
| `dispute_transactions` | `transaction_id, customer_id, product_id, business_date (DATE), amount, currency, amount_usd, merchant_name, transaction_type, channel, status, fraud_score` | Ver §2.2 |
| `cards` | `product_id, customer_id, card_mask, status` | Ver §2.3 |
| `customer_profile` | `customer_id, segment, country, prior_complaints_90d (INTEGER)` | Uno por cliente que tenga transacciones |
| `demo_customers` | `customer_id, display_name, segment, country, suggested_language, scenario` | Ver §2.4 |

Si quieren tablas o columnas extra, está bien: el backend las ignora. Lo que **no** pueden hacer es cambiar nombres o tipos de estas sin avisar.

### 2.2 Reglas de `dispute_transactions`

- `amount_usd` **sin nulos** (incluida la corrección de USD: `amount_usd = amount`).
- `fraud_score` puede ser nulo (dispara la regla R8, y está bien).
- `status` ∈ `Approved`, `Declined`, `Pending`, `Reversed`, con esa ortografía exacta.
- `currency` ∈ `ARS`, `COP`, `USD`.
- `business_date` ≤ `2026-06-17` (`reference_date` de `policy.yaml`). **El backend solo busca los últimos 120 días antes de esa fecha**, así que los clientes de demo tienen que tener transacciones entre **2026-02-17 y 2026-06-17**, o el chat dirá "no encontré ese cargo".
- `is_fraud`, documento, dirección, teléfono y correo **no** van en gold.

### 2.3 ⚠️ Reglas de `cards`

- **Todo `product_id` que aparezca en las transacciones de los clientes de demo tiene que estar en `cards`**, con el mismo `customer_id`. Si falta, el flujo de fraude falla al intentar bloquear la tarjeta.
- `card_mask` como `"•••• 4821"`, **nunca** el número completo.
- `status` ∈ `Active`, `Blocked`, `Suspended`, `Closed`. Para el cliente de fraude, la tarjeta tiene que estar `Active` (si no, no hay nada que bloquear).

### 2.4 Clientes de demo: uno por escenario

La pantalla de login lista `demo_customers` tal cual (`display_name`, `segment`, `country`, `scenario`). Elijan clientes **reales del dataset** que cumplan cada escenario y pónganle un `display_name` **ficticio**:

| # | `scenario` (texto que ve el jurado) | Qué tiene que tener ese cliente en los últimos 120 días | Regla que dispara |
| :-: | :-- | :-- | :-- |
| 1 | Resolución normal | Una transacción `Approved`, `fraud_score` < 30, monto bajo el límite de su tipo, **con `merchant_name`** y un monto único (que no se repita) | R12 |
| 2 | Ambiguo (varias candidatas) | 2 o más transacciones con **el mismo monto** | Pide elegir |
| 3 | Fraude con bloqueo y handoff | Una transacción con `fraud_score` ≥ 40 y tarjeta `Active` | R7 |
| 4 | Zona gris | `fraud_score` entre 30 y 39 | R9 |
| 5 | Riesgo desconocido | `fraud_score` nulo | R8 |
| 6 | Monto alto | `amount_usd` por encima del límite de su tipo (`policy.yaml` → `amount_usd_max`) | R10 |
| 7 | Cargo rechazado | Una transacción `Declined` | R2 |
| 8 | Portugués | Cualquiera de los anteriores con `suggested_language = "pt"` | — |

Con 1, 2, 3 y 8 cubrimos los escenarios obligatorios; 4 a 7 suman para la demo y la evaluación. Para cada uno, anoten en `docs/data_contracts.md` qué `transaction_id` y monto usar en la demo (ej.: "cliente 1: escribir *no reconozco un cargo de 350 en Oxxo*").

### 2.5 Tamaño (importante para el deploy)

El servidor gratis tiene **512 MB de RAM**. Para el link público, el gold tiene que ser **chico**: solo los clientes de demo más una muestra, idealmente **menos de 50 MB**. El gold completo sirve para la evaluación local, pero no para Render. Cuando lo tengan, hablamos de cómo lo metemos a la imagen: hoy `data/` está fuera de Git y de Docker a propósito.

### 2.6 Umbrales en `policy.yaml`

Si recalibran `fraud_score_high`, `fraud_score_low`, `amount_usd_max` o `claim_window_days`, solo cambian el YAML, con la evidencia en un comentario, y **suben `policy_version`**. El backend no necesita cambios, y los tests de bordes leen los mismos números.

### 2.7 Cómo probarlo antes de entregármelo

```powershell
copy <su archivo> data\gold\gold.duckdb
python -m pytest -v                          # tiene que seguir 65 passed (los tests usan stubs)
uvicorn app.main:app --app-dir backend --port 8000
```

Luego, en http://localhost:8000/api/health, debería decir `gold:gold.duckdb`. En `/docs`, prueben el login con cada cliente de demo y el mensaje de su escenario.

---

## 3. Nanu · Frontend

### 3.1 ¿Ya puede trabajar? Sí, con el backend real

El backend está completo y desplegado. No hace falta esperar a nadie:

- **Contra Render:** en `frontend/vite.config.ts`, cambiar el proxy temporalmente a `"/api": { target: "https://factored-hackathon-2026-daia.onrender.com", changeOrigin: true }`. Así corre solo `npm run dev`, sin levantar Python. (La primera petición puede tardar ~1 min si el servidor estaba dormido.)
- **Contra su compu:** levantar uvicorn en el puerto 8000; el proxy actual ya funciona.
- **Swagger** (`/docs`) muestra todos los endpoints con ejemplos.

### 3.2 Endpoints

| Endpoint | Para qué | Rol |
| :-- | :-- | :-- |
| `GET /api/auth/demo-customers` | Lista del login. **No escribir los clientes a mano en la UI**: cambian cuando llegue el gold de Diego | público |
| `POST /api/auth/login` `{customer_id, otp}` | Devuelve `access_token` (15 min) | público |
| `POST /api/auth/agent-login` `{agent_id: "AGT-DEMO", otp: "123456"}` | Login de la consola del agente | público |
| `POST /api/auth/demo/expire` | Botón "expirar sesión" (responde 204) | cliente |
| `POST /api/chat` | El chat (ver §3.3) | cliente |
| `GET /api/cases` | Casos del cliente (o todos, si es agente) | ambos |
| `GET /api/handoffs` y `GET /api/handoffs/{id}` | Cola y detalle del agente humano | agente |
| `GET /api/traces/{trace_id}` | Panel de auditoría | ambos |
| `GET /api/ops/metrics` 🆕 | Tablero de operación (ver §3.5) | agente |

Todas las rutas son relativas (`/api/...`): en producción la UI y la API están en el mismo dominio.

### 3.3 Cómo funciona `/api/chat`

- **Primer mensaje:** `{"message": "..."}`, sin `conversation_id`. Guardar el `conversation_id` que devuelve.
- **Siguientes:** `{"conversation_id": "...", "message": "..."}`.
- **Botones:** `{"conversation_id": "...", "ui_action": {...}}`, sin `message`:
  - elegir transacción: `{"type": "select_transaction", "transaction_id": "..."}`
  - confirmar: `{"type": "confirm", "pending_action_id": "..."}`
  - cancelar: `{"type": "cancel", "pending_action_id": "..."}`

**Qué pintar según `response.ui.type`:**

| `ui.type` | Qué mostrar |
| :-- | :-- |
| `transaction_options` | Tarjetas con `ui.options[]` (fecha, comercio, monto, moneda, `card_mask`). Al tocar una → `select_transaction` |
| `confirmation` | `ui.pending_action.summary` + botones **Confirmar** / **Cancelar**. Vence en `expires_at` (5 min) |
| `case_created` | Tarjeta del caso: `case.case_id`, `case.sla_due_at` |
| `handoff` | "Te atiende un especialista" + `ui.queue` |
| `null` | Solo los `messages` |

- **Los textos del bot vienen en `messages[].text`, ya en el idioma del cliente.** La UI no traduce, pero **sus propios textos** (botones, títulos) tienen que existir en ES y PT. Usen `response.language` para elegir.
- `messages[].source` es `"template"` o `"llm"`. Puede servir como detalle en el panel de auditoría.

### 3.4 Errores

Todos vienen con el mismo formato: `{"error": {"code": "...", "message": "..."}}`.

| Código | Qué hacer |
| :-- | :-- |
| `401 SESSION_EXPIRED` o `UNAUTHENTICATED` | Volver al login y mostrar "tu sesión expiró" |
| `404 NOT_FOUND` en `/chat` | La conversación no existe (ej. el servidor se reinició en Render): empezar una conversación nueva |
| `403`, `422`, `500` | Mensaje genérico de "algo salió mal, intentá de nuevo" |

### 3.5 Lo nuevo desde el diseño original

1. **La traza tiene un resumen por turno** (todos los campos son opcionales): `intent`, `intent_confidence`, `rule_id`, `actions[]` (con `verified`/`failed`), `latency_ms`, `case_id`, `handoff_id`, `versions`. Hay que agregarlos a `frontend/src/api/types.ts` en `Trace.turns`.
2. **`GET /api/ops/metrics`** (solo agente): `conversations`, `handoff_rate`, `handoffs_by_reason`, `rules`, `latency_ms.p50/p95`, `tool_errors`… Ideal para una tarjetita de "salud del sistema" en la consola del agente.
3. **Nuevos motivos de handoff:** `POLICY_ESCALATION`, `CLARIFICATION_EXHAUSTED` (no se entendió tras 2 aclaraciones), `NO_TRANSACTION_FOUND` (no se encontró el cargo 2 veces), `TOOL_FAILURE`. En el detalle del handoff, `actions_declined` indica qué rechazó el cliente (ej. no quiso bloquear la tarjeta).

### 3.6 Reglas en lenguaje humano (para el panel de auditoría y la consola del agente)

Al jurado le sirve ver **"R7 · Fraude probable"** en vez de solo "R7":

| Regla | Texto sugerido |
| :-- | :-- |
| R1 | Transacción no encontrada (o de otro cliente) |
| R2 | Cargo rechazado: no hubo cobro |
| R3 | Cargo pendiente |
| R4 | Cargo ya revertido |
| R5 | Ya existe una disputa abierta |
| R6 | Fuera de la ventana de reclamo |
| R7 | Fraude probable: bloqueo de tarjeta |
| R8 | Riesgo desconocido (sin score) |
| R9 | Zona gris de fraude |
| R10 | Monto alto |
| R11 | Cliente con disputas repetidas |
| R12 | Registro automático |

### 3.7 Build y deploy

- `npm run build` tiene que pasar sin errores de TypeScript: Render lo corre en cada push y, si falla, **no se despliega nada** (ni el backend).
- Subir `package-lock.json` siempre que agreguen una dependencia.
- La UI se ve en el link de Render apenas se suba a `main`.

---

## 4. Checklist del checkpoint (miércoles 30)

- [ ] `/api/health` en Render dice `gold:gold.duckdb` y el `model_version` del NLU de Ariela
- [ ] `python -m pytest -v` en verde después de integrar todo
- [ ] Desde el link: escenario normal en ES → caso creado
- [ ] Desde el link: ambiguo → tarjetas → elegir → confirmar
- [ ] Desde el link: fraude en PT → bloqueo → caso → handoff visible en la consola del agente
- [ ] Desde el link: "quiero un préstamo" → se abstiene
- [ ] Botón "expirar sesión" → vuelve al login
