# Contratos y operación de datos · Fase 2

La fuente oficial es el prefijo `data/` del bucket del hackathon. No se usa el backup.
El pipeline corre fuera del servidor de chat; el backend recibe un DuckDB de solo lectura.
Se versionan el gold reducido de servicio y cinco artefactos pequeños de la corrida de entrega.
El gold completo, las capas Parquet y las bases de trabajo no se versionan en Git. Credenciales exclusivamente en el entorno o
`.env` local: no se incluyen en SQL, logs, reportes ni manifiestos.

## Ejecutar en Windows

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-data.txt
.venv\Scripts\python.exe -m data_pipeline.run_pipeline --full
.venv\Scripts\python.exe -m data_pipeline.run_pipeline --incremental --since 2026-06-17
.venv\Scripts\python.exe -m data_pipeline.verify_backend
.venv\Scripts\python.exe -m pytest -q
```

`make data` ejecuta la carga full (Makefile compatible con la ruta de Python de Windows).
Para abrir el notebook en Jupyter, el entorno de desarrollo completo está en `requirements.txt`.
El proceso carga `.env` sin imprimirlo. `S3_BUCKET` es preferido; se admite `BUCKET` por
compatibilidad con `explorar.py`. También se admiten credenciales temporales mediante la
cadena de credenciales de boto3, incluido `AWS_SESSION_TOKEN`.

Para desarrollo sin AWS, `--local-source C:\ruta\copia-data` recibe un espejo CSV con
las mismas rutas relativas de S3; no recibe Parquet ni un directorio con otro nivel `data/`.
Usar `--data-dir` y `--reports-dir` distintos para no mezclar una fixture y los datos reales.

## Alcance y capas

Se ingieren ocho tablas: transactions, products, customers, daily_exchange_rates,
complaints, call_center_interactions, satisfaction_surveys y service_agents.
Transacciones: 2025-07-01 a 2026-06-17. Las otras tablas conservan su histórico disponible
hasta `reference_date`. Los textos descartados para ML y marketing no se reprocesan.

| Capa/artefacto | Ubicación y contenido |
|---|---|
| Bronze | `data/bronze/<tabla>/<hash>.parquet`: valores CSV como texto, vacíos como nulos; ninguna corrección de negocio |
| Metadatos bronze | `_source_file`, `_ingested_at` UTC, `_file_hash` SHA-256 de bytes CSV, `_partition_date` y ordinal `_source_row` |
| Silver | `data/runs/<run_id>/silver/<tabla>.parquet`: tipos, deduplicación, fechas y correcciones; conserva columnas adicionales |
| Gold completo | `data/gold/gold_full.duckdb`: transacciones del período con relaciones válidas, todos los tipos de producto |
| Gold para backend | `data/gold/gold.duckdb`: clientes de demo + muestra determinista de 100 clientes, transacciones de tarjetas |
| Calidad | `reports/quality_report.json`; copia inmutable en cada corrida |
| Linaje | `data/manifest.json` identifica última publicación exitosa; cada corrida tiene su propio manifiesto |
| Demos | `reports/demo_scenarios.json`: cliente, transacción, monto, mensaje y regla esperada |
| Integración | `reports/backend_acceptance.json`: ocho recorridos HTTP sobre gold y SQLite en memoria |
| Política | `reports/policy_calibration.json`, notebook `analysis/02_politica.ipynb` |
| Narrativa | `analysis/metricas_problema.json`: métricas con numeradores/denominadores explícitos |

Bronze contiene campos sensibles del dataset sintético; solo gold aplica minimización.
`work.duckdb` dentro de la corrida es almacenamiento de trabajo local, no es un entregable
para frontend/backend. Los archivos de las corridas anteriores se conservan para auditoría.

## Transformaciones y calidad

- Los esquemas mínimos de cada archivo están en `data_pipeline/contracts.py` (`REQUIRED`).
  Falta de columna, tipos inválidos, PK nula/duplicada después de deduplicar, dominios inválidos,
  montos no positivos, scores fuera de 0–100 y números no finitos son fallas duras.
- Pandera valida lotes de hasta 50,000 filas. La unicidad se comprueba también globalmente
  con DuckDB para detectar duplicados que crucen lotes.
- PK: ID de cada tabla; tasas: `(date, source_currency, target_currency)`.
- Deduplicación por PK: `last_updated` si existe; después fecha de negocio y timestamp
  del evento en hechos; luego ingesta, archivo, hash y ordinal de fila para desempate determinista.
  Se cuentan filas descartadas. Duplicados de contenido con ID distinto se advierten y se
  conservan: dos cargos iguales pueden representar precisamente un cobro duplicado.
- `business_date` sale de la partición; cuando no hay partición, de `process_date`.
  Si ambos existen y discrepan, se bloquea. Ninguna fecha de negocio supera `reference_date`.
- El diccionario no declara zona horaria. Timestamps sin offset se interpretan como UTC
  **por supuesto explícito**, configurable con `--source-timezone`; los que incluyen offset
  se convierten a UTC. No se cambia la fecha de negocio a partir del timestamp.
- `Mexico` se normaliza a `México`. No se inventan monedas MXN en transacciones/productos;
  MXN sí puede existir legítimamente en tasas y quejas históricas.
- USD: `amount_usd = amount`. ARS/COP: conservar valor existente; si falta, multiplicar por
  `exchange_rate` del par moneda→USD y misma fecha de negocio, redondeando a centavos.
  No se usa una tasa futura, inversa ni aproximada. Si no hay tasa, falla antes de publicar.
- `fraud_score` nulo se conserva: activa R8. `is_fraud` permanece solo en bronze/silver
  para calibración; nunca se exporta a gold.
- Huérfanos se reportan. Gold excluye transacciones sin cliente, producto o dueño coherente
  y cuenta esa exclusión. Los datos no se corrigen inventando relaciones.
- `prior_complaints_90d` cuenta **todas las quejas históricas** del cliente en la ventana
  inclusiva `[reference_date - 90, reference_date]`, no solo las subcategorías de disputa.
  No se utiliza el booleano `is_repeat_complainer` como sustituto de ese conteo.
  El backend suma los casos operativos abiertos por separado.
- Tasas esperadas de nulos son alertas, no imputaciones: score >25 %, comercio >85 %,
  otros campos >10 %. Nulos de duración o días de resolución son visibles en el reporte
  y las métricas calculan denominadores de valores observados.

## Esquema exacto de serving

La especificación única se extrae del literal `SCHEMA` de `scripts/make_demo_gold.py`
mediante AST, sin importar/ejecutar ese script. Las pruebas comparan `PRAGMA table_info`
para tipos, claves y nulabilidad. No se modificó ningún archivo de backend.

| Tabla | Columnas (orden del contrato) |
|---|---|
| dispute_transactions | transaction_id, customer_id, product_id, business_date, amount, currency, amount_usd, merchant_name, transaction_type, channel, status, fraud_score |
| cards | product_id, customer_id, card_mask, status |
| customer_profile | customer_id, segment, country, prior_complaints_90d |
| demo_customers | customer_id, display_name, segment, country, suggested_language, scenario |

Los identificadores y textos son VARCHAR, montos y score DOUBLE, business_date DATE y
prior_complaints_90d INTEGER. Son nulos permitidos únicamente `merchant_name`, `fraud_score`
y `card_mask`. Se preservan PK y NOT NULL de la especificación.
Se agrega `baseline_metrics(metric, value_json)`, que el backend ignora.

`cards` solo contiene Tarjeta Crédito y Tarjeta Débito. La demo restringe sus transacciones
a estos productos para garantizar cobertura de tarjetas sin convertir cuentas/préstamos
en tarjetas ficticias. El gold completo conserva también esas otras transacciones:
un flujo de bloqueo sobre una cuenta requiere decisión del equipo backend, no una
falsificación de `cards`. Nombres de demo ficticios, máscara `•••• 1234`; sin nombre real,
documento, dirección, contacto ni `is_fraud` en tablas de serving.

## Demos y mensajes

Se buscan clientes reales distintos para normal, ambiguo, fraude, zona gris, score nulo,
monto alto, rechazo y portugués. Son obligatorios normal/ambiguo/fraude/PT; los demás
producen advertencia si no existen. La corrida real de entrega contiene los ocho.

Fechas y precedencia se respetan: búsqueda 120 días, reclamo 60 días; reglas R2–R6
pueden prevalecer sobre fraude. El caso normal exige score bajo, monto permitido,
historial <3 y búsqueda inequívoca. El fraude exige tarjeta Active. La ambigüedad usa
dos cargos reales del mismo monto, sin fabricarlos.

Los IDs y mensajes reproducibles están en `reports/demo_scenarios.json`, generado en
cada corrida. Se usan decimales con coma para el NLU actual. La prueba de aceptación
verifica que la candidata prevista aparezca entre las opciones, confirma mediante botones
y verifica el caso y el bloqueo. El escenario ambiguo puede terminar en escalamiento según
el riesgo de la transacción elegida; ambigüedad describe la búsqueda, no una regla final.

Selección verificada con política 1.1.0 (29-sep-2026). El JSON generado es la referencia
si se cambia la fuente o la política:

| Escenario | customer_id | transaction_id | Monto y moneda |
|---|---|---|---|
| Normal | CLI-J5NJU5RPGL86 | TRX-005HIZC65RATD2IHQPL3 | 83,05 USD |
| Ambiguo | CLI-LGP3LQTS3OFT | TRX-6YLV6ZITHQPP22FTOUKF | 399,76 USD |
| Fraude | CLI-MJYE6F3P14V7 | TRX-1VU2UC2RH9V04TFG4POG | 232,76 USD |
| Zona gris | CLI-RK7NEP9EA8S9 | TRX-22XUFBHYP6Q91OVZRZB2 | 23,62 USD |
| Riesgo desconocido | CLI-LWKFG1BSHVUA | TRX-0010BAIHUZK701H93FDJ | 566076,69 COP |
| Monto alto | CLI-60BVCS0DG226 | TRX-0003Y34IMGRAAKKVVQHR | 1952832,76 COP |
| Rechazado | CLI-3QT57SJ5FEL5 | TRX-001NVLXOPXU9E5X48EG3 | 485,48 USD |
| Portugués | CLI-46JMKDWLAJFU | TRX-006NVIV8DGO5P0U8M3JD | 352,78 USD |

Normal: `No reconozco un cargo de 83,05 en Tienda Don José`.
Ambiguo: `No reconozco un cargo de 399,76`, elegir la transacción indicada.
Fraude: `No reconozco un cargo de 232,76`, confirmar bloqueo y después registro del caso.
Portugués: `Não reconheço uma compra de 352,78 em Teatro Nacional`.
Para los demás, `No reconozco un cargo de <monto>`; usar coma decimal y confirmar con botones.

## Incrementalidad y frescura

T+1 es la política objetivo. Estos datos son estáticos: frescura se mide contra 2026-06-17,
no contra la fecha real de septiembre. Se reportan fecha máxima y días de atraso por tabla.

`--incremental --since D --reprocess-days 3` incluye particiones desde D−3, inclusive.
Las dimensiones sin partición se revisan en cada ejecución. Se pagina el inventario S3;
ETag + LastModified detectan cambios (ETag **no** se presenta como checksum SHA-256).
Los bytes leídos tienen SHA-256 propio y el Parquet cacheado se verifica antes de reutilizarse.

Solo los CSV nuevos/cambiados seleccionados se descargan. Silver y gold se reconstruyen
desde el conjunto bronze acumulado: es incremental en extracción y hace upsert lógico por
PK, con reconstrucción de derivados para simplificar consistencia. No se promete procesamiento
incremental de cada agregado. Repetir una corrida preserva el contenido lógico; manifiestos,
tiempos y bytes internos de DuckDB no tienen por qué ser iguales.

Cambios anteriores a la ventana se advierten y requieren `--full` o un `--since` anterior.
En incremental, un archivo desaparecido se conserva y se advierte; un full reconcilia el
inventario. Un full puede reutilizar bronze idéntico verificado: no necesita volver a transferirlo.

La fixture `tests/fixtures/incremental/scenario.json` está rotulada como generada por el
equipo: día N, N+1 con duplicado actualizado, partición N−2 que aparece tarde y columna nueva.
Los tests verifican resultado, upsert, idempotencia y equivalencia con reconstrucción full.

## Publicación, recuperación y entrega

Cada corrida genera artefactos inmutables y una copia de la política. Se publican después
de contratos, calidad y aceptación del backend. El archivo activo `gold.duckdb` se reemplaza
atómicamente; una validación fallida conserva el gold activo. No hay transacción atómica
conjunta entre todos los archivos: la corrida inmutable es la evidencia autoritativa si falla
la copia de un reporte. Detener/reiniciar el backend al actualizar gold, especialmente en Windows.

Un lock evita dos pipelines sobre el mismo `data-dir`. Si se interrumpe violentamente,
comprobar que no quede otro pipeline activo antes de retirar `data/.pipeline.lock` manualmente.
Los errores externos se reportan por tipo y etapa, sin filas originales ni credenciales.

La imagen de servicio incluye `data/gold/gold.duckdb` mediante el Dockerfile.
El gold completo queda fuera del despliegue. Las semillas, métricas históricas,
calibración, aceptación del backend y copia de política de la corrida
`20260929T234658Z-7cf922c1` se conservan en `data/runs/`.
La copia de política de esa corrida es 1.1.0; la política vigente del sistema
es 1.3.0. No deben sustituirse entre sí.

La prueba de versiones de trazas consulta la política activa; el desajuste con el
literal 1.0.0 del estado inicial ya fue corregido. Los ocho recorridos de aceptación
de datos y la suite posterior se documentan en la evidencia de evaluación.
