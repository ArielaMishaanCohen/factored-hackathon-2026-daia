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
| D1.11 | Modelo de Gemini fijado: `gemini-3.5-flash` | 1 | Tomada |
| D2.x | Pipeline: duplicados, `amount_usd`, zona horaria, reproceso, umbrales | 2 | Pendiente |
| D4.1 | Set de intenciones generado por el equipo | 4 | Reemplazada por D4.2 |
| D4.2 | Set de intenciones híbrido: Banking77 + suplemento + test aparte | 4 | Tomada |
| D4.x | Clasificador elegido y umbral de abstención | 4 | Pendiente |
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
**Fecha:** 29-sep-2026 · **Responsable:** equipo · **Estado:** Tomada
**Contexto:** D1.2 dejó el ID del modelo por fijar. Hay que fijarlo antes del Paso 7 de la Fase 4.2 (Gemini zero-shot como candidato de clasificador), porque su F1, latencia y costo dependen del modelo exacto. Es el mismo modelo que usa el bot para extraer y redactar. Se configura con `GEMINI_MODEL` en `.env` y en Render.
**Alternativas:**
- A. `gemini-3.8-flash`: el Flash más nuevo disponible para nuestra API key y más barato hoy (ver precios). El 29-sep dio 503 `UNAVAILABLE` ("high demand") en 3 de 4 llamadas, y la única que respondió tardó 11,3 s.
- B. `gemini-3.5-flash`: respondió al primer intento en 1,6 s en la misma prueba.
**Decisión:** B, `gemini-3.5-flash`.
**Por qué:** D1.2 se valida con latencia p95 y tasa de fallback por errores de la API; un modelo saturado empeora justo esas métricas y es un riesgo para la demo del viernes 2. Las tareas del LLM (extraer en JSON y redactar en ES/PT, y el candidato de referencia en 4.2) no deberían necesitar el modelo más nuevo; el Paso 7 lo mide.
**Precio al 29-sep-2026** (ai.google.dev/gemini-api/docs/pricing, capa pagada, por 1M de tokens): `gemini-3.5-flash` USD 1,50 entrada y USD 9,00 salida. Como referencia, `gemini-3.8-flash` cuesta USD 0,75 y USD 3,75 hasta el 31-dic-2026 (USD 1,50 y USD 7,50 desde el 1-ene-2027). Ambos tienen capa gratuita. **Costo aceptado:** el 3.5 cuesta ~2× en entrada y ~2,4× en salida; con los volúmenes del hackathon la diferencia es marginal frente a la estabilidad.
**Cómo validamos:** en el Paso 7 de la 4.2 y en la Fase 6, latencia p95 y tasa de errores de la API con `gemini-3.5-flash`. Si el 3.8 se estabiliza, cambiarlo exige volver a correr el candidato Gemini de la 4.2 y registrarlo como decisión nueva que reemplace a esta.

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

## Fase 5 · Frontend

*(pendiente)*

## Fase 6 · Evaluación

*(pendiente)*

## Fase 7 · Operación y deploy

*(pendiente)*

## Fase 8 · Entrega

*(pendiente)*
