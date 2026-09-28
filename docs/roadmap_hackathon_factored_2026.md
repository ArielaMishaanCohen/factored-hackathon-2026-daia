# Roadmap · Fase 0: datos, EDA y elección del reto

**Hackathon:** Factored AI & Data Hackathon 2026 · sistema de atención al cliente con IA para LATAM Bank
**Equipo:** 3–4 personas, medio tiempo
**Meta de esta fase:** lunes 28 de septiembre (cierre del día)
**Versión:** v4 · 27 de septiembre de 2026 (v4: código completo de cada chunk del notebook; copia local a Parquet en lugar de leer todo de S3)

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

| Opción                                  | Qué haría el sistema                                                                                         | Conviene si…                                                                              | Riesgo en 5 días                                            |
| :--------------------------------------- | :------------------------------------------------------------------------------------------------------------- | :----------------------------------------------------------------------------------------- | :----------------------------------------------------------- |
| 1. Disputas de transacciones             | Encuentra la transacción, aplica la política, confirma y crea el caso, o escala (fraude, monto alto)         | Los reclamos por transacciones tienen volumen y mal desempeño (FCR, escalamiento, SLA)    | Medio                                                        |
| 2. Soporte de tarjetas                   | Pérdida/robo, bloqueo (con confirmación), desbloqueo (escala), explicación de rechazos por`response_code` | Predominan los motivos de tarjetas y los`response_code` tienen significado               | Bajo-medio                                                   |
| 3. Consultas de cuenta y pagos           | Saldos, movimientos, "¿ya se acreditó mi pago?"                                                              | Dominan el volumen y se quiere el camino más seguro                                       | Bajo, pero casi sin acciones: puede parecer "un chatbot"     |
| 4. Crédito: información y elegibilidad | Explica productos y evalúa elegibilidad con política sintética + estimación de riesgo                      | Hay señal para un modelo de riesgo y el texto de los transcripts no sirve para clasificar | Alto (guardrails de crédito, etiqueta proxy, casos límite) |

**No combinar flujos:** más flujos no dan puntos. El flujo elegido solo reconoce los pedidos de los demás y se abstiene o los deriva.

---

## 3. Roles para esta fase

| Rol                     | Responsable  | En esta fase                                                           |
| :---------------------- | :----------- | :--------------------------------------------------------------------- |
| A. Datos                | _(nombre)_ | Conexión, inventario, secciones 1–2 del notebook (esquema y calidad) |
| B. ML                   | _(nombre)_ | Secciones 3–4 (demanda y dolor operativo) y 7 (viabilidad de ML)      |
| C. Backend              | _(nombre)_ | Sección 5 (¿los datos soportan cada flujo?)                          |
| D. Frontend y narrativa | _(nombre)_ | Sección 6 (idioma y texto) + esqueleto del repo                       |

Con 3 personas, C y D se reparten la sección 5 y la 6.

---

## 4. Agenda del lunes 28 (~5 h)

| Bloque     | Quién               | Qué                                                                                                                                          |
| :--------- | :------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------- |
| 0:00–0:45 | A (y todos replican) | Pasos 5.1 y 5.2: entorno,`.env`, conexión y copia local (chunks 0.1–0.4). Todos deben poder correr la celda de conexión antes de seguir. |
| 0:45–3:30 | Repartido            | Notebook de exploración (paso 5.3), según los roles de la sección 3.                                                                       |
| 3:30–4:15 | Todos                | Cada quien resume sus hallazgos en 3 bullets con números dentro del notebook (sección 8 del notebook).                                      |
| 4:15–5:00 | Todos                | Reunión de decisión: llenar la matriz (sección 6), decidir el flujo y escribirlo en`docs/decisions.md`.                                  |

**Hecho cuando:**

- [ ] Todos leen de S3 con la misma conexión
- [ ] El notebook corre de principio a fin
- [ ] La matriz está llena con evidencia
- [ ] El flujo está decidido y escrito en `docs/decisions.md`

---

## 5. Paso a paso

Cada bloque de código de esta sección es **un chunk (celda) del notebook**, en orden. Los nombres de columnas ya están verificados contra los datos reales (esquema de los Parquet de `data/`). Si un chunk falla por una columna, comparen con el output del chunk 1.3.

### 5.1 Entorno y credenciales

#### Entorno de Python (una vez por persona)

En la raíz del repo, desde la terminal:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt ipykernel
python -m ipykernel install --user --name hackathon-daia --display-name "Python (.venv hackathon)"
```

En VS Code, al abrir el notebook: **Select Kernel → "Python (.venv hackathon)"** (o el `.venv` en *Python Environments*). Si sale `No module named 'duckdb'`, está usando otro kernel.

`.gitignore` debe incluir `.venv/`.

#### Credenciales en `.env` (nunca en el código)

Las llaves están en el diccionario de datos, sección 1 ("Data Access Credentials"). Son de solo lectura, pero las reglas prohíben credenciales en el repo público.

1. En la raíz del repo, asegúrate de que `.gitignore` tenga:

   ```gitignore
   .env
   .venv/
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

### 5.2 Conexión a S3 y copia local de los datos

**Lo que ya sabemos del inventario:** todo está en CSV. Hay 5 tablas en un solo archivo (`customers`, `products`, `branches`, `service_agents`, `daily_exchange_rates`, más `marketing_campaigns`, que no usamos) y el resto está particionado por día: `tabla/year=AAAA/month=MM/day=DD/tabla_AAAAMMDD.csv`, unos 1097 archivos por tabla (17-06-2023 a 17-06-2026).

**Por qué no leemos todo directo de S3:** con CSV, cada consulta a una tabla grande vuelve a leer sus ~1097 archivos por internet. Por eso:

1. Las tablas chicas se leen directo de S3 (son un solo archivo).
2. Las tablas grandes se **copian una sola vez** a Parquet en `data/` (tarda unos minutos la primera vez). Después, todas las consultas son locales e inmediatas.
3. `transactions` (5 M de filas) se copia solo con los últimos 12 meses.

Una persona del equipo puede hacer la copia y compartir los `.parquet` por Drive; los demás los ponen en `data/` y se saltan la descarga. `data/` está en `.gitignore`.

**`data_pipeline/connection.py`:**

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

### 5.3 Notebook de exploración (`analysis/01_exploracion.ipynb`)

Reglas del notebook: corre de principio a fin sin errores; cada sección termina con una celda Markdown de **hallazgos** con números; los gráficos llevan título y unidad; nada de credenciales impresas.

---

#### Sección 0 · Setup

**Chunk 0.1 · Imports y conexión**

```python
import sys
from pathlib import Path

# El notebook vive en analysis/; agregamos la raíz del repo para poder importar data_pipeline
ROOT = Path.cwd().parent if Path.cwd().name == "analysis" else Path.cwd()
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from data_pipeline.connection import get_connection, list_files, BASE

SEED = 42
FECHA_CORTE = "2026-06-17"  # fin del dataset = "hoy" simulado
pd.set_option("display.max_columns", 60)
pd.set_option("display.max_colwidth", 120)
sns.set_theme(style="whitegrid")

con = get_connection()

def q(sql):
    """Corre SQL y devuelve un DataFrame."""
    return con.sql(sql).df()

def columnas(tabla):
    return list(q(f"DESCRIBE SELECT * FROM {tabla}")["column_name"])
```

**Chunk 0.2 · Inventario de archivos en S3** (solo lista nombres, no descarga)

```python
files = list_files(con)
files["ruta"] = files["file"].str.replace(BASE + "/", "")
files["tabla"] = files["ruta"].str.split("/").str[0].str.replace(".csv", "")
files["particionada"] = files["ruta"].str.contains("/")
inventario = files.groupby(["tabla", "particionada"]).size().rename("archivos").reset_index()
inventario
```

**Chunk 0.3 · Vistas de las tablas chicas y de las remotas** (rápido: solo lee el primer archivo de cada tabla para saber las columnas)

```python
SMALL = ["customers", "products", "branches", "service_agents", "daily_exchange_rates"]
BIG = ["transactions", "call_center_interactions", "call_transcripts", "complaints", "satisfaction_surveys"]

for t in SMALL:
    con.execute(f"CREATE OR REPLACE VIEW {t} AS SELECT * FROM read_csv('{BASE}/{t}.csv', header=true)")

for t in BIG:
    con.execute(f"""
        CREATE OR REPLACE VIEW {t}_remote AS
        SELECT * FROM read_csv('{BASE}/{t}/**/*.csv', header=true, hive_partitioning=true, filename=true)
    """)

q("SELECT COUNT(*) AS n FROM customers")
```

**Chunk 0.4 · Copia local a Parquet** (tarda unos minutos solo la primera vez; si los archivos ya existen, no descarga nada)

```python
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

for t in ["complaints", "satisfaction_surveys", "call_center_interactions", "call_transcripts"]:
    out = DATA / f"{t}.parquet"
    if not out.exists():
        print("Descargando", t, "...")
        con.execute(f"COPY (SELECT * FROM {t}_remote) TO '{out}' (FORMAT parquet)")
    con.execute(f"CREATE OR REPLACE VIEW {t} AS SELECT * FROM read_parquet('{out}')")

# transactions: solo los últimos 12 meses (jul-2025 a jun-2026)
out = DATA / "transactions_12m.parquet"
if not out.exists():
    print("Descargando transactions (12 meses) ...")
    # Se listan solo las carpetas de esos meses para no tocar los demás archivos en S3
    rutas = [f"{BASE}/transactions/year=2025/month={m:02d}/*/*.csv" for m in range(7, 13)]
    rutas += [f"{BASE}/transactions/year=2026/*/*/*.csv"]
    con.execute(f"""
        COPY (SELECT * FROM read_csv({rutas}, header=true, hive_partitioning=true, filename=true))
        TO '{out}' (FORMAT parquet)
    """)
con.execute(f"CREATE OR REPLACE VIEW transactions AS SELECT * FROM read_parquet('{out}')")

# Las tablas chicas también se guardan localmente para no depender de internet
for t in SMALL:
    out = DATA / f"{t}.parquet"
    if not out.exists():
        con.execute(f"COPY (SELECT * FROM {t}) TO '{out}' (FORMAT parquet)")
    con.execute(f"CREATE OR REPLACE VIEW {t} AS SELECT * FROM read_parquet('{out}')")

TABLAS = SMALL + BIG
print("Listo:", TABLAS)
```

Si este chunk falla con un error de columnas que no coinciden entre archivos, el esquema cambió con el tiempo: en ese caso, agregar `union_by_name=true` solo a la vista `_remote` de esa tabla (chunk 0.3) y volver a correr.

**Para las sesiones siguientes:** con los Parquet ya en `data/`, basta correr 0.1, 0.3 y 0.4 (esta última ya no descarga).

---

#### Sección 1 · Inventario y esquema

**Chunk 1.1 · Filas por tabla vs. el diccionario**

```python
# Llenar con las filas que dice el diccionario (p. ej. "transactions": 5_000_000)
FILAS_DICCIONARIO = {
    "customers": None, "products": None, "branches": None, "service_agents": None,
    "daily_exchange_rates": None, "transactions": None, "call_center_interactions": None,
    "call_transcripts": None, "complaints": None, "satisfaction_surveys": None,
}

conteos = pd.DataFrame(
    [(t, q(f"SELECT COUNT(*) AS n FROM {t}")["n"][0]) for t in TABLAS],
    columns=["tabla", "filas"],
)
conteos["diccionario"] = conteos["tabla"].map(FILAS_DICCIONARIO)
conteos["nota"] = np.where(conteos["tabla"] == "transactions", "solo últimos 12 meses", "")
conteos
```

**Chunk 1.2 · Rango de fechas por partición** (tablas grandes)

```python
rangos = []
for t in BIG:
    r = q(f"""
        SELECT MIN(make_date(year::INT, month::INT, day::INT)) AS desde,
               MAX(make_date(year::INT, month::INT, day::INT)) AS hasta,
               COUNT(DISTINCT make_date(year::INT, month::INT, day::INT)) AS dias_con_datos
        FROM {t}
    """)
    rangos.append({"tabla": t, **r.iloc[0].to_dict()})
pd.DataFrame(rangos)
```

**Chunk 1.3 · Columnas y tipos de cada tabla** (compararlas con el diccionario; **pegar este output** si algún chunk posterior falla por nombres)

```python
for t in TABLAS:
    d = q(f"DESCRIBE {t}")
    print(f"\n## {t} ({len(d)} columnas)")
    print(", ".join(f"{c} ({ty})" for c, ty in zip(d["column_name"], d["column_type"])))
```

**Chunk 1.4 · ¿Cambió el esquema con el tiempo?** (compara el encabezado del primer, un intermedio y el último archivo de cada tabla grande; son 15 lecturas pequeñas a S3)

```python
evolucion = []
for t in BIG:
    arch = files.loc[files["file"].str.startswith(f"{BASE}/{t}/"), "file"].sort_values().tolist()
    muestra = [arch[0], arch[len(arch) // 2], arch[-1]]
    esquemas = {f.split("/")[-1]: columnas(f"read_csv('{f}', header=true)") for f in muestra}
    base = set(next(iter(esquemas.values())))
    for nombre, cols in esquemas.items():
        evolucion.append({
            "tabla": t, "archivo": nombre, "n_columnas": len(cols),
            "nuevas": sorted(set(cols) - base), "faltantes": sorted(base - set(cols)),
        })
pd.DataFrame(evolucion)
```

**Hallazgos (Markdown):** filas vs. diccionario, rango de fechas, columnas faltantes/extra/tipos raros, y si hay evolución de esquema.

---

#### Sección 2 · Calidad de datos

**Chunk 2.1 · Nulos por columna** (`SUMMARIZE` da nulos, mín., máx. y cardinalidad de todas las columnas)

```python
resumen = {t: q(f"SUMMARIZE {t}") for t in TABLAS}

nulos = pd.concat(
    [r.assign(tabla=t)[["tabla", "column_name", "column_type", "null_percentage", "approx_unique"]]
     for t, r in resumen.items()]
)
nulos["null_percentage"] = pd.to_numeric(nulos["null_percentage"].astype(str).str.rstrip("%"), errors="coerce")
nulos[nulos["null_percentage"] > 0].sort_values("null_percentage", ascending=False)
```

Para ver el detalle de una tabla: `resumen["complaints"]`.

**Chunk 2.2 · Duplicados por llave primaria y duplicados exactos**

```python
PK = {
    "customers": "customer_id",
    "products": "product_id",
    "branches": "branch_id",
    "service_agents": "agent_id",
    "transactions": "transaction_id",
    "call_center_interactions": "interaction_id",
    "call_transcripts": "transcript_id",
    "complaints": "complaint_id",
    "satisfaction_surveys": "survey_id",
}
TECNICAS = ["filename", "year", "month", "day"]  # columnas que agregamos al leer, no son datos

filas = []
for t, pk in PK.items():
    cols = [c for c in columnas(t) if c not in TECNICAS]
    try:
        r = q(f"""
            SELECT COUNT(*) AS filas,
                   COUNT(DISTINCT {pk}) AS ids_unicos,
                   COUNT(*) - COUNT(DISTINCT {pk}) AS dup_por_llave,
                   COUNT(*) - (SELECT COUNT(*) FROM (SELECT DISTINCT {", ".join(cols)} FROM {t})) AS dup_exactos
            FROM {t}
        """).iloc[0].to_dict()
        filas.append({"tabla": t, "pk": pk, **r})
    except Exception as e:
        filas.append({"tabla": t, "pk": pk, "error": str(e)[:80]})
dups = pd.DataFrame(filas)
dups["pct_dup_llave"] = (100 * dups["dup_por_llave"] / dups["filas"]).round(2)
dups
```

- `dup_exactos` > 0 → filas repetidas idénticas (se eliminan).
- `dup_por_llave` > `dup_exactos` → misma llave con valores distintos (versiones; hay que decidir cuál conservar, p. ej. la más reciente).

**Chunk 2.3 · Ejemplos de llaves duplicadas con valores distintos** (cambiar la tabla)

```python
t, pk = "complaints", PK["complaints"]
q(f"""
    SELECT * FROM {t}
    WHERE {pk} IN (SELECT {pk} FROM {t} GROUP BY 1 HAVING COUNT(*) > 1 LIMIT 3)
    ORDER BY {pk}
""")
```

**Chunk 2.4 · Huérfanos** (llaves foráneas sin padre)

```python
FK = [  # (tabla hija, columna, tabla padre, columna padre)
    ("products", "customer_id", "customers", "customer_id"),
    ("transactions", "customer_id", "customers", "customer_id"),
    ("transactions", "product_id", "products", "product_id"),
    ("call_center_interactions", "customer_id", "customers", "customer_id"),
    ("call_center_interactions", "agent_id", "service_agents", "agent_id"),
    ("call_transcripts", "interaction_id", "call_center_interactions", "interaction_id"),
    ("complaints", "customer_id", "customers", "customer_id"),
    ("complaints", "affected_product_id", "products", "product_id"),
    ("complaints", "origin_interaction_id", "call_center_interactions", "interaction_id"),
    ("satisfaction_surveys", "interaction_id", "call_center_interactions", "interaction_id"),
]

filas = []
for hija, col, padre, pcol in FK:
    try:
        r = q(f"""
            SELECT COUNT(*) AS con_llave,
                   SUM(CASE WHEN p.{pcol} IS NULL THEN 1 ELSE 0 END) AS huerfanos
            FROM {hija} h
            LEFT JOIN (SELECT DISTINCT {pcol} FROM {padre}) p ON h.{col} = p.{pcol}
            WHERE h.{col} IS NOT NULL
        """).iloc[0].to_dict()
        filas.append({"relacion": f"{hija}.{col} → {padre}", **r})
    except Exception as e:
        filas.append({"relacion": f"{hija}.{col} → {padre}", "error": str(e)[:80]})
huerf = pd.DataFrame(filas)
huerf["pct_huerfanos"] = (100 * huerf["huerfanos"] / huerf["con_llave"]).round(2)
huerf
```

Ojo: `transactions` solo tiene 12 meses, así que `satisfaction_surveys → interactions` o `complaints → products` son las relaciones más confiables aquí.

**Chunk 2.5 · Llegadas tardías** (días entre la fecha del evento y la partición en la que llegó)

```python
FECHA_EVENTO = {
    "transactions": "transaction_date",
    "call_center_interactions": "interaction_date",
    "complaints": "creation_date",
    "satisfaction_surveys": "survey_date",
}

atrasos = []
for t, col in FECHA_EVENTO.items():
    try:
        r = q(f"""
            SELECT DATE_DIFF('day', CAST({col} AS DATE), make_date(year::INT, month::INT, day::INT)) AS atraso_dias,
                   COUNT(*) AS n
            FROM {t}
            GROUP BY 1
        """)
        r["tabla"] = t
        atrasos.append(r)
    except Exception as e:
        print(t, "→", str(e)[:80])
atrasos = pd.concat(atrasos)
atrasos["pct"] = (100 * atrasos["n"] / atrasos.groupby("tabla")["n"].transform("sum")).round(2)
atrasos.pivot_table(index="atraso_dias", columns="tabla", values="pct").fillna(0).sort_index()
```

Atraso 0 = llegó el mismo día. Atrasos positivos = llegadas tardías (el pipeline tendrá que reprocesar días anteriores). Negativos = algo raro.

**Chunk 2.6 · Valores fuera de dominio: categorías**

Muestra los valores de todas las columnas de texto con pocas categorías, para compararlas con las enumeraciones del diccionario (buscar mayúsculas inconsistentes, espacios, valores inventados).

```python
for t, r in resumen.items():
    cat = r[(r["column_type"] == "VARCHAR") & (r["approx_unique"] <= 30)]["column_name"]
    for c in cat:
        if c in TECNICAS:
            continue
        vc = q(f"SELECT {c} AS valor, COUNT(*) AS n FROM {t} GROUP BY 1 ORDER BY 2 DESC")
        print(f"\n{t}.{c}: " + " | ".join(f"{v} ({n})" for v, n in zip(vc["valor"], vc["n"])))
```

**Chunk 2.7 · Valores fuera de dominio: números y fechas**

```python
checks = {
    "credit_score fuera de 300–850":
        "SELECT COUNT(*) FROM customers WHERE credit_score NOT BETWEEN 300 AND 850",
    "montos negativos en transactions":
        "SELECT COUNT(*) FROM transactions WHERE amount_usd < 0",
    "transacciones con fecha futura":
        f"SELECT COUNT(*) FROM transactions WHERE CAST(transaction_date AS DATE) > DATE '{FECHA_CORTE}'",
    "interacciones con duración <= 0":
        "SELECT COUNT(*) FROM call_center_interactions WHERE duration_seconds <= 0",
    "interacciones con espera negativa":
        "SELECT COUNT(*) FROM call_center_interactions WHERE wait_time_seconds < 0",
    "quejas con resolution_days negativo":
        "SELECT COUNT(*) FROM complaints WHERE resolution_days < 0",
    "quejas con claimed_amount negativo":
        "SELECT COUNT(*) FROM complaints WHERE claimed_amount < 0",
    "ingreso mensual negativo o cero":
        "SELECT COUNT(*) FROM customers WHERE estimated_monthly_income <= 0",
}
filas = []
for nombre, sql in checks.items():
    try:
        filas.append({"chequeo": nombre, "filas": q(sql).iloc[0, 0]})
    except Exception as e:
        filas.append({"chequeo": nombre, "filas": None, "error": str(e)[:80]})
pd.DataFrame(filas)
```

**Chunk 2.8 · Tabla de problemas de calidad** (se llena a mano con lo encontrado; alimenta el pipeline del roadmap 2)

```python
problemas = pd.DataFrame([
    # {"problema": "Duplicados exactos", "tabla": "complaints", "pct_afectado": 0.0, "tratamiento": "Eliminar"},
], columns=["problema", "tabla", "pct_afectado", "tratamiento"])
problemas
```

**Hallazgos (Markdown).**

---

#### Sección 3 · Demanda (por qué contacta la gente)

**Chunk 3.1 · Motivos de contacto**

```python
motivos = q("""
    SELECT reason_category, contact_reason, COUNT(*) AS n,
           ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
    FROM call_center_interactions
    GROUP BY 1, 2
    ORDER BY n DESC
""")
categorias = motivos.groupby("reason_category", as_index=False)[["n", "pct"]].sum().sort_values("n", ascending=False)
display(categorias)
motivos.head(20)
```

**Chunk 3.2 · Gráfico de categorías**

```python
fig, ax = plt.subplots(figsize=(9, 5))
sns.barplot(data=categorias, y="reason_category", x="pct", ax=ax, color="steelblue")
ax.set(title="Contactos al call center por categoría de motivo", xlabel="% de contactos", ylabel="")
plt.tight_layout()
```

**Chunk 3.3 · Tendencia mensual por categoría**

```python
mensual = q("""
    SELECT DATE_TRUNC('month', CAST(interaction_date AS DATE)) AS mes, reason_category, COUNT(*) AS n
    FROM call_center_interactions
    GROUP BY 1, 2
    ORDER BY 1
""")
fig, ax = plt.subplots(figsize=(11, 5))
sns.lineplot(data=mensual, x="mes", y="n", hue="reason_category", ax=ax)
ax.set(title="Contactos por mes y categoría", xlabel="Mes", ylabel="Contactos")
ax.legend(bbox_to_anchor=(1.01, 1), loc="upper left")
plt.tight_layout()
```

**Chunk 3.4 · Cortes por país, segmento y canal** (% de cada categoría dentro de cada grupo)

```python
def corte(columna, origen="c"):
    df = q(f"""
        SELECT {origen}.{columna} AS grupo, i.reason_category, COUNT(*) AS n
        FROM call_center_interactions i
        LEFT JOIN customers c USING (customer_id)
        GROUP BY 1, 2
    """)
    tabla = df.pivot_table(index="grupo", columns="reason_category", values="n", fill_value=0)
    return (100 * tabla.div(tabla.sum(axis=1), axis=0)).round(1)

for col, origen in [("country", "c"), ("segment", "c"), ("channel", "i")]:
    print(f"\n### Por {col} (% por fila)")
    try:
        display(corte(col, origen))
    except Exception as e:
        print("  ", str(e)[:100])
```

**Chunk 3.5 · Quejas: tipo, categoría y canal de recepción**

```python
for col in ["case_type", "category", "reception_channel"]:
    display(q(f"""
        SELECT {col}, COUNT(*) AS n, ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
        FROM complaints GROUP BY 1 ORDER BY n DESC
    """))

q("""
    SELECT category, subcategory, COUNT(*) AS n,
           ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
    FROM complaints GROUP BY 1, 2 ORDER BY n DESC LIMIT 25
""")
```

**Hallazgos (Markdown):** los 3 motivos principales con su %, si hay estacionalidad, diferencias fuertes por país/segmento/canal, y las categorías de quejas más comunes.

---

#### Sección 4 · Dolor operativo por motivo (cómo le va hoy al banco)

**Chunk 4.1 · Indicadores por motivo, comparados con el promedio**

```python
dolor = q("""
    SELECT reason_category, contact_reason,
           COUNT(*)                                             AS n,
           ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)   AS pct,
           ROUND(100.0 * AVG(was_resolved::INT), 1)             AS fcr_pct,
           ROUND(100.0 * AVG(was_escalated::INT), 1)            AS escalamiento_pct,
           ROUND(100.0 * AVG(requires_followup::INT), 1)        AS seguimiento_pct,
           ROUND(MEDIAN(duration_seconds) / 60, 1)              AS aht_mediana_min,
           ROUND(MEDIAN(wait_time_seconds) / 60, 1)             AS espera_mediana_min,
           ROUND(100.0 * AVG((detected_sentiment IN ('Negativo', 'Muy Negativo'))::INT), 1) AS negativo_pct
    FROM call_center_interactions
    GROUP BY 1, 2
    ORDER BY n DESC
""")

total = q("""
    SELECT ROUND(100.0 * AVG(was_resolved::INT), 1)      AS fcr_pct,
           ROUND(100.0 * AVG(was_escalated::INT), 1)     AS escalamiento_pct,
           ROUND(100.0 * AVG(requires_followup::INT), 1) AS seguimiento_pct,
           ROUND(MEDIAN(duration_seconds) / 60, 1)       AS aht_mediana_min
    FROM call_center_interactions
""").iloc[0]
print("Promedio general:", total.to_dict())

# Cuántos indicadores están peor que el promedio (sirve para el criterio 2 de la matriz)
dolor["peor_en"] = (
    (dolor["fcr_pct"] < total["fcr_pct"]).astype(int)
    + (dolor["escalamiento_pct"] > total["escalamiento_pct"]).astype(int)
    + (dolor["seguimiento_pct"] > total["seguimiento_pct"]).astype(int)
    + (dolor["aht_mediana_min"] > total["aht_mediana_min"]).astype(int)
)
dolor
```

Si los valores de `detected_sentiment` son otros (ver chunk 2.6), ajustar la lista `('Negativo', 'Muy Negativo')`.

**Chunk 4.2 · Lo mismo agregado por categoría**

```python
q("""
    SELECT reason_category,
           COUNT(*) AS n,
           ROUND(100.0 * AVG(was_resolved::INT), 1)      AS fcr_pct,
           ROUND(100.0 * AVG(was_escalated::INT), 1)     AS escalamiento_pct,
           ROUND(100.0 * AVG(requires_followup::INT), 1) AS seguimiento_pct,
           ROUND(MEDIAN(duration_seconds) / 60, 1)       AS aht_mediana_min
    FROM call_center_interactions
    GROUP BY 1 ORDER BY n DESC
""")
```

**Chunk 4.3 · Gráfico volumen vs. resolución** (arriba a la izquierda = poco volumen y bien resuelto; **abajo a la derecha = mucho volumen y mal resuelto**, lo que buscamos)

```python
fig, ax = plt.subplots(figsize=(10, 7))
sns.scatterplot(data=dolor, x="n", y="fcr_pct", size="aht_mediana_min", hue="reason_category",
                sizes=(40, 400), alpha=0.7, ax=ax)
for _, r in dolor.nlargest(12, "n").iterrows():
    ax.annotate(r["contact_reason"], (r["n"], r["fcr_pct"]), fontsize=8, xytext=(4, 4), textcoords="offset points")
ax.axhline(total["fcr_pct"], ls="--", c="gray")
ax.set(title="Motivos de contacto: volumen vs. resolución en el primer contacto (tamaño = AHT)",
       xlabel="Contactos", ylabel="FCR (%)")
ax.legend(bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=8)
plt.tight_layout()
```

**Chunk 4.4 · Quejas por categoría: SLA, tiempo de resolución, compensación y satisfacción**

```python
q("""
    SELECT category,
           COUNT(*) AS n,
           ROUND(100.0 * AVG(sla_breached::INT), 1)                 AS sla_incumplido_pct,
           MEDIAN(resolution_days)                                  AS resolucion_mediana_dias,
           ROUND(100.0 * AVG((compensation_granted > 0)::INT), 1)   AS con_compensacion_pct,
           ROUND(AVG(resolution_satisfaction), 2)                   AS satisfaccion_media,
           ROUND(100.0 * AVG(is_repeat_complainer::INT), 1)         AS reincidente_pct
    FROM complaints
    GROUP BY 1 ORDER BY n DESC
""")
```

**Chunk 4.5 · CSAT por categoría de motivo** (encuestas unidas a interacciones)

```python
q("""
    SELECT i.reason_category,
           COUNT(*) AS encuestas,
           ROUND(AVG(s.main_score), 2) AS csat_medio
    FROM satisfaction_surveys s
    JOIN call_center_interactions i USING (interaction_id)
    GROUP BY 1 ORDER BY csat_medio
""")
```

**Hallazgos (Markdown):** ¿qué motivo combina alto volumen con mal desempeño? Anotar sus números contra el promedio.

---

#### Sección 5 · ¿Los datos soportan cada flujo?

Aquí se puntúa el criterio 3 (veto) de la matriz. Una subsección por opción.

##### 5a · Disputas de transacciones

**Chunk 5a.1 · Estado, tipo, fraude y comercio**

```python
display(q("""
    SELECT transaction_type, transaction_status, COUNT(*) AS n,
           ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
    FROM transactions GROUP BY 1, 2 ORDER BY n DESC
"""))

q("""
    SELECT COUNT(*) AS transacciones,
           ROUND(100.0 * AVG(is_fraud::INT), 2)                   AS fraude_pct,
           ROUND(100.0 * AVG((merchant_name IS NOT NULL)::INT), 1) AS con_comercio_pct,
           COUNT(DISTINCT merchant_name)                          AS comercios_distintos
    FROM transactions
""")
```

**Chunk 5a.2 · Distribución de montos**

```python
display(q("""
    SELECT transaction_type,
           ROUND(QUANTILE_CONT(amount_usd, 0.25), 2) AS p25,
           ROUND(MEDIAN(amount_usd), 2)              AS mediana,
           ROUND(QUANTILE_CONT(amount_usd, 0.9), 2)  AS p90,
           ROUND(QUANTILE_CONT(amount_usd, 0.99), 2) AS p99,
           ROUND(MAX(amount_usd), 2)                 AS maximo
    FROM transactions GROUP BY 1
"""))

montos = q("SELECT amount_usd FROM transactions USING SAMPLE 200000 ROWS (reservoir, 42)")
fig, ax = plt.subplots(figsize=(9, 4))
sns.histplot(montos["amount_usd"].clip(lower=0.01), log_scale=True, bins=60, ax=ax)
ax.set(title="Monto por transacción (muestra de 200k, escala log)", xlabel="USD", ylabel="Transacciones")
plt.tight_layout()
```

**Chunk 5a.3 · ¿Se pueden emparejar quejas con transacciones?** (`complaints` no tiene `transaction_id`: probamos con cliente + producto + monto + fecha cercana)

```python
emparejo = q("""
    WITH quejas AS (
        SELECT complaint_id, customer_id, affected_product_id, claimed_amount, currency,
               CAST(creation_date AS DATE) AS fecha_queja
        FROM complaints
        WHERE CAST(creation_date AS DATE) >= DATE '2025-08-01'           -- ventana cubierta por transactions_12m
          AND claimed_amount IS NOT NULL
    ),
    candidatos AS (
        SELECT q.complaint_id, COUNT(t.transaction_id) AS n_candidatas
        FROM quejas q
        LEFT JOIN transactions t
          ON t.customer_id = q.customer_id
         AND t.product_id = q.affected_product_id
         AND t.currency = q.currency
         AND ABS(t.amount - q.claimed_amount) <= 0.01 * q.claimed_amount + 0.5
         AND CAST(t.transaction_date AS DATE) BETWEEN q.fecha_queja - INTERVAL 60 DAY AND q.fecha_queja
        GROUP BY 1
    )
    SELECT CASE WHEN n_candidatas = 0 THEN '0 (no empareja)'
                WHEN n_candidatas = 1 THEN '1 (emparejo único)'
                ELSE '2+ (ambiguo)' END AS resultado,
           COUNT(*) AS quejas,
           ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
    FROM candidatos GROUP BY 1 ORDER BY 1
""")
emparejo
```

Si casi ninguna empareja, la política y los casos de prueba se construirían desde `transactions`, no desde `complaints`. Probar también sin la condición de monto si da muy bajo. `claimed_amount` viene en la moneda de la queja (`currency`), por eso se compara con `amount` (moneda local) y no con `amount_usd`.

##### 5b · Soporte de tarjetas

**Chunk 5b.1 · Productos de tarjeta por estado**

```python
q("""
    SELECT product_type, product_status, COUNT(*) AS n,
           ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY product_type), 1) AS pct_del_tipo
    FROM products
    WHERE product_type ILIKE 'Tarjeta%'
    GROUP BY 1, 2 ORDER BY 1, n DESC
""")
```

**Chunk 5b.2 · Transacciones rechazadas por `response_code`: ¿tienen sentido?**

```python
display(q("""
    SELECT response_code, COUNT(*) AS n,
           ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
    FROM transactions
    WHERE transaction_status = 'Declined'
    GROUP BY 1 ORDER BY n DESC
"""))

# Prueba de coherencia: si los códigos fueran aleatorios, se verían igual en aprobadas y rechazadas
q("""
    SELECT transaction_status, response_code, COUNT(*) AS n
    FROM transactions
    GROUP BY 1, 2
    ORDER BY 1, n DESC
""").pivot_table(index="response_code", columns="transaction_status", values="n", fill_value=0)
```

**Chunk 5b.3 · ¿Los rechazos se relacionan con el estado del producto?** (una tarjeta bloqueada debería tener más rechazos)

```python
q("""
    SELECT p.product_status,
           COUNT(*) AS transacciones,
           ROUND(100.0 * AVG((t.transaction_status = 'Declined')::INT), 1) AS rechazo_pct
    FROM transactions t
    JOIN products p USING (product_id)
    WHERE p.product_type ILIKE 'Tarjeta%'
    GROUP BY 1 ORDER BY rechazo_pct DESC
""")
```

##### 5c · Consultas de cuenta y pagos

**Chunk 5c.1 · Lista de todos los motivos** (marcar a mano cuáles son consultas informativas)

```python
q("SELECT reason_category, contact_reason, COUNT(*) AS n FROM call_center_interactions GROUP BY 1, 2 ORDER BY 1, n DESC")
```

**Chunk 5c.2 · ¿Tenemos lo necesario para responder saldo y "¿ya se acreditó?"?**

```python
display(q("""
    SELECT product_type,
           COUNT(*) AS productos,
           ROUND(100.0 * AVG((current_balance IS NULL)::INT), 1)        AS balance_nulo_pct,
           ROUND(100.0 * AVG((last_transaction_date IS NULL)::INT), 1)  AS ult_transaccion_nula_pct
    FROM products GROUP BY 1
"""))

# Coherencia: ¿last_transaction_date coincide con la última transacción real del producto?
q("""
    WITH ult AS (
        SELECT product_id, MAX(CAST(transaction_date AS DATE)) AS ult_real
        FROM transactions GROUP BY 1
    )
    SELECT COUNT(*) AS productos_con_transacciones,
           ROUND(100.0 * AVG((CAST(p.last_transaction_date AS DATE) = u.ult_real)::INT), 1) AS coincide_pct,
           MEDIAN(ABS(DATE_DIFF('day', CAST(p.last_transaction_date AS DATE), u.ult_real))) AS dif_mediana_dias
    FROM products p JOIN ult u USING (product_id)
""")
```

**Chunk 5c.3 · Pagos y sus estados** (¿hay "Pending" que luego se asientan?)

```python
q("""
    SELECT transaction_type, transaction_status, COUNT(*) AS n
    FROM transactions
    WHERE transaction_type ILIKE '%payment%' OR transaction_type ILIKE '%transfer%' OR transaction_type ILIKE '%deposit%'
    GROUP BY 1, 2 ORDER BY 1, n DESC
""")
```

##### 5d · Crédito

**Chunk 5d.1 · Nulos y distribución de las variables de crédito**

```python
display(q("""
    SELECT COUNT(*) AS clientes,
           ROUND(100.0 * AVG((credit_score IS NULL)::INT), 1)              AS score_nulo_pct,
           ROUND(100.0 * AVG((estimated_monthly_income IS NULL)::INT), 1)  AS ingreso_nulo_pct,
           MIN(credit_score) AS score_min, MEDIAN(credit_score) AS score_mediana, MAX(credit_score) AS score_max,
           MEDIAN(estimated_monthly_income) AS ingreso_mediana
    FROM customers
"""))

q("""
    SELECT product_type, COUNT(*) AS n,
           ROUND(100.0 * AVG((credit_limit IS NULL)::INT), 1)  AS limite_nulo_pct,
           ROUND(100.0 * AVG((interest_rate IS NULL)::INT), 1) AS tasa_nula_pct,
           ROUND(100.0 * AVG((days_past_due > 0)::INT), 1)     AS con_mora_pct,
           ROUND(100.0 * AVG((days_past_due > 30)::INT), 1)    AS mora_30_pct
    FROM products
    WHERE credit_limit IS NOT NULL OR days_past_due IS NOT NULL
    GROUP BY 1
""")
```

**Chunk 5d.2 · Prueba de realismo: ¿el score predice la mora?**

```python
credito = q("""
    SELECT c.customer_id, c.credit_score, c.estimated_monthly_income,
           MAX(p.days_past_due) AS max_dpd
    FROM customers c
    JOIN products p USING (customer_id)
    WHERE c.credit_score IS NOT NULL AND p.days_past_due IS NOT NULL
    GROUP BY 1, 2, 3
""")
credito["mora_30"] = (credito["max_dpd"] > 30).astype(int)
credito["decil_score"] = pd.qcut(credito["credit_score"], 10, labels=False, duplicates="drop") + 1

print("Correlación de Spearman score vs. días de mora:",
      round(credito[["credit_score", "max_dpd"]].corr(method="spearman").iloc[0, 1], 3))

por_decil = credito.groupby("decil_score").agg(clientes=("customer_id", "count"),
                                                score_medio=("credit_score", "mean"),
                                                mora_30_pct=("mora_30", "mean"))
por_decil["mora_30_pct"] = (100 * por_decil["mora_30_pct"]).round(1)

fig, ax = plt.subplots(figsize=(8, 4))
sns.barplot(data=por_decil.reset_index(), x="decil_score", y="mora_30_pct", color="indianred", ax=ax)
ax.set(title="Mora > 30 días por decil de credit score (1 = score más bajo)", xlabel="Decil de score", ylabel="% con mora > 30 días")
plt.tight_layout()
por_decil
```

Si la mora baja claramente de los deciles bajos a los altos, hay señal para un modelo de riesgo. Si la barra es plana, un modelo de riesgo sería ruido.

**Hallazgos (Markdown):** para cada opción, qué herramientas se podrían construir con columnas reales y cuáles requieren supuestos → puntaje del criterio 3.

---

#### Sección 6 · Idioma y texto

**Chunk 6.1 · Idioma, acento y calidad de la transcripción**

```python
for col in ["detected_language", "detected_accent", "transcription_model", "audio_quality"]:
    try:
        display(q(f"""
            SELECT {col}, COUNT(*) AS n, ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
            FROM call_transcripts GROUP BY 1 ORDER BY n DESC
        """))
    except Exception as e:
        print(col, "→", str(e)[:80])

q("SELECT ROUND(AVG(accent_confidence), 3) AS confianza_media, ROUND(MEDIAN(accent_confidence), 3) AS confianza_mediana FROM call_transcripts")
```

**Chunk 6.2 · Largo del texto del cliente**

```python
q("""
    SELECT COUNT(*) AS transcripts,
           ROUND(100.0 * AVG((customer_text IS NULL OR TRIM(customer_text) = '')::INT), 1) AS vacio_pct,
           MEDIAN(LEN(STRING_SPLIT(customer_text, ' ')))                   AS palabras_mediana,
           QUANTILE_CONT(LEN(STRING_SPLIT(customer_text, ' ')), 0.9)       AS palabras_p90,
           COUNT(DISTINCT customer_text)                                    AS textos_distintos
    FROM call_transcripts
""")
```

Si `textos_distintos` es mucho menor que `transcripts`, el texto es de plantilla (típico de datos sintéticos).

**Chunk 6.3 · Lectura humana: 10 textos al azar de cada uno de los 3 motivos principales**

```python
top3 = motivos.head(3)["contact_reason"].tolist()
for motivo in top3:
    print(f"\n{'=' * 100}\nMOTIVO: {motivo}\n{'=' * 100}")
    muestra = q(f"""
        SELECT t.customer_text
        FROM call_transcripts t JOIN call_center_interactions i USING (interaction_id)
        WHERE i.contact_reason = '{motivo.replace("'", "''")}' AND t.customer_text IS NOT NULL
        USING SAMPLE 10 ROWS (reservoir, 42)
    """)
    for i, txt in enumerate(muestra["customer_text"], 1):
        print(f"\n[{i}] {txt[:600]}")
```

Anotar en Markdown: ¿el texto del cliente habla del motivo etiquetado? Copiar 2–3 ejemplos buenos y 2–3 que no cuadren.

**Hallazgos (Markdown):** ¿hay portugués? (si no, es una limitación que se reporta), largo típico del texto, y si el texto se ve realista.

---

#### Sección 7 · Viabilidad de un componente de ML (~30 min)

¿El texto del cliente predice el motivo de contacto? Si sí, un clasificador de intención es viable; si no, el componente de ML tendría que usar variables estructuradas.

**Chunk 7.1 · Datos para la prueba**

```python
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline

df = q("""
    SELECT i.customer_id, t.customer_text, t.full_text, i.contact_reason, i.reason_category
    FROM call_transcripts t
    JOIN call_center_interactions i USING (interaction_id)
    WHERE t.customer_text IS NOT NULL
    USING SAMPLE 30000 ROWS (reservoir, 42)
""").drop_duplicates()

split = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=SEED)
tr, te = next(split.split(df, groups=df["customer_id"]))  # un cliente no aparece en train y test a la vez
print(len(df), "filas ·", len(tr), "train ·", len(te), "test")
```

**Chunk 7.2 · Baseline vs. TF-IDF, con dos etiquetas y dos textos**

```python
def modelo_tfidf():
    return make_pipeline(
        TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=3, sublinear_tf=True),
        LogisticRegression(max_iter=2000, class_weight="balanced"),
    )

resultados = []
for etiqueta in ["reason_category", "contact_reason"]:
    y = df[etiqueta]
    dummy = DummyClassifier(strategy="stratified", random_state=SEED).fit(df.iloc[tr], y.iloc[tr])
    fila = {"etiqueta": etiqueta, "clases": y.nunique(),
            "azar": f1_score(y.iloc[te], dummy.predict(df.iloc[te]), average="macro")}
    for texto in ["customer_text", "full_text"]:  # full_text solo para detectar fuga
        m = modelo_tfidf().fit(df[texto].iloc[tr], y.iloc[tr])
        fila[f"tfidf_{texto}"] = f1_score(y.iloc[te], m.predict(df[texto].iloc[te]), average="macro")
    resultados.append(fila)
pd.DataFrame(resultados).round(3)
```

**Chunk 7.3 · Detalle por clase** (con `reason_category` y `customer_text`)

```python
y = df["reason_category"]
m = modelo_tfidf().fit(df["customer_text"].iloc[tr], y.iloc[tr])
print(classification_report(y.iloc[te], m.predict(df["customer_text"].iloc[te]), digits=3))
```

Cómo leer el resultado:

| Resultado                                                                                            | Interpretación                                     | Qué implica para la decisión                                                                                                      |
| :--------------------------------------------------------------------------------------------------- | :-------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------- |
| `tfidf_customer_text` supera claramente al azar (≥ 0,15 de macro-F1 por encima y ≥ 0,5 absoluto) | El texto del cliente sí predice el motivo          | Clasificador de intención viable para cualquier flujo                                                                              |
| `tfidf_customer_text` ≈ azar                                                                      | El texto sintético no se relaciona con la etiqueta | El ML tendría que ser con variables estructuradas (p. ej., riesgo de escalamiento o de crédito); el flujo de crédito gana puntos |
| `tfidf_full_text` ≫ `tfidf_customer_text`                                                       | La parte del agente "delata" la etiqueta            | Usar`full_text` sería fuga: solo `customer_text`                                                                               |

**Chunk 7.4 (opcional) · Quejas: `description` → `category`**

```python
dq = q("""
    SELECT customer_id, description, category FROM complaints
    WHERE description IS NOT NULL
    USING SAMPLE 30000 ROWS (reservoir, 42)
""")
tr2, te2 = next(GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=SEED).split(dq, groups=dq["customer_id"]))
dummy = DummyClassifier(strategy="stratified", random_state=SEED).fit(dq.iloc[tr2], dq["category"].iloc[tr2])
m = modelo_tfidf().fit(dq["description"].iloc[tr2], dq["category"].iloc[tr2])
print("Azar:  ", round(f1_score(dq["category"].iloc[te2], dummy.predict(dq.iloc[te2]), average="macro"), 3))
print("TF-IDF:", round(f1_score(dq["category"].iloc[te2], m.predict(dq["description"].iloc[te2]), average="macro"), 3))
```

**Chunk 7.5 (si el texto no sirve) · Prueba rápida con variables estructuradas: ¿se puede predecir el escalamiento?**

```python
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

de = q("""
    SELECT i.customer_id, i.was_escalated::INT AS y,
           i.reason_category, i.detected_sentiment, c.segment, c.country,
           i.wait_time_seconds, c.credit_score
    FROM call_center_interactions i LEFT JOIN customers c USING (customer_id)
    USING SAMPLE 100000 ROWS (reservoir, 42)
""")
X = pd.get_dummies(de.drop(columns=["customer_id", "y"]), dtype=float)
tr3, te3 = next(GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=SEED).split(X, groups=de["customer_id"]))
gb = HistGradientBoostingClassifier(random_state=SEED).fit(X.iloc[tr3], de["y"].iloc[tr3])
print("Tasa de escalamiento:", round(de["y"].mean(), 3))
print("AUC (0,5 = azar):", round(roc_auc_score(de["y"].iloc[te3], gb.predict_proba(X.iloc[te3])[:, 1]), 3))
```

`wait_time_seconds` se conoce antes de atender; no usar `duration_seconds` ni `was_resolved` (se conocen después y serían fuga).

**Hallazgos (Markdown):** macro-F1 del azar vs. TF-IDF, si hay fuga con `full_text`, y (si se corrió) el AUC del modelo estructurado → puntaje del criterio 5.

---

#### Sección 8 · Conclusiones

**Chunk 8.1 · Tabla de hallazgos** (se llena a mano; es lo que se lee en la reunión de decisión)

```python
hallazgos = pd.DataFrame([
    {"seccion": "1 · Esquema",         "hallazgo": "", "numero": ""},
    {"seccion": "2 · Calidad",         "hallazgo": "", "numero": ""},
    {"seccion": "3 · Demanda",         "hallazgo": "", "numero": ""},
    {"seccion": "4 · Dolor operativo", "hallazgo": "", "numero": ""},
    {"seccion": "5 · Soporte de datos","hallazgo": "", "numero": ""},
    {"seccion": "6 · Idioma",          "hallazgo": "", "numero": ""},
    {"seccion": "7 · ML",              "hallazgo": "", "numero": ""},
])
hallazgos
```

**Chunk 8.2 · Matriz de decisión** (puntajes 1–3; los de los criterios 4 y 6 vienen a priori y se pueden ajustar)

```python
PESOS = {"volumen": 2, "dolor": 2, "soporte_datos": 3, "cobertura": 3, "ml": 2, "factibilidad": 2, "negocio": 1}

puntajes = pd.DataFrame({
    #                Disputas  Tarjetas  Cuenta  Crédito
    "volumen":       [None,    None,     None,   None],
    "dolor":         [None,    None,     None,   None],
    "soporte_datos": [None,    None,     None,   None],
    "cobertura":     [3,       3,        1,      2],
    "ml":            [None,    None,     None,   None],
    "factibilidad":  [2,       3,        3,      1],
    "negocio":       [None,    None,     None,   None],
}, index=["Disputas", "Tarjetas", "Cuenta y pagos", "Crédito"]).astype(float)

matriz = puntajes.copy()
matriz["total"] = sum(puntajes[c] * p for c, p in PESOS.items())
matriz["vetada"] = puntajes["soporte_datos"] == 1
matriz.sort_values("total", ascending=False)
```

**Hallazgos (Markdown):** opción elegida y por qué, en 3–5 líneas. Esto se copia a `docs/decisions.md` (sección 7).

---

## 6. Matriz de decisión

Se llena en la reunión de cierre del lunes, con evidencia del notebook. Se guarda en `analysis/decision_matrix.md`.

**Escala:** 1 = débil, 2 = aceptable, 3 = fuerte. **Puntaje final** = Σ (peso × puntaje). Máximo posible: 45.

| # | Criterio                                  | Peso | Cómo se puntúa                                                                                                                              | Evidencia           | Disputas | Tarjetas | Cuenta y pagos | Crédito |
| :-: | :---------------------------------------- | :--: | :-------------------------------------------------------------------------------------------------------------------------------------------- | :------------------ | :------: | :------: | :------------: | :------: |
| 1 | Volumen de demanda                        |  2  | 3 = el motivo está en el top 3 de contactos o quejas; 2 = relevante (≥ 10 %); 1 = marginal                                                  | Secc. 3             |          |          |                |          |
| 2 | Dolor operativo                           |  2  | 3 = peor que el promedio en ≥ 2 indicadores (FCR, escalamiento, AHT, SLA); 2 = en 1; 1 = en ninguno                                          | Secc. 4             |          |          |                |          |
| 3 | Soporte de los datos (**veto**)     |  3  | 3 = todas las herramientas se construyen con columnas reales y coherentes; 2 = con supuestos menores; 1 = faltan datos clave                  | Secc. 5             |          |          |                |          |
| 4 | Cobertura de escenarios obligatorios      |  3  | 3 = cubre de forma natural aclaración, acción con confirmación, verificación y escalamiento; 2 = cubre la mayoría; 1 = casi solo lectura | A priori            |    3    |    3    |       1       |    2    |
| 5 | Viabilidad del componente de ML           |  2  | 3 = hay un modelo claramente mejor que su baseline; 2 = marginal; 1 = no hay señal                                                           | Secc. 7             |          |          |                |          |
| 6 | Factibilidad en 5 días (3 = bajo riesgo) |  2  | 3 = el equipo lo termina con holgura; 2 = justo; 1 = requiere cosas extra                                                                     | A priori, ajustable |    2    |    3    |       3       |    1    |
| 7 | Historia de negocio                       |  1  | 3 = el impacto se puede estimar con datos; 2 = con supuestos; 1 = difícil de cuantificar                                                     | Secc. 4             |          |          |                |          |
|  | **Total**                           |      |                                                                                                                                               |                     |          |          |                |          |

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
