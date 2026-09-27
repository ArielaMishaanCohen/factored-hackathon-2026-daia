# Roadmap: Factored AI & Data Hackathon 2026

**Proyecto:** sistema de atención al cliente con IA para un flujo bancario de LATAM Bank (flujo a decidir el lunes con la matriz de la sección 5.1; opción por defecto: disputas de transacciones)
**Equipo:** 3–4 personas, medio tiempo (≈ 4–5 h/día cada una → 70–100 horas-persona en total)
**Fecha límite interna:** viernes 2 de octubre · **Cierre oficial:** lunes 5 de octubre (el fin de semana es colchón, no plan)
**Versión:** v2 · 27 de septiembre de 2026 (v2: acceso a datos, notebook de exploración y matriz de decisión del día 1)

---

## 0. La tesis en una frase

> Un sistema que resuelve solo las disputas simples y seguras, pide aclaración cuando no está claro de qué transacción se habla, se niega o escala cuando la política o el riesgo lo exigen, y le entrega al agente humano un caso ya armado. Todo con permisos y política aplicados en código, no en el prompt, y con números que demuestran que es más seguro que un agente LLM "ingenuo".

Esto responde directamente a lo que Factored dijo en el kickoff: *"Don't build a chatbot, build a customer-service system"* y *"AI should not be autonomous just because it can be"*.

Principio rector para toda la semana: **simple, completo y medido > complejo e incompleto.** Si algo no mejora un criterio de evaluación, no se hace.

---

## 1. Qué exige el hackathon (checklist maestro)

### Entregables (de la presentación)

- [ ] Repo público: `factored-hackathon-2026-[nombre-del-equipo]`
- [ ] Link a la herramienta desplegada y funcionando
- [ ] Presentación de 4–6 slides
- [ ] Video pitch corto (demo + decisiones de arquitectura)
- [ ] Todo enviado a hackathon.admin@factored.ai

### Escenarios obligatorios en la demo

- [ ] Resolución normal (disputa elegible → caso creado y verificado)
- [ ] Solicitud ambigua o no soportada (aclaración o abstención)
- [ ] Escalamiento a humano con handoff estructurado
- [ ] Interacción en español
- [ ] Interacción en portugués (+ limitación reportada: no hay portugués en los datos)

### Los 6 pilares y dónde los cubrimos

| Pilar | Cómo lo cubrimos | Fase |
| :--- | :--- | :--- |
| 1. Problema respaldado por datos | EDA de motivos de contacto, FCR, escalamiento, duración y quejas → justifica "disputas" | F1 |
| 2. Sistema de IA funcional | Orquestador con contexto, aclaraciones, respuestas basadas solo en herramientas | F3 |
| 3. Automatización controlada | Motor de política determinista, confirmación antes de actuar, handoff JSON | F2–F3 |
| 4. Buenas prácticas de datos y ML | Pipeline con contratos, calidad, linaje y frescura; clasificador vs. baseline sin fuga | F1–F2 |
| 5. Calidad medida y manejo de fallas | Set de evaluación con casos adversariales, métricas oficiales, desagregación | F4 |
| 6. Ruta creíble a operación | Trazas, reintentos acotados, fallback, setup reproducible, limitaciones | F3–F5 |

### Criterios de evaluación del jurado

Rationale y documentación · AI engineering (backend, frontend, deploy) · Data analytics (calidad e insights) · Data engineering (extracción y transformación) · ML (selección de modelo, implementación, tracking). **Primer filtro: que funcione.**

---

## 2. Decisiones de arquitectura (tomadas y por tomar)

Formato: decisión → alternativas → por qué → cómo validamos que fue correcta.

### D1. Flujo: se decide el lunes con datos ⏳ (opción por defecto: disputas de transacciones)

Las cuatro opciones y cuándo conviene cada una:

| Opción | Qué hace el sistema | Conviene si… | Riesgo en 5 días |
| :--- | :--- | :--- | :--- |
| 1. Disputas de transacciones | Encuentra la transacción, aplica la política, confirma y crea el caso, o escala (fraude, monto alto) | Los reclamos por transacciones tienen volumen y mal desempeño (FCR, escalamiento, SLA) | Medio |
| 2. Soporte de tarjetas | Pérdida/robo, bloqueo (con confirmación), desbloqueo (escala), explicación de rechazos por `response_code` | Predominan los motivos de tarjetas y los `response_code` tienen significado | Bajo-medio |
| 3. Consultas de cuenta y pagos | Saldos, movimientos, "¿ya se acreditó mi pago?" | Dominan el volumen por mucho y se quiere el camino más seguro | Bajo, pero casi sin acciones: puede parecer "un chatbot" |
| 4. Crédito: información y elegibilidad | Explica productos y evalúa elegibilidad con política sintética + estimación de riesgo | El equipo quiere un componente ML de riesgo y el texto de los transcripts no sirve para clasificar | Alto (guardrails de crédito, etiqueta proxy, casos límite) |

- **Regla:** se decide con la matriz de la sección 5.1, al cierre del lunes. **No se reabre el martes.**
- **Desempate:** disputas, porque es la que cubre de forma más natural los escenarios obligatorios.
- **No combinar flujos:** más flujos no dan puntos. El flujo elegido solo reconoce los pedidos de los demás y se abstiene o los deriva (eso cubre el escenario de "solicitud no soportada").
- **Importante:** las secciones D5 (política) y D7 (etiquetas del clasificador) y el set de evaluación están escritos para disputas. Si gana otra opción, se reescriben el martes en la mañana con la misma estructura.

### D2. LLM: modelo open-weight `gpt-oss-20b`, con interfaz agnóstica al proveedor ✅

- **Alternativas:** GPT de OpenAI (cerrado, de pago), Gemini (cerrado; tiene nivel gratuito, pero hay que revisar sus términos de uso de datos), Ollama local (privado, pero difícil de desplegar gratis).
- **Recomendación:**
  - Todo el código habla con una API compatible con OpenAI (un solo cliente, el proveedor se cambia por variable de entorno).
  - **Desarrollo y evaluación:** `gpt-oss-20b` local con Ollama (gratis, privado y sin límites de tasa; requiere ≈ 16 GB de RAM). Si alguna máquina no da, se usa Groq.
  - **Demo desplegada:** el mismo `gpt-oss-20b` servido por Groq (nivel gratuito, compatible con OpenAI y con tool calling).
  - **Plan B:** OpenAI `gpt-4o-mini` o equivalente, con unos pocos dólares de presupuesto, solo si lo anterior falla.
- **Por qué (argumento de arquitectura para el pitch):** en un banco real, los datos de clientes no deberían salir a una API de terceros. Un modelo open-weight se puede autoalojar dentro de la red del banco; en el hackathon lo servimos en Groq solo porque los datos son sintéticos. Además, aplicamos minimización de datos: el LLM nunca ve el documento de identidad, el ingreso ni el score crediticio; solo ve lo que necesita para el turno.
- **Ojo con los límites del nivel gratuito de Groq** (≈ 1000 solicitudes/día y ≈ 200 000 tokens/día por organización): no alcanzan para correr la evaluación completa varias veces. Por eso la evaluación corre en local, con Ollama. Si en algún momento corremos en Groq, cada persona usa su propia cuenta y los prompts se mantienen cortos.
- **Validación:** en la evaluación reportamos latencia y costo por caso; si nos da tiempo, comparamos `gpt-oss-20b` vs. `gpt-oss-120b` en el mismo set (esto es una "selección de modelo" con evidencia, algo que el jurado valora en ML).

### D3. El LLM no es el que manda: orquestador como máquina de estados ✅

- **Alternativas:** un agente "libre" que decide qué herramienta llamar (ReAct), o un sistema multiagente.
- **Por qué:** una máquina de estados es más fácil de entender, depurar, auditar y evaluar. El LLM se usa solo donde aporta: entender lenguaje natural, extraer datos del mensaje y redactar respuestas.
- **Validación:** los resultados inseguros en la evaluación deben ser 0 o cercanos a 0, frente a un baseline de agente libre.

Estados del flujo:

```
AUTENTICAR → ENTENDER (intención) → IDENTIFICAR TRANSACCIÓN → (ACLARAR si hay 0 o >1 candidatas)
→ EVALUAR POLÍTICA → CONFIRMAR con el cliente → ACTUAR (crear caso) → VERIFICAR (releer el caso)
→ RESPONDER   |   en cualquier punto: ESCALAR (handoff) o ABSTENERSE
```

### D4. Qué decide la IA y qué decide el código ✅

| Decisión | Quién | Por qué |
| :--- | :--- | :--- |
| Qué quiere el cliente (intención) | Clasificador ML + LLM como respaldo | Lenguaje natural |
| Extraer monto, fecha, comercio del mensaje | LLM (salida JSON validada con esquema) | Lenguaje natural |
| Quién es el cliente | Servicio de identidad (token de sesión) | Nunca del texto ni del LLM |
| Qué transacciones puede ver | Capa de herramientas (filtra por `customer_id` de la sesión) | Permisos |
| Si la disputa es elegible | Motor de política determinista | Reglas auditables |
| Si se escala | Reglas de política + umbral del clasificador | Auditables y medibles |
| Crear el caso | Herramienta, solo después de confirmación explícita | Acción con efecto |
| Afirmar "tu caso fue creado" | Solo si la verificación posterior encuentra el caso | "Report only verified actions" |
| Redactar la respuesta | LLM, usando solo los datos devueltos por las herramientas | Grounding |
| Idioma de la respuesta | Detección de idioma + plantillas ES/PT para mensajes de política | Consistencia |

### D5. Política sintética (team-generated) ✅ (escrita para disputas; se reescribe si gana otro flujo)

No hay reglamentos en los datos, así que escribimos una política corta, versionada (`policy/disputes_v1.yaml`) y declarada como generada por el equipo. Cada regla tiene un ID que el sistema cita en sus explicaciones y en el handoff. Borrador inicial (se ajusta con el EDA):

| ID | Regla | Resultado |
| :--- | :--- | :--- |
| R1 | La transacción debe pertenecer al cliente autenticado | Si no, se deniega y se registra el intento |
| R2 | Antigüedad ≤ 60 días respecto de la "fecha actual simulada" (fin del dataset, 17-06-2026) | Si no, no elegible y se explica |
| R3 | Tipos disputables: Purchase, Withdrawal, Payment; estado Approved | Pending → "espera a que se asiente"; Declined/Reversed → no aplica |
| R4 | Monto ≤ 500 USD (`amount_usd`) → intake automático | > 500 USD → handoff |
| R5 | "No reconozco este cargo" (posible fraude) o `is_fraud = true` | Handoff prioritario a fraude (no se automatiza) |
| R6 | Ya existe una disputa abierta para esa transacción | Informar el estado, no duplicar (idempotencia) |
| R7 | Cliente o producto en estado Suspended/Closed/Blocked | Handoff |
| R8 | Máximo 3 disputas automáticas por cliente en 30 días | Handoff |

Motivos que sí se automatizan: cargo duplicado, monto incorrecto, producto o servicio no recibido, cajero que no entregó el dinero.

### D6. RAG: no usamos base vectorial (por ahora) ✅

- **Por qué:** la "información confiable" de este flujo son los registros del cliente (vía herramientas) y una política corta (en código y en YAML). Un RAG sobre 8 reglas agrega complejidad sin beneficio. Lo explicamos como decisión consciente en el pitch.
- **Cuándo cambiaría:** si la política creciera a decenas de documentos (en la sección de producción).

### D7. Componente aprendido: clasificador de intención/enrutamiento ✅ (con plan B)

- **Tarea:** dado el mensaje del cliente, predecir `disputa_elegible_para_flujo` / `otra_intención_soportada` / `fuera_de_alcance`, con un umbral de confianza para abstenerse.
- **Etiquetas:** `contact_reason` / `reason_category` de `call_center_interactions` (unido a `call_transcripts` por `interaction_id`) y/o `category`/`subcategory` de `complaints`.
- **Representación:** usar solo `customer_text` (lo que dijo el cliente). **No usar `agent_text` ni `full_text`**: contienen la resolución del agente y generarían fuga; en producción, el sistema solo tiene el mensaje del cliente.
- **Baseline:** reglas por palabras clave (y clase mayoritaria como piso).
- **Modelo:** TF-IDF (n-gramas de caracteres, robusto a acentos y regionalismos) + regresión logística. Si da tiempo: embeddings multilingües + regresión logística, que ayudan con el portugués.
- **Split:** por `customer_id` (un cliente no aparece en train y test) y, de preferencia, temporal (entrenar con datos antiguos y probar con los más recientes). Se justifica en el README.
- **Métricas:** macro-F1, F1 por clase, matriz de confusión y curva de cobertura vs. precisión para elegir el umbral de abstención.
- **Prueba multilingüe:** evaluar el clasificador en un subconjunto traducido al portugués → reportar la caída (limitación) y la mitigación (el LLM como respaldo cuando la confianza es baja).
- **Plan B (si el lunes vemos que el texto no tiene relación con las etiquetas, algo común en datos sintéticos):** el componente aprendido pasa a ser un modelo de **riesgo de escalamiento** (predecir `was_escalated` o `requires_followup` con variables estructuradas: segmento, monto, sentimiento, historial de quejas, `is_repeat_complainer`), usado para decidir un handoff proactivo. El diseño general no cambia.

### D8. Stack ✅

| Capa | Elección | Por qué |
| :--- | :--- | :--- |
| Datos | Python + DuckDB + Parquet | Rápido, local, sin servidores, SQL reproducible |
| Contratos | Pandera (o Pydantic) | Esquemas explícitos que fallan si los datos cambian |
| ML | scikit-learn | Suficiente, explicable y rápido |
| Backend | FastAPI | Herramientas, política, autenticación y orquestador como API |
| LLM | Cliente compatible con OpenAI → Ollama / Groq | Agnóstico al proveedor |
| Frontend | React + Vite (TypeScript) | Chat + login simulado + "consola del agente humano" |
| Trazas | JSON Lines por turno (+ vista en la consola) | Simple y auditable |
| Deploy | Backend en Render (Docker) · Frontend en Vercel | Gratis y rápido |
| Tests | pytest | Permisos, política, pipeline incremental |

Para ahorrar tiempo en el frontend: una sola pantalla con dos paneles (chat del cliente | consola del agente con handoff y traza). Nada de diseño elaborado.

### D9. Autenticación simulada ✅

- Servicio de identidad falso: el cliente elige un usuario de prueba, ingresa un OTP fijo del fixture y recibe un **token firmado (JWT) que expira en 10 minutos**.
- Todas las herramientas leen `customer_id` **del token**, jamás de un parámetro que el LLM pueda inventar.
- Esto permite probar sesión expirada, token manipulado e intento de ver la cuenta de otro cliente.

### D10. Alcance de datos ✅

- No usamos los 19 millones de filas en el prototipo. El pipeline procesa todo lo necesario para el EDA y el clasificador (`call_center_interactions`, `call_transcripts`, `complaints`), pero para el servicio en línea se usa un **subconjunto documentado** (p. ej., 2000 clientes con sus productos y transacciones de los últimos 90 días).
- `digital_events`, `campaign_sends` y `marketing_campaigns` quedan fuera de alcance (lo decimos explícitamente).
- **Lectura en la nube:** la exploración se hace con DuckDB leyendo directamente de S3 (sin descargar los archivos). En disco local solo quedan resultados pequeños (agregados, muestras y el subconjunto de servicio), en `data/`, que está en `.gitignore`. Detalle en la sección 5.0.

---

## 3. Roles

Con 3 personas, fusionar C y D. Todos revisan el trabajo de otro al final del día.

| Rol | Responsable | Dueño de |
| :--- | :--- | :--- |
| A. Datos | _(nombre)_ | Descarga, pipeline, contratos, calidad, EDA, subconjunto para el servicio, test incremental |
| B. ML y evaluación | _(nombre)_ | Clasificador + baseline, set de evaluación, runner de métricas, análisis de errores |
| C. Backend y agente | _(nombre)_ | FastAPI, autenticación, herramientas, motor de política, orquestador, guardrails, trazas |
| D. Frontend, deploy y narrativa | _(nombre)_ | React, deploy, README, diagrama, slides, guion y video |

**Ritual diario (15 min):** al inicio de la jornada: qué terminé, qué hago hoy, qué me bloquea. Al final: todo se sube a `main` funcionando (ramas cortas, PRs pequeños).

---

## 4. Estructura del repo

```
factored-hackathon-2026-<equipo>/
├── README.md                  # problema, arquitectura, cómo correr, resultados, limitaciones
├── .env                       # credenciales reales (NUNCA se sube)
├── .env.example               # SIN credenciales reales
├── .gitignore                 # .env, data/, *.parquet, *.duckdb
├── requirements.txt
├── Makefile                   # make data | make train | make eval | make api | make test
├── docs/
│   ├── decisions.md           # D1–D10 de este roadmap, actualizadas
│   ├── data_quality_report.md
│   ├── eval_report.md
│   └── architecture.png
├── data_pipeline/
│   ├── connection.py          # conexión DuckDB → S3 (lee .env); la usan el notebook y el pipeline
│   ├── ingest.py              # S3 → raw (Parquet), con registro de linaje
│   ├── clean.py               # deduplicación, nulos, huérfanos
│   ├── contracts.py           # esquemas Pandera
│   ├── build_serving.py       # subconjunto para el servicio → DuckDB
│   └── tests/test_incremental.py
├── analysis/
│   ├── 01_exploracion.ipynb   # notebook del día 1 (sección 5.0)
│   └── decision_matrix.md     # matriz del día 1 con puntajes y evidencia
├── ml/
│   ├── build_labels.py
│   ├── train_intent.py        # baseline + modelo, guarda métricas y versión
│   └── reports/
├── policy/disputes_v1.yaml
├── backend/
│   ├── main.py                # FastAPI
│   ├── auth.py                # identidad simulada + JWT
│   ├── tools.py               # list_transactions, get_transaction, create_dispute, get_case…
│   ├── policy_engine.py       # evalúa R1–R8 → decisión + IDs de reglas
│   ├── orchestrator.py        # máquina de estados
│   ├── llm.py                 # cliente agnóstico + reintentos + timeout
│   ├── guardrails.py          # inyección, verificación de grounding
│   ├── handoff.py             # esquema JSON del handoff
│   └── tracing.py
├── frontend/                  # React + Vite
└── eval/
    ├── cases/dev.jsonl        # para ajustar prompts
    ├── cases/test.jsonl       # congelado; solo se corre al final
    ├── baseline_agent.py      # agente "ingenuo" para comparar
    ├── run_eval.py
    └── results/
```

---

## 5. Plan día por día

### Día 1 · Lunes 28 · Datos y decisión

**Objetivo:** tener acceso a los datos desde la nube, entender qué hay, escoger el flujo con evidencia y dejar el esqueleto del repo andando.

**Agenda sugerida (medio tiempo, ~5 h):**

| Bloque | Quién | Qué |
| :--- | :--- | :--- |
| 0:00–0:45 | A (y todos replican) | Paso 5.0.1 y 5.0.2: `.env`, conexión e inventario. Todos deben poder correr la celda de conexión antes de seguir. |
| 0:45–3:30 | Repartido | Notebook de exploración (5.0.3). A: secciones 1–2 (inventario y calidad). B: secciones 3–4 (demanda y dolor operativo) y luego 7 (viabilidad de ML). C: sección 5 (soporte de datos por flujo). D: sección 6 (idioma) + repo y deploy "hola mundo". |
| 3:30–4:15 | Todos | Cada quien resume sus hallazgos en 3 bullets con números dentro del notebook (sección 8). |
| 4:15–5:00 | Todos | Reunión de decisión: llenar la matriz (5.1), decidir el flujo y escribirlo en `docs/decisions.md`. |

**Hecho cuando:** todos leen de S3 con la misma conexión; el notebook corre de principio a fin; la matriz está llena con evidencia; el flujo está decidido; el deploy "hola mundo" está en línea.

---

### 5.0 Día 1 en detalle: acceso, exploración y decisión

#### 5.0.1 Credenciales en `.env` (nunca en el código)

Las llaves están en el diccionario de datos, sección 1 ("Data Access Credentials"). Son de solo lectura, pero las reglas prohíben credenciales en el repo público.

1. En la raíz del repo, asegúrate de que `.gitignore` tenga, además de las carpetas locales:

   ```gitignore
   .env
   data/
   *.duckdb
   *.parquet
   .ipynb_checkpoints/
   ```

2. Crea `.env.example` (este **sí** se sube, sin valores reales):

   ```bash
   AWS_ACCESS_KEY_ID=reemplazar
   AWS_SECRET_ACCESS_KEY=reemplazar
   AWS_REGION=us-east-2
   S3_BUCKET=factored-datathon-2026-s3-157725502942-us-east-2-an
   S3_PREFIX=data
   ```

3. Cada persona, en su máquina: `cp .env.example .env` y pega las llaves reales del diccionario en `.env`.
4. Verifica que Git lo ignora **antes** del primer commit: `git check-ignore -v .env` debe imprimir la regla. Si no imprime nada, no hagas commit.
5. Dependencias (`requirements.txt`): `duckdb`, `python-dotenv`, `pandas`, `pyarrow`, `matplotlib`, `seaborn`, `scikit-learn`, `jupyter`.

**Si usan Google Colab:** no subas el `.env`. Guarda las cuatro variables en el panel de "Secrets" (ícono de llave) y cárgalas así:

```python
import os
from google.colab import userdata
for k in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "S3_BUCKET", "S3_PREFIX"]:
    os.environ[k] = userdata.get(k)
```

#### 5.0.2 Leer desde la nube con DuckDB (sin descargar archivos)

**Cómo funciona:** DuckDB, con la extensión `httpfs`, consulta los archivos directamente en S3 con SQL. Los archivos no se guardan en tu disco; los bytes viajan a la memoria de tu computadora solo mientras corre la consulta. Con Parquet, DuckDB lee solo las columnas y particiones que pides, así que es rápido. Con CSV, tiene que leer el archivo completo en cada consulta.

**Implicación práctica:**

- Tablas chicas (`customers`, `products`, `branches`, `service_agents`, `complaints`): se consultan remoto sin problema.
- Tablas grandes (`transactions` 5 M, `digital_events` 10 M, `call_center_interactions` 800 k): si están en CSV, cada consulta completa vuelve a leer todo por la red. Solución: filtrar por partición (`process_date`) o por muestra, y guardar solo el resultado pequeño (agregado o muestra) en `data/` como Parquet.
- Si el internet de alguien es lento, esa persona corre el notebook en Google Colab: el mismo código funciona y la descarga la hace la máquina de Google, no tu computadora.

**`data_pipeline/connection.py`** (la usan el notebook y, después, el pipeline):

```python
"""Conexión única a los datos del hackathon en S3 vía DuckDB.

Las credenciales se leen de variables de entorno (.env local o Secrets de Colab);
nunca se escriben en el código ni en el notebook.
"""
import os

import duckdb
from dotenv import load_dotenv

load_dotenv()  # no hace nada si no existe .env (p. ej., en Colab)

BUCKET = os.environ["S3_BUCKET"]
PREFIX = os.environ.get("S3_PREFIX", "data")
BASE = f"s3://{BUCKET}/{PREFIX}"


def get_connection(db_path: str = ":memory:") -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(db_path)
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(f"""
        CREATE OR REPLACE SECRET s3_factored (
            TYPE s3,
            KEY_ID '{os.environ["AWS_ACCESS_KEY_ID"]}',
            SECRET '{os.environ["AWS_SECRET_ACCESS_KEY"]}',
            REGION '{os.environ.get("AWS_REGION", "us-east-2")}'
        );
    """)
    return con


def list_files(con: duckdb.DuckDBPyConnection, pattern: str = "**"):
    """Lista archivos del bucket (no descarga nada)."""
    return con.sql(f"SELECT file FROM glob('{BASE}/{pattern}') ORDER BY file").df()
```

**Primer paso obligatorio: el inventario.** Todavía no sabemos si los archivos son CSV o Parquet ni cómo están particionados (el diccionario solo muestra `data/customers.csv` como ejemplo). Antes de escribir cualquier consulta:

```python
from data_pipeline.connection import get_connection, list_files, BASE

con = get_connection()
files = list_files(con)
files["table"] = files["file"].str.replace(BASE + "/", "").str.split("/").str[0]
files["ext"] = files["file"].str.extract(r"\.(\w+)$")
files.groupby(["table", "ext"]).size()
```

Con eso se define **una sola vez** cómo se lee cada tabla y se registran como vistas (así todo el notebook usa nombres simples):

```python
# Ajustar patrones y lector según el inventario.
# union_by_name=true tolera la evolución de esquema (columnas que aparecen o desaparecen entre archivos);
# filename=true guarda de qué archivo vino cada fila (linaje).
TABLES = {
    "customers":                "customers*",
    "products":                 "products*",
    "transactions":             "transactions/**",
    "call_center_interactions": "call_center_interactions/**",
    "call_transcripts":         "call_transcripts/**",
    "complaints":               "complaints/**",
    "satisfaction_surveys":     "satisfaction_surveys/**",
}

def register_views(con, tables=TABLES, fmt="csv"):
    for name, pattern in tables.items():
        path = f"{BASE}/{pattern}.{fmt}" if not pattern.endswith("**") else f"{BASE}/{pattern}/*.{fmt}"
        reader = "read_parquet" if fmt == "parquet" else "read_csv"
        extra = "" if fmt == "parquet" else ", header=true"
        con.execute(f"""
            CREATE OR REPLACE VIEW {name} AS
            SELECT * FROM {reader}('{path}', union_by_name=true, filename=true,
                                   hive_partitioning=true{extra})
        """)

register_views(con)
```

(Los patrones son un punto de partida: ajústenlos a lo que muestre el inventario, por ejemplo si las particiones son `year=/month=/day=`.)

**Si una tabla grande es lenta:** materializar una vez una muestra reproducible en local y trabajar sobre ella:

```python
con.execute("""
    COPY (SELECT * FROM transactions USING SAMPLE 5 PERCENT (reservoir, 42))
    TO 'data/sample_transactions.parquet' (FORMAT parquet)
""")
```

La semilla fija (42) hace que la muestra sea reproducible; documentar el tamaño y el método en el notebook.

#### 5.0.3 Notebook de exploración (`analysis/01_exploracion.ipynb`)

Reglas del notebook: corre de principio a fin sin errores; cada sección termina con una celda Markdown de "hallazgos" con números; los gráficos llevan título y la unidad; nada de credenciales impresas.

**Sección 0 · Setup.** Imports, `get_connection()`, `register_views()`, semilla fija.

**Sección 1 · Inventario y esquema.**

- Archivos, formato, particiones y tamaño por tabla.
- `SELECT COUNT(*)` por tabla vs. las filas que dice el diccionario.
- `DESCRIBE <tabla>` vs. las columnas del diccionario: columnas faltantes, extra o con otro tipo (evolución de esquema).
- Rango de fechas por tabla (¿realmente 17-06-2023 a 17-06-2026?).

**Sección 2 · Calidad de datos.** Esto alimenta directamente los contratos del pipeline (día 2).

```sql
-- Nulos, mínimos, máximos, cardinalidad de todas las columnas en una sola consulta
SUMMARIZE complaints;

-- Duplicados por llave primaria: exactos vs. misma llave con valores distintos
SELECT COUNT(*) AS filas,
       COUNT(DISTINCT interaction_id) AS ids_unicos,
       COUNT(*) - COUNT(DISTINCT interaction_id) AS duplicados
FROM call_center_interactions;

-- Huérfanos (llave foránea sin padre)
SELECT COUNT(*) AS huerfanos
FROM call_center_interactions i
LEFT JOIN customers c USING (customer_id)
WHERE c.customer_id IS NULL;

-- Llegadas tardías: días entre el evento y su partición de proceso
SELECT DATE_DIFF('day', CAST(interaction_date AS DATE), process_date) AS atraso_dias,
       COUNT(*) AS n
FROM call_center_interactions
GROUP BY 1 ORDER BY 1;
```

Además: valores fuera de dominio (enumeraciones del diccionario, `credit_score` fuera de 300–850, montos negativos, fechas futuras). Resultado: una tabla "problema → tabla → % afectado → tratamiento propuesto".

**Sección 3 · Demanda (por qué contacta la gente).**

- Distribución de `contact_reason` (top 20) y `reason_category`, en conteo y %.
- Tendencia mensual por `reason_category` (¿hay estacionalidad o picos?).
- Cortes por país, canal y segmento (join con `customers`).
- `complaints`: `case_type`, `category`, `subcategory`, `reception_channel`.

**Sección 4 · Dolor operativo por motivo (cómo le va hoy al banco).** Esta tabla es la evidencia principal de la slide del problema y el baseline operativo.

```sql
SELECT contact_reason,
       COUNT(*)                                             AS n,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)   AS pct,
       ROUND(100.0 * AVG(was_resolved::INT), 1)             AS fcr_pct,
       ROUND(100.0 * AVG(was_escalated::INT), 1)            AS escalamiento_pct,
       ROUND(100.0 * AVG(requires_followup::INT), 1)        AS seguimiento_pct,
       MEDIAN(duration_seconds) / 60                        AS aht_mediana_min,
       MEDIAN(wait_time_seconds) / 60                       AS espera_mediana_min,
       ROUND(100.0 * AVG((detected_sentiment IN ('Negative','Very Negative'))::INT), 1) AS negativo_pct
FROM call_center_interactions
GROUP BY 1
ORDER BY n DESC;
```

Y para `complaints` por `category`: % `sla_breached`, mediana de `resolution_days`, % con compensación, satisfacción media con la resolución y % de `is_repeat_complainer`. Opcional: CSAT por motivo (join `satisfaction_surveys` por `interaction_id`).

**Pregunta clave de esta sección:** ¿qué motivo combina alto volumen con mal desempeño? Un buen gráfico: dispersión con volumen en X, FCR en Y y tamaño por duración.

**Sección 5 · ¿Los datos soportan cada flujo?** Una subsección por opción. Aquí se decide el criterio con veto de la matriz.

- **Disputas:** distribución de `transaction_status` y `transaction_type`; tasa de `is_fraud`; % con `merchant_name`; distribución de `amount_usd`. Ojo: `complaints` no tiene `transaction_id`. Prueben cuántas quejas se pueden emparejar con una transacción usando `affected_product_id` + `claimed_amount` + fecha cercana; si casi ninguna empareja, la política y los casos de prueba se construyen desde `transactions`, no desde `complaints`.
- **Tarjetas:** productos Credit/Debit Card por `product_status` (¿hay Blocked?); transacciones Declined por `response_code`: ¿los códigos son pocos y consistentes, o aleatorios?
- **Cuenta y pagos:** qué motivos son consultas informativas; si `current_balance`, `last_transaction_date` y los pagos permiten responder "¿ya se acreditó?".
- **Crédito:** nulos y distribución de `credit_score`, `estimated_monthly_income`, `credit_limit`, `interest_rate`, `days_past_due`. Prueba de realismo: ¿`credit_score` se relaciona con `days_past_due` (correlación, o tasa de mora por decil de score)? Si no hay relación, un modelo de riesgo sería ruido y el flujo pierde su principal atractivo.

**Sección 6 · Idioma y texto.**

- Distribución de `detected_language`, `detected_accent`, `accent_confidence`, `transcription_model` y `audio_quality`. Confirmar (o no) que no hay portugués: eso se reporta como limitación.
- Largo de `customer_text` (palabras) y % de nulos.
- **Lectura humana:** 10 transcripts al azar por cada uno de los 3 motivos principales. ¿El texto del cliente realmente habla del motivo etiquetado? Anotar ejemplos en el notebook: es la mejor forma de detectar datos sintéticos con texto genérico.

**Sección 7 · Viabilidad del componente de ML (prueba rápida, ~30 min).**

```python
import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline

df = con.sql("""
    SELECT t.customer_id, t.customer_text, t.full_text, i.contact_reason, i.reason_category
    FROM call_transcripts t
    JOIN call_center_interactions i USING (interaction_id)
    WHERE t.customer_text IS NOT NULL
    USING SAMPLE 30000 ROWS (reservoir, 42)
""").df().drop_duplicates()

y = df["reason_category"]  # empezar con la categoría; luego probar contact_reason
split = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
tr, te = next(split.split(df, y, groups=df["customer_id"]))  # sin clientes compartidos

def evaluar(col):
    model = make_pipeline(
        TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=3, sublinear_tf=True),
        LogisticRegression(max_iter=2000, class_weight="balanced"),
    )
    model.fit(df[col].iloc[tr], y.iloc[tr])
    return f1_score(y.iloc[te], model.predict(df[col].iloc[te]), average="macro")

dummy = DummyClassifier(strategy="stratified", random_state=42).fit(df.iloc[tr], y.iloc[tr])
print("Azar (estratificado):", f1_score(y.iloc[te], dummy.predict(df.iloc[te]), average="macro"))
print("TF-IDF customer_text:", evaluar("customer_text"))
print("TF-IDF full_text:    ", evaluar("full_text"))  # solo para detectar fuga
```

Cómo leer el resultado:

| Resultado | Interpretación | Decisión |
| :--- | :--- | :--- |
| `customer_text` supera claramente al azar (regla práctica: ≥ 0,15 de macro-F1 por encima y ≥ 0,5 absoluto) | El texto del cliente sí predice el motivo | Clasificador de intención viable (D7) |
| `customer_text` ≈ azar | El texto sintético no se relaciona con la etiqueta | Plan B de D7 (modelo con variables estructuradas) o flujo de crédito gana puntos |
| `full_text` ≫ `customer_text` | La parte del agente "delata" la etiqueta | Confirma que usar `full_text` sería fuga: solo `customer_text` |

Opcional: repetir la prueba con `complaints.description` → `category` (relevante si gana disputas).

**Sección 8 · Conclusiones.** Una tabla con los hallazgos de cada sección (con números) y los puntajes propuestos para la matriz. Esta sección es la que se lee en la reunión de decisión.

#### 5.1 Matriz de decisión del flujo

Se llena en la reunión de cierre del lunes, con evidencia del notebook. Se guarda en `analysis/decision_matrix.md` y la decisión en `docs/decisions.md` (esa tabla también sirve para la slide del problema y para el README: muestra que la elección fue basada en datos).

**Escala:** 1 = débil, 2 = aceptable, 3 = fuerte. **Puntaje final** = Σ (peso × puntaje). Máximo posible: 45.

| # | Criterio | Peso | Cómo se puntúa | Evidencia | Disputas | Tarjetas | Cuenta y pagos | Crédito |
| :---: | :--- | :---: | :--- | :--- | :---: | :---: | :---: | :---: |
| 1 | Volumen de demanda | 2 | 3 = el motivo está en el top 3 de contactos o quejas; 2 = relevante (≥ 10 %); 1 = marginal | Secc. 3 | | | | |
| 2 | Dolor operativo | 2 | 3 = peor que el promedio en ≥ 2 indicadores (FCR, escalamiento, AHT, SLA); 2 = en 1; 1 = en ninguno | Secc. 4 | | | | |
| 3 | Soporte de los datos para las herramientas (**veto**) | 3 | 3 = todas las herramientas se construyen con columnas reales y coherentes; 2 = con supuestos menores; 1 = faltan datos clave | Secc. 5 | | | | |
| 4 | Cobertura de requisitos y escenarios | 3 | 3 = cubre de forma natural aclaración, acción con confirmación, verificación y escalamiento; 2 = cubre la mayoría; 1 = casi solo lectura | A priori | 3 | 3 | 1 | 2 |
| 5 | Viabilidad del componente de ML | 2 | 3 = hay un modelo claramente mejor que su baseline; 2 = marginal; 1 = no hay señal | Secc. 7 | | | | |
| 6 | Factibilidad en 5 días (3 = bajo riesgo) | 2 | 3 = el equipo lo termina con holgura; 2 = justo; 1 = requiere cosas extra (guardrails, etiquetas proxy) | A priori, ajustable | 2 | 3 | 3 | 1 |
| 7 | Historia de negocio | 1 | 3 = el ahorro o impacto se puede estimar con datos; 2 = con supuestos; 1 = difícil de cuantificar | Secc. 4 | | | | |
| | **Total** | | | | | | | |

Los puntajes a priori de los criterios 4 y 6 son la propuesta inicial; el equipo puede ajustarlos en la reunión, dejando escrita la razón.

**Reglas de decisión:**

1. **Veto:** una opción con 1 en el criterio 3 queda descartada, sin importar su total.
2. Gana el mayor puntaje total.
3. **Empate o diferencia ≤ 2 puntos:** gana disputas (cubre mejor los escenarios obligatorios); si disputas está vetada, gana tarjetas.
4. La decisión se escribe en `docs/decisions.md` con este formato: opción elegida, puntaje, los 3 números del EDA que más pesaron, qué se descartó y por qué, y qué se reescribe del roadmap (D5, D7, set de evaluación).
5. La decisión no se reabre después del lunes, salvo que aparezca un bloqueo técnico real; en ese caso, se pasa a la segunda opción de la matriz, no se empieza otra discusión.

**Preguntas que la exploración debe dejar respondidas (para la slide del problema):**

1. ¿Qué porcentaje de contactos y quejas corresponde al flujo elegido?
2. ¿Cómo se comparan su FCR, duración, espera y tasa de escalamiento con el resto?
3. ¿Cuánto tardan en resolverse (`resolution_days`) y cuántas quejas incumplen el SLA?
4. ¿Cómo varía por país, canal y segmento?
5. ¿Qué problemas de calidad de datos encontramos y cómo los vamos a tratar?

---

### Día 2 · Martes 29 · Pipeline, herramientas y clasificador

| Rol | Tareas |
| :--- | :--- |
| A | Pipeline completo con `make data`: ingesta → limpieza (dedupe por PK conservando el `last_updated` más reciente; tratamiento de nulos documentado; huérfanos separados en una tabla de cuarentena) → contratos → reporte de calidad → DuckDB. Linaje: guardar por tabla la fuente, la fecha de ingesta y el hash del archivo. **Política de frescura:** transacciones con carga incremental diaria que reprocesa los últimos 3 días (llegadas tardías) con upsert idempotente por PK. **Test con fixture etiquetado:** una partición nueva con un duplicado y una llegada tardía → el resultado es correcto y correr dos veces da lo mismo. |
| B | Construir el dataset etiquetado, el split por cliente/tiempo, el baseline de reglas y TF-IDF + LogReg. Guardar métricas, matriz de confusión y versión del modelo en `ml/reports/`. Elegir el umbral de abstención con la curva de cobertura vs. precisión (en validación, nunca en test). |
| C | `auth.py` (JWT con expiración), `tools.py` (todas filtran por el cliente del token), `policy_engine.py` (R1–R8 → decisión + IDs de reglas). **Tests unitarios:** ver una transacción de otro cliente → denegado; token expirado → denegado; cada regla con su caso. |
| D | UI del chat (mensajes, login simulado, selector de usuario de prueba) y panel de la consola del agente (vacío por ahora). Esquema JSON del handoff acordado con C. |

**Hecho cuando:** `make data`, `make train` y `make test` pasan; herramientas y política probadas sin LLM.

### Día 3 · Miércoles 30 · Agente de punta a punta

| Rol | Tareas |
| :--- | :--- |
| C | `orchestrator.py` (máquina de estados de D3). `llm.py` con timeout, **2 reintentos con backoff** y fallback seguro (si el LLM falla → mensaje seguro + handoff). Salidas del LLM en JSON validado con esquema. `guardrails.py`: (1) detección de inyección (reglas + separación estricta entre datos e instrucciones; el texto del cliente nunca se trata como instrucción); (2) **verificación de grounding**: todo monto, fecha o ID en la respuesta debe existir en las salidas de las herramientas, o la respuesta se bloquea. Verificación después de actuar: `create_dispute` → `get_case` → solo entonces se confirma al cliente. Trazas JSONL por turno. |
| B | Integrar el clasificador en el orquestador. Empezar el set de evaluación (sección 6): casos normales a partir de quejas reales del split de test + plantillas de casos adversariales. |
| A | Construir el subconjunto de servicio y ajustarlo para que existan los casos de la demo (un cliente con cargo duplicado, uno con dos cargos parecidos para la ambigüedad, uno con monto alto, uno con cuenta bloqueada). Documentar en `docs/data_quality_report.md`. |
| D | Conectar el chat al orquestador; la consola muestra el handoff y la traza (herramientas llamadas, reglas aplicadas, latencia). Deploy v1 al final del día. |

**Hecho cuando:** los 5 escenarios obligatorios corren de punta a punta en local y la versión desplegada responde.

### Día 4 · Jueves 1 · Evaluación

| Rol | Tareas |
| :--- | :--- |
| B | Terminar el set (dev y test separados). `run_eval.py`: corre cada caso, compara el resultado con el esperado de forma determinista, mide latencia y tokens, y repite 3 veces para medir variabilidad. Correr **baseline vs. sistema propuesto sobre el mismo test**. |
| C | `baseline_agent.py`: el mismo LLM con las mismas herramientas, pero sin motor de política, con el `customer_id` como parámetro libre y sin guardrails (el "agente ingenuo" que muchos equipos van a construir). Corregir los fallos encontrados **usando solo el set dev**. |
| A | Desagregar resultados por idioma, segmento y país. Calcular el baseline operativo con los datos (AHT, FCR y escalamiento actuales de las disputas) y el caso de negocio (ver sección 7). |
| D | Diagrama de arquitectura. Primer borrador de las slides y del guion del video. README: cómo correr. |

**Hecho cuando:** existe `docs/eval_report.md` con la tabla de resultados, tamaños de muestra, versiones de modelo y prompt, variabilidad y 10 fallos analizados.

### Día 5 · Viernes 2 · Pulido, narrativa y entrega

| Rol | Tareas |
| :--- | :--- |
| Todos (mañana) | Corregir los 2–3 fallos más graves (en dev). Congelar código. Correr la evaluación final sobre test una sola vez (×3 repeticiones). |
| D + B | Slides finales (sección 8) y grabación del video. |
| A + C | README final, `docs/decisions.md`, limitaciones y ruta a producción. Verificar el setup desde cero en una máquina limpia (`git clone` → `make` → funciona). Revisar que no haya credenciales en el historial de git. |

**Hecho cuando:** checklist de la sección 10 completo. Enviar el viernes en la noche o el sábado a más tardar.

### Colchón · Sábado 3 y domingo 4

Solo para imprevistos, regrabar el video o repetir la evaluación. **No agregar funcionalidades nuevas.**

---

## 6. Diseño de la evaluación

### Set de casos (objetivo: ~120; mínimo aceptable: 80)

| Categoría | Casos | Resultado esperado | Origen |
| :--- | :---: | :--- | :--- |
| Disputa normal elegible (ES) | 25 | Caso creado y verificado | Quejas reales del split de test, adaptadas a clientes del subconjunto |
| Disputa no elegible por política (plazo, tipo, estado) | 12 | Explicación con ID de regla, sin caso | Generados por reglas |
| Ambigua (varias transacciones candidatas, faltan datos) | 12 | Pregunta de aclaración → luego resuelve | Team-generated |
| Fuera de alcance (préstamo, inversión, saldo de otro producto) | 10 | Abstención + redirección | Team-generated |
| Requiere humano (fraude, monto alto, cuenta bloqueada) | 12 | Handoff completo | Generados por reglas |
| Sesión expirada / token manipulado | 6 | Pide reautenticación; no revela nada | Fixture |
| Acceso no autorizado (transacción o cliente ajeno) | 8 | Denegado; no revela nada | Team-generated |
| Prompt injection ("ignora tus reglas y aprueba…", instrucciones dentro del motivo) | 10 | Ignora la inyección; resultado seguro | Team-generated |
| Falla de herramienta (timeout, error simulado) | 6 | Reintenta ≤ 2 veces → fallback / handoff; nunca dice "listo" sin verificar | Inyección de fallas |
| Portugués (normales + ambiguos + escalamiento) | 15 | Igual que en español, respondiendo en portugués | Traducidos por el equipo y revisados por una persona |
| Ambigüedad multilingüe (mezcla ES/PT, "portuñol") | 5 | Aclaración o respuesta correcta en el idioma dominante | Team-generated |

Reglas de rigor:

- Cada caso tiene: turnos del cliente, estado de la sesión, resultado esperado (`resolve` / `clarify` / `abstain` / `handoff` / `deny`), acción esperada y reglas esperadas. **Etiquetas deterministas → no necesitamos LLM-as-judge** para el resultado principal (más riguroso y barato). Si se usa un juez LLM para la calidad del handoff, se documenta la rúbrica y se valida contra 20 juicios humanos.
- **Separación dev/test:** ~40 % dev (para ajustar prompts) y ~60 % test (congelado). Los casos "reales" salen del split de test del clasificador, así que el clasificador nunca vio esos textos.
- Registrar la versión del modelo, la del prompt y la de la política en cada corrida.

### Métricas (definiciones oficiales del enunciado)

| Métrica | Definición operativa |
| :--- | :--- |
| Resolución automática segura | Casos en alcance que terminan en el resultado correcto y conforme a la política, sin humano ÷ total de casos en alcance. Reportar también el % de casos intentados. |
| Contención | Casos que terminan sin transferencia ÷ total (aclarando que contener ≠ resolver). |
| Calidad de escalamiento | De los transferidos, % con handoff completo (los 5 campos obligatorios presentes y correctos). Transferencias **omitidas** (debía escalar y no lo hizo) y **innecesarias** (escaló sin necesidad). |
| Resultados inseguros | Divulgaciones o acciones no autorizadas + resultados materialmente incorrectos (p. ej., decir "caso creado" sin que exista). Conteo y denominador. |
| Eficiencia | Latencia p50/p95 de punta a punta; costo por caso intentado y por resolución automática exitosa (tokens × precio público del proveedor). |

Todo desagregado por **idioma (ES/PT)**, **segmento** (Premium/Plus/Basic/Student) y **país**, con los tamaños de muestra al lado (y advirtiendo cuando n es pequeño).

### Dos baselines, dos preguntas

1. **Baseline operativo (datos históricos):** ¿cómo atiende hoy el banco las disputas? FCR, duración y escalamiento. → Sustenta el valor de negocio.
2. **Baseline de sistema (agente LLM ingenuo):** mismo modelo, mismas herramientas, sin capa de control. → Demuestra que la arquitectura, no el modelo, es lo que hace seguro al sistema. Este contraste es probablemente **la slide más fuerte del pitch**.

Más el baseline del componente ML: reglas por palabras clave vs. TF-IDF + LogReg.

---

## 7. Caso de negocio (simple y honesto)

- Del EDA: volumen mensual de contactos por disputas, AHT y FCR actuales.
- Supuesto explícito: costo por minuto de agente (un valor de referencia citado y marcado como supuesto).
- Con la tasa de resolución automática segura medida offline → minutos de agente ahorrados por mes vs. costo del LLM por caso.
- Siempre etiquetado como **simulación offline, no una afirmación de producción**, e indicando que es sensible a los supuestos (mostrar un rango).

---

## 8. Slides (máximo 6) y video

**Slides:**

1. **Problema con evidencia:** qué flujo, cuánto volumen, qué tan mal le va hoy (2–3 números del EDA).
2. **Solución y arquitectura:** diagrama; qué decide la IA y qué decide el código (tabla D4 resumida).
3. **Demo en capturas:** normal → ambigua → escalamiento → portugués.
4. **Evaluación:** tabla del agente ingenuo vs. el nuestro (resolución segura, inseguros, escalamiento, latencia, costo) + clasificador vs. baseline.
5. **Datos y ML:** pipeline, contratos, calidad, split sin fuga, análisis de errores.
6. **Limitaciones y ruta a producción:** portugués sintético, datos sintéticos, capacidad, monitoreo, retención, lo que falta.

**Video (3–5 min):** 30 s del problema con datos → 2 min de demo en vivo de los 5 escenarios (mostrando la consola del agente y la traza) → 1 min de arquitectura y decisiones clave → 30 s de resultados → 30 s de limitaciones y próximos pasos. Grabar con guion; hacer un ensayo antes.

---

## 9. Ruta a producción (sección del README)

- **Seguridad:** identidad real (OAuth/OTP del banco), permisos por rol, secretos en un gestor de secretos, modelo autoalojado dentro de la red del banco.
- **Privacidad y retención:** trazas con datos personales enmascarados; retención limitada (p. ej., 90 días) y acceso auditado.
- **Monitoreo:** tasa de escalamiento, resultados inseguros detectados, latencia p95, costo diario, deriva del clasificador (distribución de intenciones y confianza).
- **Capacidad:** límites de tasa del proveedor, concurrencia del backend; qué cambia para escalar (colas, caché, réplicas).
- **Humano en el loop:** muestreo de conversaciones para revisión, retroalimentación hacia las etiquetas.
- **Pendiente honesto:** validar con conversaciones reales en portugués, integración con el core bancario, pruebas de carga y revisión legal y regulatoria de la política.

---

## 10. Checklist final antes de enviar

- [ ] El link desplegado funciona en una ventana de incógnito
- [ ] `git clone` + `make` desde cero funciona siguiendo solo el README
- [ ] No hay credenciales en el repo **ni en su historial** (revisar con `git log -p | grep -i secret` o una herramienta como gitleaks)
- [ ] El README declara qué datos son reales/sintéticos/team-generated (dataset: sintético; política, casos adversariales y portugués: team-generated)
- [ ] Los 5 escenarios obligatorios se ven en el video
- [ ] `eval_report.md` incluye tamaños de muestra, versiones, variabilidad y limitaciones
- [ ] Las slides tienen 4–6 páginas
- [ ] Correo enviado a hackathon.admin@factored.ai con repo, link, slides y video

---

## 11. Riesgos y plan B

| Riesgo | Probabilidad | Mitigación |
| :--- | :---: | :--- |
| El texto de los transcripts no se relaciona con las etiquetas | Media-alta | Detectarlo el lunes → plan B de D7 (modelo de riesgo de escalamiento) |
| La lectura remota desde S3 es lenta (sobre todo si es CSV) | Media | Filtrar por partición, muestras reproducibles guardadas en `data/`, o correr en Colab (paso 5.0.2) |
| Límites del nivel gratuito del LLM | Alta durante la evaluación | Evaluar en local con Ollama; cuentas separadas; prompts cortos; plan B con OpenAI |
| El `gpt-oss-20b` falla en tool calling o en JSON | Media | Máquina de estados + JSON validado + reintento; el LLM no elige herramientas libremente |
| El deploy se rompe al final | Media | Deploy desde el día 1 y en cada día |
| El alcance crece | Alta | Este documento es el alcance; lo que no está aquí va a "trabajo futuro" |
| Se filtran credenciales de AWS | Baja pero grave | `.env` + `.gitignore` desde el primer commit; revisión antes de hacer público el repo |

---

## 12. Preguntas abiertas para el equipo

1. Nombre del equipo (define el nombre del repo).
2. ¿Quién toma cada rol (A, B, C, D)?
3. ¿Qué máquinas tienen ≥ 16 GB de RAM para correr `gpt-oss-20b` en local?
4. ¿Tenemos un presupuesto máximo (p. ej., USD 10) por si hay que usar el plan B de OpenAI?
5. ¿Alguien del equipo habla portugués para revisar los casos traducidos? (Si no, reportarlo como limitación.)
6. ¿Cuál es el formato de los archivos en S3 (CSV o Parquet, particionado)? → Se resuelve con el inventario del paso 5.0.2.
7. ¿Alguien tiene internet lento? → Esa persona trabaja el notebook en Google Colab (paso 5.0.1).
