# Notas de Datos — Factored Hackathon 2026

> Anexo de exploración inicial. Los hallazgos describen esa muestra; el tratamiento implementado y las poblaciones de entrega están en [contratos de datos](data_contracts.md) y [reporte final](eval_report.md). Las tareas exploratorias no son requisitos pendientes para ejecutar la demo.

> Hallazgos del análisis exploratorio (EDA) del dataset **LATAM Bank v1.0.0**.
> Fecha: 27 de septiembre de 2026.
> Scripts: `explorar.py`, `probar.py`, `eda_1.py`, `eda_2.py`, `eda3.py`.

---

## 1. Fuente y estructura

| Aspecto | Detalle |
|---|---|
| Origen | Amazon S3, bucket de solo lectura (`us-east-2`) |
| Formato | CSV |
| Particionado | Estilo Hive: `year=YYYY/month=MM/day=DD/` (tablas de hechos) |
| Archivos totales en el bucket | 12,505 |
| Copia local | `C:\factored_data` (fuera del repo y de OneDrive) |
| Herramienta | DuckDB (`read_csv_auto`, `hive_partitioning=true`, `union_by_name=true`) |

### Tablas descargadas

| Tabla | Tamaño | Uso previsto |
|---|---|---|
| transactions | 0.81 GB | Transacciones que el cliente disputa; `fraud_score` para reglas |
| call_center_interactions | 0.14 GB | Análisis de demanda (volumen, FCR) |
| call_transcripts | 0.14 GB | Evaluado y descartado para entrenamiento (ver §5) |
| products | 0.07 GB | Tarjetas y cuentas del cliente |
| customers | 0.05 GB | Datos del cliente, historial |
| satisfaction_surveys | 0.05 GB | CSAT (pendiente de analizar) |
| complaints | 0.02 GB | Quejas y disputas (PQR) |
| branches, service_agents, daily_exchange_rates | < 0.01 GB | Referencia |

### Tablas no descargadas (y por qué)

| Tabla | Tamaño | Motivo |
|---|---|---|
| digital_events | 3.76 GB | Navegación en app/web, no atención al cliente. Posible uso futuro puntual (sesiones, errores previos a una llamada), consultándolo directo desde S3 con filtros. |
| campaign_sends, marketing_campaigns | 0.33 GB | Marketing, fuera del alcance del workflow. |

### Anomalías en el bucket

- **`data_backup_20260831/` está incompleto:** no tiene `call_transcripts` ni `satisfaction_surveys`, y `transactions` tiene 453 particiones en lugar de 1,097. **Decisión:** se usa `data/` como única fuente de verdad.
- **`marketing_campaigns.csv` duplicado** en la raíz del bucket. Se ignora.
- **`campaign_sends` tiene 1,083 particiones diarias en lugar de 1,097:** faltan 14 días, compatible con las "llegadas tardías" que anuncia la documentación.

---

## 2. Filas faltantes respecto al diccionario

El diccionario declara un número de filas por tabla. Las cifras reales son menores, y **no hay IDs duplicados** en ninguna de las tablas revisadas: las filas simplemente no están.

| Tabla | Filas declaradas | Filas reales | Faltantes | Duplicados por ID |
|---|---|---|---|---|
| call_center_interactions | 800,000 | 686,296 | −14.2% | 0 |
| call_transcripts | 200,000 | 171,321 | −14.3% | — |
| complaints | 80,000 | 67,095 | −16.1% | 0 |
| transactions | 5,000,000 | 4,425,008 | −11.5% | 0 |

**Implicación:** el ~2% de duplicados que anuncia la documentación no aparece a nivel de ID. Queda pendiente revisar duplicados por contenido (filas idénticas con distinto ID).

---

## 3. Call center: dónde está el problema

### Hallazgo: `contact_reason` no tiene información útil

`contact_reason` debería contener el motivo específico del contacto, pero **es idéntico a `reason_category`** en el 100% de los casos. El banco no registra el motivo detallado.

### Hallazgo: aparece una categoría no documentada

El diccionario lista 5 categorías (Transactional, Product, Technical, Commercial, Complaint). Los datos tienen **6**: aparece **"Retención"**. Es evolución de esquema no documentada.

### KPIs por categoría

| Categoría | Contactos | % del total | FCR | Sin resolver al 1er contacto | Duración prom. |
|---|---|---|---|---|---|
| **Queja** | 117,021 | 17.1% | **43.6%** | **~66,000** | 7.2 min |
| Técnico | 102,899 | 15.0% | 69.9% | ~31,000 | 6.0 min |
| Transaccional | 240,056 | 35.0% | 91.5% | ~20,400 | 3.7 min |
| Comercial | 54,879 | 8.0% | 65.2% | ~19,100 | 9.0 min |
| Retención | 20,578 | 3.0% | 60.2% | ~8,200 | 8.0 min |
| Producto | 150,863 | 22.0% | 89.6% | ~15,700 | 4.4 min |

*Sin resolver = contactos × (1 − FCR).*

**Conclusión:** "Queja" genera más contactos sin resolver que cualquier otra categoría, más del doble que la siguiente. Transaccional es la categoría más grande, pero ya se resuelve bien.

### Advertencia: variables sin señal

- **% de escalamiento:** ~10% en todas las categorías (9.8%–10.1%).
- **Sentimiento promedio:** casi idéntico en todas (−0.07 a 0.00).

Parecen generados al azar por el generador sintético. **No se usan como evidencia** para priorizar.

---

## 4. Complaints (PQR)

### Distribución por subcategoría

| Categoría | Subcategoría | Casos | % SLA roto | Días de resolución |
|---|---|---|---|---|
| Transactions | **Cargo no reconocido** | 12,297 | 20.4% | 15.4 |
| Fees | **Cobro indebido** | 12,194 | 19.9% | 15.6 |
| Technical | Problema con app | 12,128 | 20.0% | 15.5 |
| Branch | Atención en sucursal | 11,892 | 20.4% | 15.6 |
| Service | Calidad de servicio | 11,886 | 20.3% | 15.9 |
| (varias) | *vacía* | ~6,600 | — | — |

- **Las disputas (cargo no reconocido + cobro indebido) suman 24,491 casos: ~40% de las quejas con subcategoría.**
- Tardan **~15.5 días** en resolverse y **1 de cada 5 rompe SLA**.
- **~10% de las quejas no tiene subcategoría.**
- Distribución casi uniforme entre subcategorías: comportamiento típico de dato sintético.

### Estado actual de las disputas

| Estado | Casos | % |
|---|---|---|
| In Process | 9,821 | 40.1% |
| Open | 7,278 | 29.7% |
| Resolved | 4,971 | 20.3% |
| Escalated | 1,253 | 5.1% |
| Closed | 934 | 3.8% |
| Rejected | 234 | 1.0% |

**El 70% de las disputas sigue abierto o en proceso.** Compensación promedio en resueltas o cerradas: ~254.

### Hallazgo: las descripciones son plantillas (leakage)

- **5 descripciones distintas** en 67,095 quejas.
- Formato: `"Queja relacionada con {categoría}"`.
- **La etiqueta está escrita dentro del texto.** Entrenar un clasificador sobre `description` sería leakage directo. **Descartado.**

### Hallazgo: los montos reclamados ignoran la moneda

| Moneda | Casos | Mínimo | Mediana | Máximo |
|---|---|---|---|---|
| COP | 1,989 | 51 | 2,358 | 4,998 |
| ARS | 2,009 | 60 | 2,521 | 4,995 |
| MXN | 2,035 | 51 | 2,587 | 5,000 |
| USD | 2,094 | 61 | 2,608 | 4,999 |
| *vacía* | **16,364** | 60 | 2,687 | 4,962 |

- Todas las monedas comparten el mismo rango (~50–5,000), aunque 5,000 COP ≈ 1 USD y 5,000 USD es un monto alto.
- **66.8% de las disputas no tiene moneda.**
- **Decisión:** `claimed_amount` **no se usa** para reglas de umbral. El monto se toma de la transacción real en `transactions`.

---

## 5. Call transcripts

- **Solo 546 textos distintos** en 171,321 transcripts.
- `detected_intents` = `consulta_general` en el 95% de los casos, y vacío en el resto.
- **Placeholders sin rellenar** en el texto: `{monto}`, `{moneda}`, `{limite}`.
- **`main_topics` no corresponde al texto:** la misma llamada ("consultar saldo de tarjeta") aparece etiquetada como Comercial, Técnico y Transaccional.
- Texto duplicado dentro de un mismo transcript y errores de tipeo ("No hayproblema").

**Conclusión:** no son aptos para entrenar ni evaluar un clasificador de intención. **Descartados como fuente de entrenamiento.**

---

## 6. Transactions

### Prevalencia de fraude

| is_fraud | Transacciones | % |
|---|---|---|
| False | 4,420,692 | 99.902% |
| True | 4,316 | 0.098% |

Aproximadamente 1 fraude por cada 1,000 transacciones.

### `fraud_score` vs fraude real

| Rango de score | Transacciones | Fraudes | % fraude |
|---|---|---|---|
| 0–9 | 1,179,452 | 337 | 0.03% |
| 10–19 | 1,179,243 | 359 | 0.03% |
| 20–29 | 1,178,174 | 356 | 0.03% |
| **30–39** | 969 | 360 | **37.15%** |
| **40–99** | 2,013 | 2,013 | **100.00%** |
| *vacío* | 885,157 (20.0%) | 891 | 0.10% |

- **Score ≥ 40 → 100% de precisión** en 2,013 casos históricos.
- Con corte en ≥ 30, el score detecta ~2,373 de 4,316 fraudes (**~55% de recall**).
- El ~45% restante de los fraudes está distribuido al azar (tasa ≈ ruido de fondo), sin relación con el score.
- **20% de las transacciones no tiene `fraud_score`.**

### Ninguna otra variable tiene señal de fraude

- Por tipo y canal: 0.10%–0.19% en todas las combinaciones.
- País de la transacción distinto al del cliente: 0.11%, contra 0.10% cuando coincide. En datos reales esta sería una señal fuerte; aquí no existe.

**Conclusión:** el fraude fuera del rango del score es ruido. **Un modelo de fraude no puede superar al `fraud_score` como baseline.** Se descarta como componente aprendido principal.

**Decisión:** el `fraud_score` se usa directamente en el motor de reglas, con umbrales justificados por esta tabla:
- **≥ 40:** fraude de alta confianza.
- **30–39:** zona gris, escala a humano.
- **< 30 o vacío:** sin indicio por score.

### Estados de transacción

| Estado | Transacciones |
|---|---|
| Approved | 4,070,681 |
| Declined | 221,234 |
| Pending | 88,343 |
| Reversed | 44,750 |

### Monedas

| Moneda | Transacciones | Mediana | Mediana en USD |
|---|---|---|---|
| ARS | 792,585 | 163,285 | 466.40 |
| USD | 2,437,979 | 467.08 | **vacío** |
| COP | 1,194,444 | 1,867,136 | 466.86 |

- **No hay transacciones en MXN**, aunque México es uno de los tres países del dataset. Pendiente: verificar en qué moneda operan los clientes mexicanos.
- **`amount_usd` está vacío en todas las transacciones en USD.** Debería ser igual a `amount`. **Corrección en el pipeline:** `amount_usd = amount` cuando `currency = 'USD'`.
- Aquí los montos sí respetan la moneda (COP en millones, ARS en cientos de miles), a diferencia de `complaints`.

---

## 7. Resumen de decisiones

| # | Decisión | Evidencia |
|---|---|---|
| 1 | Workflow: **disputas de transacciones** | "Queja" tiene la mayor cantidad de contactos sin resolver (~66k, FCR 43.6%); las disputas son ~40% de las quejas; 70% siguen abiertas. |
| 2 | `data/` como fuente de verdad | El backup está incompleto. |
| 3 | No usar `contact_reason` | Es idéntico a `reason_category`. |
| 4 | No entrenar con transcripts ni descripciones de quejas | Son plantillas; en las quejas la etiqueta está en el texto (leakage). |
| 5 | No usar `claimed_amount` para reglas | Ignora la moneda; 67% sin moneda. |
| 6 | `fraud_score` en reglas con umbrales 30 / 40 | 100% de precisión en ≥ 40; 37% en 30–39. |
| 7 | No construir modelo de fraude | Ninguna variable tiene señal fuera del score. |
| 8 | Componente aprendido: **clasificador de intención ES/PT** | La intención real no existe en los datos; el portugués es obligatorio y no viene en el dataset. |
| 9 | No usar escalamiento ni sentimiento como evidencia | Uniformes entre categorías (~10%, ~−0.06). |

---

## 8. Limitaciones para reportar

- **Idioma:** todo el dataset está en español. El portugués se cubre con datos generados por el equipo, que deben documentarse como tales.
- **Moneda:** no hay transacciones en MXN.
- **Etiquetas:** las variables de texto y de intención del dataset no son utilizables.
- **Filas faltantes:** entre 11% y 16% menos filas que las declaradas en el diccionario.
- **Señales sintéticas:** varias métricas (escalamiento, sentimiento, fraude fuera del score, SLA) son uniformes. Los resultados no deben interpretarse como comportamiento real de clientes.
- **Resultados offline:** toda mejora medida es una comparación offline, no una mejora de producción comprobada.

---

## 9. Pendientes

- [ ] Revisar duplicados por contenido (no solo por ID).
- [ ] Verificar la moneda de los clientes de México.
- [ ] Analizar `satisfaction_surveys`: ¿las quejas tienen peor CSAT?
- [ ] Revisar si las quejas se pueden vincular a una transacción específica (`complaints` no tiene `transaction_id`, solo `affected_product_id`).
- [ ] Porcentaje de nulos por columna en las tablas que se usarán.
- [ ] Convertir las tablas de CSV a Parquet dentro del pipeline.
