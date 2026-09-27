# Roadmap · Fase 0: datos, EDA y elección del reto

**Hackathon:** Factored AI & Data Hackathon 2026 · sistema de atención al cliente con IA para LATAM Bank
**Equipo:** 3–4 personas, medio tiempo
**Meta de esta fase:** lunes 28 de septiembre (cierre del día)
**Versión:** v3 · 27 de septiembre de 2026 (v3: se recorta a la fase 0; el roadmap de construcción se escribe después de elegir el reto)

---

## 0. Qué cubre este roadmap y qué no

Todavía no hemos escogido qué flujo vamos a construir, así que planear la semana completa no tiene sentido. Este roadmap llega solo hasta ese punto:

1. **Acceso a los datos:** que todos puedan leer los datos desde la nube con la misma conexión.
2. **EDA:** entender qué hay en los datos y qué tan bien soportan cada opción.
3. **Decisión:** escoger el flujo con una matriz y evidencia del EDA.

**Termina cuando:** la decisión está escrita en `docs/decisions.md`. Con eso escribimos el **roadmap 2** (arquitectura, pipeline, modelo, agente, evaluación y entrega), ya pensado para el flujo elegido.

---

## 1. Lo que hay que tener en mente al decidir

No es el plan de construcción, pero la elección tiene que permitir cumplir esto:

**Escenarios obligatorios en la demo**

- Resolución normal
- Solicitud ambigua o no soportada (aclaración o abstención)
- Escalamiento a humano con handoff estructurado
- Interacción en español
- Interacción en portugués

**Criterios del jurado:** rationale y documentación · AI engineering · data analytics · data engineering · ML. **Primer filtro: que funcione.**

Frases del kickoff que sirven de guía: *"Don't build a chatbot, build a customer-service system"* y *"AI should not be autonomous just because it can be"*.

---

## 2. Las cuatro opciones

| Opción | Qué haría el sistema | Conviene si… | Riesgo en 5 días |
| :--- | :--- | :--- | :--- |
| 1. Disputas de transacciones | Encuentra la transacción, aplica la política, confirma y crea el caso, o escala (fraude, monto alto) | Los reclamos por transacciones tienen volumen y mal desempeño (FCR, escalamiento, SLA) | Medio |
| 2. Soporte de tarjetas | Pérdida/robo, bloqueo (con confirmación), desbloqueo (escala), explicación de rechazos por `response_code` | Predominan los motivos de tarjetas y los `response_code` tienen significado | Bajo-medio |
| 3. Consultas de cuenta y pagos | Saldos, movimientos, "¿ya se acreditó mi pago?" | Dominan el volumen y se quiere el camino más seguro | Bajo, pero casi sin acciones: puede parecer "un chatbot" |
| 4. Crédito: información y elegibilidad | Explica productos y evalúa elegibilidad con política sintética + estimación de riesgo | Hay señal para un modelo de riesgo y el texto de los transcripts no sirve para clasificar | Alto (guardrails de crédito, etiqueta proxy, casos límite) |

**No combinar flujos:** más flujos no dan puntos. El flujo elegido solo reconoce los pedidos de los demás y se abstiene o los deriva.

---

## 3. Roles para esta fase

| Rol | Responsable | En esta fase |
| :--- | :--- | :--- |
| A. Datos | _(nombre)_ | Conexión, inventario, secciones 1–2 del notebook (esquema y calidad) |
| B. ML | _(nombre)_ | Secciones 3–4 (demanda y dolor operativo) y 7 (viabilidad de ML) |
| C. Backend | _(nombre)_ | Sección 5 (¿los datos soportan cada flujo?) |
| D. Frontend y narrativa | _(nombre)_ | Sección 6 (idioma y texto) + esqueleto del repo |

Con 3 personas, C y D se reparten la sección 5 y la 6.

---

## 4. Agenda del lunes 28 (~5 h)

| Bloque | Quién | Qué |
| :--- | :--- | :--- |
| 0:00–0:45 | A (y todos replican) | Pasos 5.1 y 5.2: `.env`, conexión e inventario. Todos deben poder correr la celda de conexión antes de seguir. |
| 0:45–3:30 | Repartido | Notebook de exploración (paso 5.3), según los roles de la sección 3. |
| 3:30–4:15 | Todos | Cada quien resume sus hallazgos en 3 bullets con números dentro del notebook (sección 8 del notebook). |
| 4:15–5:00 | Todos | Reunión de decisión: llenar la matriz (sección 6), decidir el flujo y escribirlo en `docs/decisions.md`. |

**Hecho cuando:**

- [ ] Todos leen de S3 con la misma conexión
- [ ] El notebook corre de principio a fin
- [ ] La matriz está llena con evidencia
- [ ] El flujo está decidido y escrito en `docs/decisions.md`

---

## 5. Paso a paso

### 5.1 Credenciales en `.env` (nunca en el código)

Las llaves están en el diccionario de datos, sección 1 ("Data Access Credentials"). Son de solo lectura, pero las reglas prohíben credenciales en el repo público.

1. En la raíz del repo, asegúrate de que `.gitignore` tenga:

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

**Si usan Google Colab:** no subas el `.env`. Guarda las variables en el panel de "Secrets" (ícono de llave) y cárgalas así:

```python
import os
from google.colab import userdata
for k in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "S3_BUCKET", "S3_PREFIX"]:
    os.environ[k] = userdata.get(k)
```

### 5.2 Leer desde la nube con DuckDB (sin descargar archivos)

**Cómo funciona:** DuckDB, con la extensión `httpfs`, consulta los archivos directamente en S3 con SQL. Los archivos no se guardan en tu disco; los bytes viajan a la memoria solo mientras corre la consulta. Con Parquet, DuckDB lee solo las columnas y particiones que pides, así que es rápido. Con CSV, tiene que leer el archivo completo en cada consulta.

**Implicación práctica:**

- Tablas chicas (`customers`, `products`, `branches`, `service_agents`, `complaints`): se consultan remoto sin problema.
- Tablas grandes (`transactions` 5 M, `digital_events` 10 M, `call_center_interactions` 800 k): si están en CSV, cada consulta completa vuelve a leer todo por la red. Solución: filtrar por partición (`process_date`) o por muestra, y guardar solo el resultado pequeño en `data/` como Parquet.
- Si el internet de alguien es lento, esa persona corre el notebook en Google Colab: el mismo código funciona y la descarga la hace la máquina de Google.
- `digital_events`, `campaign_sends` y `marketing_campaigns` quedan fuera de esta exploración salvo que el inventario muestre algo que cambie eso.

**`data_pipeline/connection.py`** (la usa el notebook y, después, el pipeline):

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

**Primer paso obligatorio: el inventario.** Todavía no sabemos si los archivos son CSV o Parquet ni cómo están particionados. Antes de escribir cualquier consulta:

```python
from data_pipeline.connection import get_connection, list_files, BASE

con = get_connection()
files = list_files(con)
files["table"] = files["file"].str.replace(BASE + "/", "").str.split("/").str[0]
files["ext"] = files["file"].str.extract(r"\.(\w+)$")
files.groupby(["table", "ext"]).size()
```

Con eso se define **una sola vez** cómo se lee cada tabla y se registran como vistas:

```python
# Ajustar patrones y lector según el inventario.
# union_by_name=true tolera la evolución de esquema;
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

**Si una tabla grande es lenta:** materializar una vez una muestra reproducible en local:

```python
con.execute("""
    COPY (SELECT * FROM transactions USING SAMPLE 5 PERCENT (reservoir, 42))
    TO 'data/sample_transactions.parquet' (FORMAT parquet)
""")
```

La semilla fija (42) hace que la muestra sea reproducible; documentar el tamaño y el método en el notebook.

### 5.3 Notebook de exploración (`analysis/01_exploracion.ipynb`)

Reglas del notebook: corre de principio a fin sin errores; cada sección termina con una celda Markdown de "hallazgos" con números; los gráficos llevan título y unidad; nada de credenciales impresas.

**Sección 0 · Setup.** Imports, `get_connection()`, `register_views()`, semilla fija.

**Sección 1 · Inventario y esquema.**

- Archivos, formato, particiones y tamaño por tabla.
- `SELECT COUNT(*)` por tabla vs. las filas que dice el diccionario.
- `DESCRIBE <tabla>` vs. las columnas del diccionario: columnas faltantes, extra o con otro tipo.
- Rango de fechas por tabla (¿realmente 17-06-2023 a 17-06-2026?).

**Sección 2 · Calidad de datos.**

```sql
-- Nulos, mínimos, máximos, cardinalidad de todas las columnas en una sola consulta
SUMMARIZE complaints;

-- Duplicados por llave primaria
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

Además: valores fuera de dominio (enumeraciones del diccionario, `credit_score` fuera de 300–850, montos negativos, fechas futuras). Resultado: una tabla "problema → tabla → % afectado → tratamiento propuesto" (le sirve al roadmap 2 para el pipeline).

**Sección 3 · Demanda (por qué contacta la gente).**

- Distribución de `contact_reason` (top 20) y `reason_category`, en conteo y %.
- Tendencia mensual por `reason_category`.
- Cortes por país, canal y segmento (join con `customers`).
- `complaints`: `case_type`, `category`, `subcategory`, `reception_channel`.

**Sección 4 · Dolor operativo por motivo (cómo le va hoy al banco).**

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

**Pregunta clave:** ¿qué motivo combina alto volumen con mal desempeño? Buen gráfico: dispersión con volumen en X, FCR en Y y tamaño por duración.

**Sección 5 · ¿Los datos soportan cada flujo?** Una subsección por opción. De aquí sale el criterio con veto de la matriz.

- **Disputas:** distribución de `transaction_status` y `transaction_type`; tasa de `is_fraud`; % con `merchant_name`; distribución de `amount_usd`. Ojo: `complaints` no tiene `transaction_id`. Prueben cuántas quejas se pueden emparejar con una transacción usando `affected_product_id` + `claimed_amount` + fecha cercana.
- **Tarjetas:** productos Credit/Debit Card por `product_status` (¿hay Blocked?); transacciones Declined por `response_code`: ¿los códigos son pocos y consistentes, o aleatorios?
- **Cuenta y pagos:** qué motivos son consultas informativas; si `current_balance`, `last_transaction_date` y los pagos permiten responder "¿ya se acreditó?".
- **Crédito:** nulos y distribución de `credit_score`, `estimated_monthly_income`, `credit_limit`, `interest_rate`, `days_past_due`. Prueba de realismo: ¿`credit_score` se relaciona con `days_past_due` (correlación, o tasa de mora por decil de score)? Si no hay relación, un modelo de riesgo sería ruido.

**Sección 6 · Idioma y texto.**

- Distribución de `detected_language`, `detected_accent`, `accent_confidence`, `transcription_model` y `audio_quality`. Confirmar (o no) que no hay portugués.
- Largo de `customer_text` (palabras) y % de nulos.
- **Lectura humana:** 10 transcripts al azar por cada uno de los 3 motivos principales. ¿El texto del cliente realmente habla del motivo etiquetado? Anotar ejemplos: es la mejor forma de detectar texto sintético genérico.

**Sección 7 · Viabilidad de un componente de ML (prueba rápida, ~30 min).**

¿El texto del cliente predice el motivo de contacto? Si sí, un clasificador de intención es viable; si no, habrá que buscar otro componente aprendido (con variables estructuradas).

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

| Resultado | Interpretación | Qué implica para la decisión |
| :--- | :--- | :--- |
| `customer_text` supera claramente al azar (≥ 0,15 de macro-F1 por encima y ≥ 0,5 absoluto) | El texto del cliente sí predice el motivo | Clasificador de intención viable para cualquier flujo |
| `customer_text` ≈ azar | El texto sintético no se relaciona con la etiqueta | El ML tendría que ser con variables estructuradas (p. ej., riesgo de escalamiento o de crédito); el flujo de crédito gana puntos |
| `full_text` ≫ `customer_text` | La parte del agente "delata" la etiqueta | Usar `full_text` sería fuga: solo `customer_text` |

Opcional: repetir con `complaints.description` → `category`.

**Sección 8 · Conclusiones.** Una tabla con los hallazgos de cada sección (con números) y los puntajes propuestos para la matriz. Esta sección es la que se lee en la reunión de decisión.

---

## 6. Matriz de decisión

Se llena en la reunión de cierre del lunes, con evidencia del notebook. Se guarda en `analysis/decision_matrix.md`.

**Escala:** 1 = débil, 2 = aceptable, 3 = fuerte. **Puntaje final** = Σ (peso × puntaje). Máximo posible: 45.

| # | Criterio | Peso | Cómo se puntúa | Evidencia | Disputas | Tarjetas | Cuenta y pagos | Crédito |
| :---: | :--- | :---: | :--- | :--- | :---: | :---: | :---: | :---: |
| 1 | Volumen de demanda | 2 | 3 = el motivo está en el top 3 de contactos o quejas; 2 = relevante (≥ 10 %); 1 = marginal | Secc. 3 | | | | |
| 2 | Dolor operativo | 2 | 3 = peor que el promedio en ≥ 2 indicadores (FCR, escalamiento, AHT, SLA); 2 = en 1; 1 = en ninguno | Secc. 4 | | | | |
| 3 | Soporte de los datos (**veto**) | 3 | 3 = todas las herramientas se construyen con columnas reales y coherentes; 2 = con supuestos menores; 1 = faltan datos clave | Secc. 5 | | | | |
| 4 | Cobertura de escenarios obligatorios | 3 | 3 = cubre de forma natural aclaración, acción con confirmación, verificación y escalamiento; 2 = cubre la mayoría; 1 = casi solo lectura | A priori | 3 | 3 | 1 | 2 |
| 5 | Viabilidad del componente de ML | 2 | 3 = hay un modelo claramente mejor que su baseline; 2 = marginal; 1 = no hay señal | Secc. 7 | | | | |
| 6 | Factibilidad en 5 días (3 = bajo riesgo) | 2 | 3 = el equipo lo termina con holgura; 2 = justo; 1 = requiere cosas extra | A priori, ajustable | 2 | 3 | 3 | 1 |
| 7 | Historia de negocio | 1 | 3 = el impacto se puede estimar con datos; 2 = con supuestos; 1 = difícil de cuantificar | Secc. 4 | | | | |
| | **Total** | | | | | | | |

Los puntajes a priori de los criterios 4 y 6 son una propuesta inicial; el equipo puede ajustarlos en la reunión, dejando escrita la razón.

**Reglas de decisión:**

1. **Veto:** una opción con 1 en el criterio 3 queda descartada, sin importar su total.
2. Gana el mayor puntaje total.
3. **Empate o diferencia ≤ 2 puntos:** gana la que tenga más puntaje en el criterio 4 (cobertura de escenarios obligatorios); si siguen empatadas, la de mayor factibilidad (criterio 6).
4. La decisión no se reabre, salvo que aparezca un bloqueo técnico real; en ese caso se pasa a la segunda opción de la matriz, sin empezar otra discusión.

**Preguntas que el EDA debe dejar respondidas (servirán para la slide del problema):**

1. ¿Qué porcentaje de contactos y quejas corresponde al flujo elegido?
2. ¿Cómo se comparan su FCR, duración, espera y tasa de escalamiento con el resto?
3. ¿Cuánto tardan en resolverse (`resolution_days`) y cuántas quejas incumplen el SLA?
4. ¿Cómo varía por país, canal y segmento?
5. ¿Qué problemas de calidad de datos encontramos y cómo los vamos a tratar?

---

## 7. Entregable de esta fase: `docs/decisions.md`

Con este formato, que es el punto de partida del roadmap 2:

- **Opción elegida** y su puntaje en la matriz.
- **Los 3 números del EDA** que más pesaron.
- **Qué se descartó y por qué** (una línea por opción).
- **Componente de ML** que el EDA dejó como viable (clasificador de texto o modelo con variables estructuradas).
- **Problemas de calidad** encontrados y tratamiento propuesto (de la sección 2 del notebook).
- **Idioma:** si hay o no portugués en los datos.

---

## 8. Preguntas abiertas para el equipo (antes o durante el lunes)

1. Nombre del equipo (define el nombre del repo).
2. ¿Quién toma cada rol (A, B, C, D)?
3. ¿Cuál es el formato de los archivos en S3 (CSV o Parquet, particionado)? → Se resuelve con el inventario del paso 5.2.
4. ¿Alguien tiene internet lento? → Esa persona trabaja el notebook en Google Colab (paso 5.1).
5. ¿Alguien del equipo habla portugués? (Importa para el roadmap 2.)

---

## Siguiente paso

Con `docs/decisions.md` listo, escribimos el **roadmap 2**: arquitectura, LLM, política, pipeline, componente de ML, agente, evaluación, deploy y entrega, todo para el flujo elegido.
