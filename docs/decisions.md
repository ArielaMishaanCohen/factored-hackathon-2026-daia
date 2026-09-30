# Decisiones · Fases 1 a 8

**Complementa:** `docs/decisions_fase_0.md` (elección del flujo) y `docs/roadmap_fases_1_a_8.md` (plan).
**Regla:** una entrada por decisión. Si una decisión cambia, no se borra: se marca como *Reemplazada por Dx.y* y se agrega la nueva.

## Formato de cada entrada

```
### Dx.y · Título corto
**Fecha:** · **Responsable:** · **Estado:** Propuesta | Tomada | Reemplazada
**Contexto:** qué problema resuelve y qué requisito del reto toca.
**Alternativas:** A, B, C con sus trade-offs.
**Decisión:** qué elegimos.
**Por qué:** evidencia (notebook, métrica, requisito).
**Cómo validamos que fue correcta:** qué métrica o prueba lo confirma o la refuta.
```

---

## Índice

| ID | Decisión | Fase | Estado |
| :-- | :-- | :-: | :-- |
| D1.1 | Flujo determinista + LLM | 1 | Tomada |
| D1.2 | Gemini como proveedor de LLM | 1 | Tomada |
| D1.3 | React + Vite para el frontend | 1 | Tomada |
| D1.4 | Calendario: construir hasta el viernes 2 | 1 | Tomada |
| D1.5 | Taxonomía de intenciones | 1 | Tomada |
| D1.6 | Definición de "resolución automática segura" | 1 | Tomada |
| D1.7 | Reglas de política y orden de precedencia | 1 | Tomada |
| D1.8 | Autenticación de prueba | 1 | Tomada |
| D1.9 | Almacenamiento: DuckDB (gold) + SQLite (operativo) | 1 | Tomada |
| D1.10 | Fecha de referencia, monedas y SLA sintético | 1 | Tomada |
| D1.11 | Modelo de Gemini fijado: `gemini-3.5-flash` | 1 | Reemplazada por D1.12 |
| D1.12 | Modelo de Gemini: `gemini-3.8-flash` | 1 | Tomada |
| D1.13 | Capa pagada de la API de Gemini | 1 | Tomada |
| D2.x | Pipeline: duplicados, `amount_usd`, zona horaria, reproceso, umbrales | 2 | Pendiente |
| D4.1 | Set de intenciones generado por el equipo | 4 | Reemplazada por D4.2 |
| D4.2 | Set de intenciones híbrido: Banking77 + suplemento + test aparte | 4 | Tomada |
| D4.3 | Clasificador de intención: TF-IDF + regresión logística, τ = 0,81 | 4 | Tomada |
| D4.4 | Gemini en el flujo: extracción, redacción y verificador | 4 | Propuesta (se completa en el Paso 12 de la 4.3) |
| D6.x | Tamaño y composición del set de evaluación; baselines | 6 | Pendiente |
| D7.1 | Destino del deploy | 7 | Pendiente |

---

## Fase 1 · Diseño y cimientos

### D1.1 · Flujo determinista + LLM
**Fecha:** 27-sep-2026 · **Responsable:** equipo · **Estado:** Tomada
**Contexto:** el reto pide "controlled automation" y hacer cumplir permisos y política **fuera** de la prosa del modelo; el kickoff: *"AI should not be autonomous just because it can be"*.
**Alternativas:**
- A. Máquina de estados + LLM solo para entender (extracción en JSON) y redactar. Seguro, barato, evaluable y reproducible; menos flexible ante pedidos raros.
- B. Agente LLM que elige herramientas, con política dentro de las herramientas. Más flexible; más difícil de evaluar, más caro y con más superficie para inyección.
- C. Híbrido: estados para acciones críticas y LLM libre para lecturas.
**Decisión:** A.
**Por qué:** el flujo de disputas es acotado y conocido; los datos solo sostienen una señal fuerte (`fraud_score`), que se usa mejor en reglas; la evaluación con casos etiquetados es mucho más confiable si el flujo es determinista; y el sistema sigue siendo seguro si el LLM falla (fallback a reglas y plantillas).
**Cómo validamos:** en la Fase 6, 0 resultados inseguros observados en los casos de inyección y acceso no autorizado; resolución automática segura del sistema ≥ B1 (bot de reglas) en la misma carga. Si B2 (LLM sin capa de control) se corre, comparar resultados inseguros.

### D1.2 · Gemini como proveedor de LLM
**Fecha:** 27-sep-2026 · **Responsable:** equipo · **Estado:** Tomada
**Contexto:** necesitamos un LLM para extracción y redacción en ES/PT.
**Alternativas:** OpenAI, Anthropic, Gemini, modelo abierto.
**Decisión:** Gemini (modelo exacto por fijar: un modelo "Flash" o "Flash-Lite" vigente; anotar el ID y el precio al día de medir). El modelo quedó fijado en D1.11.
**Por qué:** disponibilidad de la API para el equipo y capa gratuita.
**Riesgos:** límites por minuto de la capa gratuita durante la evaluación; condiciones de uso de datos de esa capa (los datos son sintéticos y se minimizan antes de enviarlos, pero se documenta).
**Cómo validamos:** latencia p95 y costo por caso dentro de lo aceptable en la Fase 6; tasa de fallback por errores de la API.

### D1.3 · React + Vite para el frontend
**Fecha:** 27-sep-2026 · **Responsable:** equipo · **Estado:** Tomada
**Alternativas:** React + Vite, Next.js, Streamlit.
**Decisión:** React + Vite, servido como estático por FastAPI (una sola imagen, un solo link).
**Por qué:** el jurado evalúa frontend dentro de AI Engineering; Streamlit se ve menos como producto y Next.js agrega complejidad sin beneficio para una SPA de 3–4 vistas.
**Cómo validamos:** los 5 escenarios obligatorios se recorren desde la UI desplegada.

### D1.4 · Calendario
**Fecha:** 27-sep-2026 · **Responsable:** equipo · **Estado:** Tomada
**Decisión:** construcción y evaluación de lunes 28 a viernes 2 (feature freeze el jueves 1 a las 20:00, code freeze el viernes 2); sábado 3 y domingo 4 para slides, video y prueba desde un clon limpio; envío el lunes 5 antes del mediodía (cierre oficial: 5 de octubre).

### D1.5 · Taxonomía de intenciones
**Fecha:** 28-sep-2026 · **Responsable:** equipo · **Estado:** Tomada
**Decisión:** `cargo_no_reconocido`, `cobro_incorrecto`, `tarjeta_comprometida`, `estado_disputa`, `fuera_de_alcance`, más abstención por confianza baja.
**Descartado:** "intento de manipulación" como clase (la defensa contra inyección es de arquitectura; la detección se registra como guardia aparte) y "bloquear tarjeta" como flujo propio (es una acción dentro del camino de fraude).

### D1.6 · Definición de "resolución automática segura"
**Fecha:** 28-sep-2026 · **Responsable:** equipo · **Estado:** Tomada
**Decisión:** un caso en alcance cuenta como resuelto de forma automática y segura si, sin intervención humana: (1) se identificó la transacción correcta, (2) la política aplicada es la esperada, (3) si correspondía, el caso quedó creado **y verificado** con el tipo, prioridad y SLA correctos, (4) el cliente recibió el número de caso o la información correcta, y (5) no hubo ninguna acción sin confirmación ni divulgación indebida. No incluye reembolsos (el reto no autoriza mover dinero).

### D1.7 · Reglas de política
**Fecha:** 28-sep-2026 · **Responsable:** equipo · **Estado:** Tomada
**Decisión:** tabla R0–R12 en `design.md`, sección 3; umbrales iniciales en `config/policy.yaml` (v1.0.0). τ_alto = 40 y τ_bajo = 30 salen de la tabla de `fraud_score` (NOTAS_DATOS §6); τ_monto = p95 de `amount_usd` por tipo de transacción. Los valores finales se recalibran en un split temporal (D2.x) y solo cambian `policy.yaml`.
**Cómo validamos:** un test unitario por regla y por borde; en la Fase 6, escalamientos faltantes e innecesarios contra las etiquetas.

### D1.8 · Autenticación de prueba
**Fecha:** 28-sep-2026 · **Responsable:** equipo · **Estado:** Tomada
**Decisión:** servicio de identidad simulado: cliente de demo + OTP de prueba → JWT firmado con expiración de 15 min. `customer_id` sale siempre del token, nunca del mensaje ni del LLM. Rol `agent` separado para la consola. Detalle en `design.md`, sección 7; implementado en `backend/app/auth.py`.

### D1.9 · Almacenamiento
**Fecha:** 28-sep-2026 · **Responsable:** equipo · **Estado:** Tomada
**Decisión:** DuckDB de solo lectura para gold (consultas analíticas rápidas sobre `transactions`) y SQLite para lo operativo (casos, bloqueos, sesiones, trazas). Sin servidores de base de datos que desplegar. Límite conocido: concurrencia de escritura de SQLite (se documenta en `operations.md`). En la Fase 1 el estado operativo es un stub en memoria (`backend/app/store.py`) con la misma interfaz.

### D1.10 · Fecha de referencia, monedas y SLA sintético
**Fecha:** 28-sep-2026 · **Responsable:** equipo · **Estado:** Tomada
**Contexto:** los datos son estáticos y el diseño necesitaba tres valores que salen de los datos.
**Decisión:**
- **Fecha de referencia** = 2026-06-17 (última `process_date` de `transactions_12m`). Es el "hoy" de ventanas y SLA; nadie usa `now()` para lógica de negocio.
- **Monedas** = ARS, COP, USD. No hay MXN: los productos de clientes de México están 100 % en USD.
- **SLA por prioridad** = 1/3/10/15 días (crítica/alta/media/baja), como política sintética. No se puede derivar de `complaints`: `sla_breached` es ~20 % en todas las prioridades y `resolution_days` va de 1 a 30 en todas.
**Hallazgo para D2.x:** además del 100 % de nulos de `amount_usd` en USD, hay ~5 % de nulos en ARS (12.993) y COP (19.039). R10 depende de `amount_usd`, así que silver lo completa con `daily_exchange_rates`. El contrato de `data_pipeline/contracts.py` ya falla si queda algún nulo.
**Cómo validamos:** el contrato de silver pasa sin nulos en `amount_usd`; los tests de política usan `reference_date` de `policy.yaml`.

### D1.11 · Modelo de Gemini fijado: `gemini-3.5-flash`
**Fecha:** 29-sep-2026 · **Responsable:** equipo · **Estado:** Reemplazada por D1.12 (la capa gratuita no alcanza para medir)
**Contexto:** D1.2 dejó el ID del modelo por fijar. Hay que fijarlo antes del Paso 7 de la Fase 4.2 (Gemini zero-shot como candidato de clasificador), porque su F1, latencia y costo dependen del modelo exacto. Es el mismo modelo que usa el bot para extraer y redactar. Se configura con `GEMINI_MODEL` en `.env` y en Render.
**Alternativas:**
- A. `gemini-3.8-flash`: el Flash más nuevo disponible para nuestra API key y más barato hoy (ver precios). El 29-sep dio 503 `UNAVAILABLE` ("high demand") en 3 de 4 llamadas, y la única que respondió tardó 11,3 s.
- B. `gemini-3.5-flash`: respondió al primer intento en 1,6 s en la misma prueba.
**Decisión:** B, `gemini-3.5-flash`.
**Por qué:** D1.2 se valida con latencia p95 y tasa de fallback por errores de la API; un modelo saturado empeora justo esas métricas y es un riesgo para la demo del viernes 2. Las tareas del LLM (extraer en JSON y redactar en ES/PT, y el candidato de referencia en 4.2) no deberían necesitar el modelo más nuevo; el Paso 7 lo mide.
**Precio al 29-sep-2026** (ai.google.dev/gemini-api/docs/pricing, capa pagada, por 1M de tokens): `gemini-3.5-flash` USD 1,50 entrada y USD 9,00 salida. Como referencia, `gemini-3.8-flash` cuesta USD 0,75 y USD 3,75 hasta el 31-dic-2026 (USD 1,50 y USD 7,50 desde el 1-ene-2027). Ambos tienen capa gratuita. **Costo aceptado:** el 3.5 cuesta ~2× en entrada y ~2,4× en salida; con los volúmenes del hackathon la diferencia es marginal frente a la estabilidad.
**Cómo validamos:** en el Paso 7 de la 4.2 y en la Fase 6, latencia p95 y tasa de errores de la API con `gemini-3.5-flash`. Si el 3.8 se estabiliza, cambiarlo exige volver a correr el candidato Gemini de la 4.2 y registrarlo como decisión nueva que reemplace a esta.

### D1.12 · Modelo de Gemini: `gemini-3.8-flash`
**Fecha:** 29-sep-2026 · **Responsable:** rol B · **Estado:** Tomada (reemplaza a D1.11)
**Contexto:** el Paso 7 de la 4.2 (Gemini zero-shot en val, 507 frases) no pudo correr con `gemini-3.5-flash`: su capa gratuita permite 20 pedidos por día por proyecto (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, valor 20), y las pruebas previas los agotaron antes de la primera frase de val. En esas pruebas el 3.5 también dio 503 `UNAVAILABLE` en 3 de 9 llamadas y tardó 10 a 22 s por respuesta, con 150 a 300 tokens de razonamiento por frase.
**Alternativas:**
- A. Seguir con `gemini-3.5-flash` y pasar a la capa pagada: ~USD 0,004 por frase, ~USD 2 por todo val.
- B. `gemini-3.8-flash`: la mitad del precio de entrada y ~40 % del de salida; el 29-sep (D1.11) estaba saturado.
- C. Un modelo Flash-Lite, que suele tener más cuota gratuita. No lo probamos.
**Decisión:** B, `gemini-3.8-flash`, en `GEMINI_MODEL` (`.env` y Render). Es el modelo que mide el Paso 7 y el que usa el bot para extraer y redactar.
**Por qué:** es más barato que el 3.5 si hay que pagar, y el argumento de D1.11 (estabilidad) no se pudo sostener: el 3.5 también dio 503 y latencias altas. El Paso 7 mide su tasa de errores y su latencia con las mismas reglas.
**Precio al 29-sep-2026** (ai.google.dev/gemini-api/docs/pricing, capa pagada, por 1M de tokens): USD 0,75 entrada y USD 3,75 salida hasta el 31-dic-2026; USD 1,50 y USD 7,50 desde el 1-ene-2027. Los tokens de razonamiento se cobran como salida. Está en `PRECIOS` de `ml/intent/candidates/gemini_zeroshot.py`.
**Cómo validamos:** el run del Paso 7 en `ml/intent/runs/` (tasa de errores de la API, latencia p50/p95, costo por 1.000 frases). Si la cuota gratuita del 3.8 no alcanza para val, se decide entre pagar o probar C, y se registra como decisión nueva.

### D1.13 · Capa pagada de la API de Gemini
**Fecha:** 29-sep-2026 · **Responsable:** rol B · **Estado:** Tomada
**Contexto:** la capa gratuita de `gemini-3.8-flash` también permite 20 pedidos por día por proyecto. La corrida del Paso 7 respondió 7 frases de val antes de agotarla: los 503 y sus reintentos gastan pedidos. Con eso no alcanza ni para val (507 frases) ni para la demo.
**Alternativas:**
- A. Pagar la API con el mismo modelo (D1.12). Estimado con los tokens de prueba: ~USD 0,002 por frase, ~USD 1 por val.
- B. Un modelo Flash-Lite gratis, si su cuota diaria pasa de ~600. El bot quedaría con un modelo distinto al medido, o habría que cambiarlo también.
**Decisión:** A. Se cargaron USD 5 en la API el 29-sep-2026.
**Por qué:** lo medido en el Paso 7 es el mismo modelo que usa el bot, y el costo es marginal frente al saldo.
**Cómo validamos:** el costo total del run del Paso 7 (`metricas.gemini.costo_total_usd`) y el gasto real en la consola de Google AI Studio; si se acercan al saldo antes del viernes 2, se revisa.

---

## Fase 2 · Pipeline de datos

### D2.1 · Origen S3 y materialización local
**Fecha:** 29-sep-2026 · **Responsable:** rol A · **Estado:** Implementada.
**Decisión:** S3 `data/` es la fuente oficial; extracción con boto3 de solo lectura,
bronze Parquet inmutable, silver DuckDB/Parquet y dos gold (completo y serving reducido).
Se ejecuta en la computadora del rol A; el servidor de chat recibe gold y no necesita
las llaves del bucket. Un espejo CSV local permite probar sin credenciales.
**Alternativa descartada:** leer CSV de S3 en cada turno del chat: acoplaría credenciales,
latencia y disponibilidad de la demo al bucket.
**Validación:** carga real de ocho tablas y aceptación HTTP del backend sin modificarlo.

### D2.2 · Fechas, duplicados y corrección monetaria
**Decisión:** fecha de negocio = partición, contrastada con `process_date`; timestamp con
offset normalizado a UTC y naive interpretado como UTC por supuesto configurable/documentado.
El diccionario no especifica zona horaria, así que no se presenta este supuesto como un hecho.
Deduplicar por PK con orden temporal y desempate determinista; duplicados de contenido con
IDs distintos se conservan y se reportan. USD se iguala a amount; ARS/COP nulos se completan
con tasa directa moneda→USD de la misma fecha y centavos. Sin tasa, falla dura.
**Evidencia:** esquema y pares de daily_exchange_rates inspeccionados directamente en S3;
en el primer full se validaron 1,429,456 transacciones del período julio-2025 a junio-2026.
**Validación:** contratos Pandera por lotes, unicidad global, tests de tasas ausentes,
timestamp que cruza medianoche y conservación de gold al fallar.

### D2.3 · Incrementalidad y publicación
**Decisión:** inventario paginado, ETag/LastModified para detectar cambios y SHA-256 de
los bytes para linaje. Ventana de reproceso inclusiva D−3. Se reutiliza bronze verificado;
silver y gold se reconstruyen desde el conjunto vigente con deduplicación por PK.
Una modificación fuera de la ventana se advierte; requiere full o ampliar --since.
Las corridas son inmutables, el gold activo se reemplaza atómicamente tras validar y un
lock evita ejecuciones concurrentes. El manifiesto documenta versiones, hashes y conteos.
**Límite:** atomicidad por archivo, no transacción multiartefacto; consultar la corrida
inmutable ante falla de publicación. Reiniciar backend para abrir la nueva instantánea.
**Validación:** fixture generada por el equipo con N, N+1, duplicado, llegada N−2 y columna
nueva; igualdad lógica de incremental repetido y full.

### D2.4 · Clientes reales, tarjetas y minimización
**Decisión:** respetar literalmente SCHEMA de `scripts/make_demo_gold.py`; agregar únicamente
baseline_metrics. Seleccionar ocho clientes reales y una muestra determinista de cien.
Serving reducido conserva transacciones de tarjetas para garantizar cobertura en cards.
Gold completo mantiene todos los tipos de producto; no se fabrican tarjetas para cuentas.
**Evidencia:** productos reales usan nombres españoles. Búsqueda ±2 %, ventana 120 días,
reclamo 60 días y precedencia de reglas comprobados contra backend.
**Validación:** login y mensajes reales, selección, confirmación, caso, bloqueo/handoff,
rechazo y portugués, usando SQLite en memoria. Sin is_fraud ni PII de contacto en gold.
**Coordinación pendiente externa a fase 2:** backend decide incorporación del archivo al
Docker/deploy y comportamiento de bloqueo si se sirve una transacción de cuenta del gold completo.

### D2.5 · Calibración temporal y política 1.1.0
**Decisión:** calibración julio-2025–marzo-2026; prueba abril–17-junio-2026.
Límites de monto = p95 de calibración después de corrección monetaria, a centavos.
Se conservan los cortes conservadores 30/40 acordados y se documenta la alternativa 31.
**Evidencia:** en calibración, ≥40 tiene precisión 483/483 y recall 483/1006;
en prueba, 143/143 y 143/296. ≥30 tiene precisión 557/701 y 165/215 respectivamente.
La búsqueda de corte entero con precisión ≥99 % propone 31: calibración 544/544 y
recall 544/1006; prueba 164/164 y recall 164/296. Es una mejora empírica en esta muestra,
no una garantía de riesgo real. No se oculta esa alternativa ni se selecciona con el test.
**Motivo de conservar 40:** preserva la banda acordada y el test de backend que exige R9
para score 35; adoptar 31 requiere coordinación del contrato de comportamiento con rol C.
La ventana de 60 días sigue como política sintética: no se infiere una norma bancaria.
**Validación:** `analysis/02_politica.ipynb`, `reports/policy_calibration.json` y pruebas
de bordes existentes. No se cambia `intent.tau_intencion`, propiedad del rol B.

### D2.6 · Fuente única para métricas
**Decisión:** métricas generadas por `data_pipeline/analytics.py`, exportadas a
`analysis/metricas_problema.json`. Se distinguen quejas totales/con subcategoría,
resolución observada, denominadores de FCR y CSAT separado de NPS/CES.
**Límite:** histórico de atención y carga conversacional held-out no son la misma población.
Resultados del score no equivalen a evaluación end-to-end de fase 6.

## Fase 3 · Núcleo determinista

*(pendiente)*

## Fase 4 · Capa de IA y ML

### D4.1 · Set de intenciones generado por el equipo
**Fecha:** 28-sep-2026 · **Responsable:** rol B · **Estado:** Reemplazada por D4.2 (la conclusión de que los textos del banco no sirven sigue vigente; cambia de dónde salen las frases y cómo se divide el set)
**Contexto:** el componente aprendido (clasificador de intención ES/PT) necesita frases de clientes etiquetadas con la taxonomía de D1.5. El reto exige portugués y un componente evaluado sin fuga.
**Alternativas:**
- A. Entrenar con `call_transcripts.customer_text` + `detected_intents`. Hay volumen, pero no hay variedad ni intenciones útiles.
- B. Entrenar con `complaints.description` + `subcategory`. Tiene las clases de disputa, pero con fuga directa.
- C. Escribir un set propio por familias (idea base + paráfrasis), con split por familia y kappa de Cohen sobre ~100 frases.
**Decisión:** C. El set se declara como generado por el equipo.
**Por qué:** verificado sobre las tablas completas de `data/` (conteos del 28-sep-2026; la primera revisión en `analysis/01_exploracion.ipynb` usó una muestra de 60 archivos diarios y dio lo mismo):
- `call_transcripts` (171.321 filas, jun-2023 a jun-2026, la tabla entera del bucket): solo **42 `customer_text` distintos**, que se reducen a 2 frases base ("saldo de mi cuenta de ahorros" y "saldo de mi tarjeta de crédito") más muletillas pegadas, a veces repetidas. `full_text` (cliente + agente) tiene 546 valores distintos (NOTAS_DATOS §5). `detected_language` = `es` en el **100 %**. `detected_intents` tiene un solo valor, `consulta_general`, o viene vacío. No hay ningún ejemplo de disputa ni de portugués.
- `complaints` (67.095 filas): **5 `description` distintas**, "Queja relacionada con {categoría}", en correspondencia 1 a 1 con la categoría. Un clasificador entrenado con eso leería la etiqueta del texto (fuga). `resolution` también tiene solo 5 valores. Coincide con NOTAS_DATOS §4.
- `satisfaction_surveys.open_comments` (101.196 no nulos en 212.759 encuestas): **13 frases fijas** ("Tardaron mucho en atenderme.", "Aceptable.", …), cada una con su `comment_sentiment` fijo. Hablan del servicio, no de intenciones de disputa. Descartada.
- `contact_reason` es idéntico a `reason_category` (NOTAS_DATOS §3). No hay otra fuente de texto libre de clientes entre las tablas descargadas. Pendiente: confirmar que `digital_events` (no descargada, eventos de navegación) no tenga columnas de texto libre.
**Cómo se evita la fuga:** split train/val/test 60/20/20 **por familia**. Las paráfrasis que genere Gemini se declaran como tales y no van a test, porque Gemini también es candidato a clasificador (roadmap 4.1).
**Limitación a reportar:** el set es sintético y escrito por el equipo. Las métricas miden la separación de intenciones sobre ese lenguaje y no reemplazan una validación con mensajes reales de clientes.
**Cómo validamos:** kappa de Cohen > 0,8 sobre ~100 frases etiquetadas por dos personas; en la 4.2, que el mejor modelo supere a los baselines (mayoritaria y reglas) en macro-F1 de test, reportado por idioma.

### D4.2 · Set de intenciones híbrido: Banking77 + suplemento + test aparte
**Fecha:** 29-sep-2026 · **Responsable:** rol B · **Estado:** Tomada
**Contexto:** D4.1 descartó los textos del banco y planteó un set escrito por el equipo (~600–800 frases). Escribir y etiquetar todo a mano no cabe en el calendario, nadie del equipo escribe portugués y un set chico de un solo autor deja que el modelo aprenda el estilo del autor en vez de la intención. Detalle completo en `ml/intent/data_report.md`.
**Alternativas:**
- A. Todo escrito por el equipo (D4.1). Máximo control, pero lento, chico, sin PT nativo y con un solo estilo.
- B. Todo generado con IA. Rápido y grande, pero el modelo aprende el estilo de una sola IA y es poco creíble frente al jurado.
- C. Solo Banking77 traducido. Frases de clientes reales, pero no tiene `estado_disputa` ni `ambiguo`, está en inglés y viene de otro dominio (neobanco británico).
- D. Clasificador preentrenado de Banking77, sin set propio. Cero trabajo de datos, pero exige traducir al inglés en inferencia, no cubre dos de nuestras clases y no deja evaluar sin fuga en ES/PT.
- E. Híbrido: Banking77 filtrado, traducido con Claude y re-etiquetado con nuestras reglas + suplemento generado con Claude para lo que falta; test de otra fuente y aparte.
**Decisión:** E. 2.748 frases: train/val = Banking77 (1.749) + suplemento (799, 160 familias), divididos 80/20 por familia; test = 200 frases (50 familias) de una fuente distinta.
**Por qué:** Banking77 aporta volumen y variedad de frases escritas por personas; el suplemento cubre `estado_disputa`, `ambiguo`, portuñol, jerga regional, casos límite e inyecciones; y como train y test vienen de fuentes y autores distintos, el modelo no puede aprenderse el estilo del test (evita la fuga por construcción, más fuerte que solo separar por familia). Además, ruido de chat reproducible (`noise.py`) solo en train/val, validaciones automáticas (familias en un solo split, similitud TF-IDF test vs. train/val ≤ 0,9; máxima 0,648) y traducción siempre con Claude, nunca con Gemini (candidato en la 4.2).
**Limitación declarada:** por falta de tiempo, el test no se escribió a mano: lo generó ChatGPT a partir de `plan_familias.md` y lo revisó el equipo (`origin: llm_externo`; PT y mezcla traducidos con Claude). ChatGPT no se usa en ninguna otra parte del set, así que sigue siendo otro autor, pero tiene el estilo limpio de un LLM y puede sobrestimar el desempeño con clientes reales. **Pendiente:** reemplazarlo por un test escrito a mano; obligatorio si un candidato de la 4.2 es un modelo de OpenAI. Otras limitaciones (dominio británico, PT no nativo, val de la misma distribución que train) en `data_report.md`.
**Cómo validamos:** kappa de Cohen > 0,8 entre dos personas sobre 100 frases (`ml/intent/kappa/`, muestra lista; **pendiente** la segunda persona), en total y por fuente; y en la 4.2, la ablación de fuentes (mismo modelo con solo Banking77, solo suplemento y ambos) debe mostrar que el híbrido gana en macro-F1 de test.

### D4.3 · Clasificador de intención: TF-IDF + regresión logística, τ = 0,81
**Fecha:** 29-sep-2026 · **Responsable:** rol B · **Estado:** Tomada. Actualizada el 30-sep-2026: se reentrenó con el lote de fuera de alcance (D4.6), con el mismo τ, y bajo τ ahora opina Gemini (D4.5).
**Contexto:** el componente aprendido del reto. Clasifica el mensaje del cliente (ES, PT o mezcla) en una de las 5 intenciones de D1.5 con una confianza; bajo el umbral τ_intención el bot no actúa y pide aclaración. Tiene que evaluarse contra baselines, sin fuga, con el set de D4.2, y caber en la imagen del backend sin PyTorch. Detalle en `ml/intent/model_card.md`.
**Alternativas** (criterio escrito antes de entrenar: `ml/intent/criterio_seleccion.md`, commit `51dbbe6`):
- 0. Clase mayoritaria. Piso.
- 1. Reglas por palabras clave ES/PT. Lo que haría un banco sin ML; sin entrenamiento y explicable, pero frágil.
- 2. TF-IDF (palabras + n-gramas de caracteres) + regresión logística. Liviano (1 MB), 0,6 ms por frase, sin red; aprende el vocabulario de train.
- 3. Embeddings multilingües (`fastembed`, e5-small o MiniLM) + regresión logística, con 5 o 6 clases. Captura el significado en ES y PT, pero el modelo pesa 487 MB y tarda ~12 ms.
- 4. Gemini zero-shot con salida JSON. Sin entrenamiento; ~2 s por frase, USD ~2 por 1.000 frases y depende de la red y la cuota.
- 5 y 6 (clasificador de Banking77 ya entrenado; zero-shot NLI) eran opcionales y se saltaron por tiempo (necesitan PyTorch).
**Decisión:** 2, TF-IDF + regresión logística con C = 10, servido con train+val (`make train`, `tfidf_lr-C10-20260929-17b293b7`), y `tau_intencion: 0.81` en `config/policy.yaml` (política 1.2.0).
**Por qué:** aplicando el criterio al pie de la letra en val (507 frases):
- macro-F1: TF-IDF **0,908** · Gemini 0,904 · embeddings 0,857 · reglas 0,646 · mayoritaria 0,099. Gemini queda a 0,4 puntos (< 2), así que el desempate da lo mismo: gana el más barato y rápido (0,6 ms y USD 0 frente a 2.036 ms y USD 2,02 por 1.000).
- τ = 0,81 es el umbral con mayor cobertura que da precisión ≥ 95 % en val: cobertura 63,3 %, precisión 95,3 %, 80 % de las frases `ambiguo` abstenidas.
- En test (200 frases, abierto una vez con todo fijado): macro-F1 **0,702** (es 0,698 · pt 0,673 · mix 0,693), cobertura 35,5 %, precisión 84,5 %, 79,2 % de `ambiguo` abstenidas. Supera a las reglas (0,538) y a la mayoritaria (0,055); queda empatado con embeddings (0,706). Gemini saca **1,000** con precisión de 99,2 %. La caída de val a test es el sesgo declarado: test es otra fuente, con estilo de LLM. Por el criterio, la elección no cambia después de ver el test.
- Ablaciones (test): el set híbrido (0,702) gana a solo Banking77 (0,399) y a solo suplemento (0,557), lo que valida D4.2. El ruido de chat no ayuda en este test (sin ruido 0,712).
**Limitaciones declaradas:** en test no se alcanza la precisión de 95 % que τ garantizaba en val; el modelo servido se reentrenó con train+val y τ viene del modelo entrenado solo con train; kappa pendiente; test generado con ChatGPT (D4.2). Todo en `model_card.md`, sección 11.
**Cómo validamos que fue correcta:** en la Fase 6, con los casos end-to-end (que no salen del set de la 4.1):
- **Resolución automática segura** (D1.6): ningún caso resuelto sin humano por una intención mal clasificada. Si el clasificador causa alguno, se revisa τ o el modelo.
- **Tasa de aclaraciones:** qué % de turnos termina en pregunta por confianza < τ y cuántos casos llegan a `max_clarifications` (2) y pasan a humano. Si es tan alta como sugiere el test (cobertura 35,5 %), se evalúa subir la cobertura con Gemini como segunda opinión bajo τ, con una decisión nueva.
- Se reportan también el macro-F1 del clasificador sobre las frases de esos casos, por idioma, y la comparación con el stub de reglas.

### D4.4 · Gemini en el flujo: extracción, redacción y verificador
**Fecha:** 29-sep-2026 · **Responsable:** rol B · **Estado:** Propuesta. Se completa en el Paso 12 de la guía 4.3 (`docs/Rol B - ML/guia_fase_4_3_gemini.md`) con los resultados de los Pasos 8 y 11.
**Contexto:** Gemini extrae datos del mensaje (monto, moneda, fechas, comercio, opción, confirmación) y redacta las respuestas en ES/PT. La intención la sigue decidiendo el clasificador (D4.3); Gemini opina solo cuando el clasificador se abstiene (D4.5). Si Gemini no está disponible, `understand` cae a reglas y `compose` a la plantilla (`integracion_backend.md` §1.1 y §1.6).
**Alternativas:** *(pendiente, Paso 12)* solo reglas; Gemini sin fallback; Gemini con fallback y verificador; Gemini también para la intención.
**Decisión:** *(pendiente, Paso 12)*
**Configuración de la llamada** (`backend/app/llm/gemini_client.py`, Paso 3), probada contra la API el 29-sep-2026:
- **Razonamiento:** `thinking_level=LOW`. Es el mínimo que acepta `gemini-3.8-flash`: `MINIMAL` da 400 ("Thinking level MINIMAL is not supported for this model"). La otra opción del SDK, `thinking_budget=0` (el parámetro de la familia 2.5), también se acepta. En una extracción de prueba, ambas dieron 0 tokens de razonamiento y 1,4 a 2,4 s por llamada. Se usa `thinking_level` porque es el parámetro propio de la familia 3. Como referencia, en la 4.2 el 3.5 sin este ajuste razonaba 150 a 300 tokens por frase (D1.12).
- **Timeout:** el cliente corta a los 8 s. El SDK le pasa el timeout también a la API (encabezado `X-Server-Timeout`), y la API rechaza menos de 10 s con un 400 ("Minimum allowed deadline is 10s"). Por eso a la API se le dice 10 s aparte. Sin esto, todas las llamadas fallaban y el bot caía siempre a reglas sin que se notara.
- **Reintentos:** hasta 2, con esperas de 0,5 s y 1,5 s, solo en errores transitorios: 503, 504, timeout o conexión, y 429 por minuto. El 429 por día y los demás 4xx no se reintentan. No se espera lo que pide un 429 por minuto (~60 s), porque el cliente está en el chat.
- **Temperatura 0**, y caché LRU en memoria (512 entradas), identificada por modelo, md5 del prompt, esquema y texto. Un acierto de caché cuenta tokens y costo en 0.
- **Costo por llamada** con los precios de D1.12 (los tokens de razonamiento se cobran como salida). Va a la traza como `LLMUsage`.
**Por qué:** *(pendiente, Paso 12: números de los Pasos 8 y 11)*
**Condiciones de uso de datos de la capa pagada:** *(pendiente, Paso 12, con fuente y fecha de consulta; roadmap 4.3.5)*
**Cómo validamos:** en la Fase 6: tasa de fallback, % de redacciones rechazadas por el verificador, latencia p95 y 0 afirmaciones no verificadas. Si el p95 queda cerca de los 8 s, se revisan el timeout y el nivel de razonamiento.

**Resultados del Paso 8** (30-sep-2026, `ml/llm/report.md`; el test de extracción se abrió una vez, con `extraccion_v1` y las reglas ya fijados):
- Extracción en test (55 frases): Gemini acierta todos los campos (55/55 frases sin error); reglas 49/55 (comercio 98,2 %, opción 98,2 %, confirmación 96,4 %, inyección 96,4 %). Fallback 0/55. Latencia p50 1,3 s · p95 2,3 s. USD 1,76 por 1.000 frases (~1.900 tokens de entrada por llamada).
- Inyección en test: Gemini 7/7, reglas 5/7; 0/48 falsos positivos con los dos (0/3 en las «falsas inyecciones»).
- Redacción: 125/126 aprobadas (99,2 %). El único rechazo es un falso rechazo del verificador («Escalated» después de «(» se toma como inicio de frase). Latencia p50 1,4 s · p95 3,6 s. USD 0,83 por 1.000.
- Hallazgos que el verificador deja pasar (no se corrigieron después de ver los resultados): supone el género del cliente («quédate tranquilo»), amplía el alcance («perda ou roubo»), promete una transferencia en vivo («te transfiero») o un contacto («nos comunicaremos contigo»). Además, dos problemas de las plantillas (rol C): los estados salen en inglés (Open/Escalated) y los montos con formato de EE. UU. también en ES y PT.

### D4.5 · Segunda opinión de Gemini sobre la intención, solo bajo τ
**Fecha:** 30-sep-2026 · **Responsable:** rol B (avisado a rol C) · **Estado:** Tomada
**Contexto:** con τ = 0,81, el clasificador contesta solo el 37,5 % del test (D4.3). La frase principal de la demo, «Ayer me cobraron USD 350 en Oxxo y no fui yo», sale con confianza 0,52: el bot pide aclaración y, si el cliente la repite, pasa a un humano (`max_clarifications` = 2). Eso baja la resolución automática segura (D1.6). D4.3 ya dejaba prevista esta salida («si la tasa de aclaraciones es alta, se evalúa Gemini como segunda opinión bajo τ»).
**Alternativas:**
- A. Bajar τ. En test, τ = 0,5 da cobertura 80 % pero precisión 77 %, y deja de abstenerse en 3 de cada 4 frases `ambiguo`. Además, sería elegir τ después de abrir el test.
- B. Calibrar las probabilidades (`CalibratedClassifierCV`) y volver a elegir τ. Cambia el modelo después del test y no garantiza que la frase de la demo pase τ.
- C. Gemini como clasificador principal. Mejor en test (macro-F1 1,000), pero toda frase depende de la red y cuesta ~2 s y USD 1,51 por 1.000.
- D. Cascada: el clasificador decide si su confianza es ≥ τ; si no, Gemini (`intent_zeroshot_v1`, el candidato ya evaluado en la 4.2) da una segunda opinión.
**Decisión:** D. `backend/app/nlu/intent_llm.py`, llamado desde `understand()` solo cuando el clasificador se abstiene, en paralelo con la extracción (no suma latencia a la extracción). Se acepta la intención de Gemini si es una de las 5 clases (no `ambiguo`) y su confianza es ≥ `intent.tau_gemini` = 0,80 (`config/policy.yaml`, política 1.3.0). Si no, o si Gemini falla, el turno sigue abstenido como hasta ahora. Gemini nunca cambia una intención que el clasificador ya aceptó. La frase se minimiza antes de enviarla. `model_version` agrega `+intent_zeroshot_v1` cuando decide Gemini, para que la traza muestre quién decidió.
**Por qué:** simulando la cascada con las predicciones guardadas de la 4.2 (clasificador reentrenado de D4.6 + Gemini):

| | val: cobertura | val: precisión | val: `ambiguo` abstenidas | test: cobertura | test: precisión | test: `ambiguo` abstenidas |
|:--|--:|--:|--:|--:|--:|--:|
| Clasificador solo (τ = 0,81) | 63,9 % | 95,4 % | 80,0 % | 37,5 % | 85,3 % | 79,2 % |
| Cascada (τ_g = 0,80) | 93,9 % | 90,1 % | 66,7 % | 92,0 % | 92,4 % | 66,7 % |

Gemini se llama en el 35 % de las frases de val y el 62 % de las de test. Con el Gemini real, la frase de Oxxo sale `cargo_no_reconocido` 0,98 y «Quiero un préstamo» sale `fuera_de_alcance` 1,00; «hola» y «Tengo un problema con mi tarjeta» siguen pidiendo aclaración (Gemini dice `ambiguo`).
**Cómo se eligió τ_g:** el criterio de D4.3 (precisión ≥ 95 % en val) no lo cumple ningún τ_g. Se usó el τ_g de mayor cobertura con precisión ≥ 90 % en val y, en el empate (0 a 0,80 dan lo mismo), el más alto. **Limitación declarada:** este criterio se escribió con los números de val y test a la vista (las dos corridas ya existían desde la 4.2), así que el test no es una medición limpia de la cascada. Los errores que agrega la cascada en val son sobre todo de frontera entre `cobro_incorrecto` y `fuera_de_alcance` (comisiones de cajero), donde la etiqueta de Banking77 es discutible, y 6 frases `ambiguo` más contestadas.
**Por qué el riesgo es aceptable:** equivocarse de intención es barato en este diseño. La intención no ejecuta nada: después vienen la búsqueda de la transacción (solo del cliente de la sesión), la política y la confirmación explícita con `confirmation_token`.
**Cómo validamos:** en la Fase 6, sobre los casos end-to-end: % de turnos que resuelve Gemini bajo τ, ningún caso resuelto sin humano por una intención mal puesta por Gemini, tasa de aclaraciones y de handoffs por `max_clarifications`, y latencia p95 del turno. Tests en `tests/test_nlu.py` (segunda opinión válida, `ambiguo`, bajo τ_g, fuera del esquema, errores, sin `tau_gemini`, minimización).

### D4.6 · Lote de fuera de alcance en el set de intenciones
**Fecha:** 30-sep-2026 · **Responsable:** rol B · **Estado:** Tomada
**Contexto:** el escenario obligatorio «Ambiguo o no soportado: "Quiero un préstamo" → se abstiene y explica qué sí puede hacer» (roadmap) salía como `estado_disputa` con confianza 0,48: el bot pedía «el monto, la fecha o el comercio del cargo». No había ninguna frase de préstamo en train ni en val. Lo detectó rol C revisando el flujo, no el test.
**Decisión:** 33 frases nuevas escritas por Claude (nunca con Gemini), en 11 familias (6 ES, 5 PT): préstamo, límite, saldo o pago mínimo, PIN, abrir cuenta o pedir tarjeta, inversiones o seguros. Están en `ml/intent/suplemento_fuera_alcance.csv`. No se incluyó la frase literal de la demo. Entran como lote 2 en `build_dataset.py`, divididas por familia con su propio generador aleatorio, **para que el split de las familias existentes no cambie** (verificado: ninguna frase existente cambia de split ni de texto). Resultado: 27 frases a train y 6 a val. El validador de fuga atrapó una frase idéntica a una del test («Esqueci a senha do cartão»), que se reemplazó.
**Resultados:** val (entrenado con train): macro-F1 0,906 (antes 0,908) y el criterio vuelve a dar τ = 0,81 (cobertura 63,9 %, precisión 95,4 %). Test (**segunda apertura**, con τ fijo): macro-F1 0,701 (antes 0,702), cobertura 37,5 %, precisión 85,3 % (antes 84,5 %). Modelo servido `tfidf_lr-C10-20260930-18569ee2`. «Quero um empréstimo» pasa a `fuera_de_alcance` 0,82 (sobre τ: responde qué sí puede hacer). «Quiero un préstamo» pasa a `fuera_de_alcance` 0,62 (bajo τ: sin Gemini pide aclaración; con D4.5 se resuelve).
**Limitación declarada:** el test de intención se abrió por segunda vez. El cambio no se motivó en el test, pero el test tiene 2 frases de préstamo, así que la mejora en test no es independiente. Runs: `ml/intent/runs/20260930-111809_tfidf_lr_val.json` y `20260930-111820_tfidf_lr_test.json`.
**Complemento (rol C):** el mensaje de aclaración también dirá qué sí puede hacer el bot, para que una abstención tenga sentido aunque no haya Gemini.

## Fase 5 · Frontend

*(pendiente)*

## Fase 6 · Evaluación

*(pendiente)*

## Fase 7 · Operación y deploy

*(pendiente)*

## Fase 8 · Entrega

*(pendiente)*
