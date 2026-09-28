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
| D2.x | Pipeline: duplicados, `amount_usd`, zona horaria, reproceso, umbrales | 2 | Pendiente |
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
**Decisión:** Gemini (modelo exacto por fijar: un modelo "Flash" o "Flash-Lite" vigente; anotar el ID y el precio al día de medir).
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

---

## Fase 2 · Pipeline de datos

*(pendiente)*

## Fase 3 · Núcleo determinista

*(pendiente)*

## Fase 4 · Capa de IA y ML

*(pendiente)*

## Fase 5 · Frontend

*(pendiente)*

## Fase 6 · Evaluación

*(pendiente)*

## Fase 7 · Operación y deploy

*(pendiente)*

## Fase 8 · Entrega

*(pendiente)*
