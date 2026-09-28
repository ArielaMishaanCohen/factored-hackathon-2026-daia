# Decisiones · Fase 0

**Fecha:** 27 de septiembre de 2026
**Evidencia:** `analysis/01_exploracion.ipynb` (las secciones citadas entre paréntesis son de ese notebook)

---

## 1. Decisión: construir el flujo de **Disputas de transacciones**

**Puntaje en la matriz: 38 de 45.** Segunda opción: Soporte de tarjetas (33). Crédito queda vetado.

El sistema recibe un reclamo por un cargo ("no reconozco este cobro", "me cobraron dos veces"), encuentra la transacción, aplica la política y crea el caso con confirmación del cliente, o escala a un humano (fraude, monto alto) con un handoff estructurado.

Lo elegimos porque es **el problema donde el banco está peor hoy** y porque **es el flujo cuyas herramientas mejor se sostienen con los datos**. Los datos son sintéticos: la mayoría de las columnas no tiene relación con las demás, pero `transactions` y `fraud_score` sí son coherentes, y son justo lo que usa este flujo.

---

## 2. Los 3 números que más pesaron

| # | Número | Qué dice | Sección |
| :-: | :-- | :-- | :-: |
| 1 | **FCR 43,6 %** en contactos por Queja (promedio: 76,6 %) | Es el peor motivo del banco: menos de la mitad se resuelve en el primer contacto. También tiene el peor CSAT (3,00 de 5), 63 % de seguimiento (vs. 34,8 %) y un AHT de 7,2 min (vs. 4,9). | 4 |
| 2 | **36,5 %** de las quejas formales son "Cargo no reconocido" (18,3 %) o "Cobro indebido" (18,2 %) | Las disputas de dinero son las dos subcategorías más grandes de quejas. El 20 % de todas las quejas incumple el SLA y tarda una mediana de 16 días. | 3 y 4 |
| 3 | **AUC 0,84** de `fraud_score` para detectar fraude | Es la única señal estructurada coherente del dataset. Ninguna transacción legítima pasa de 30; la mediana del fraude es 49. Sirve para decidir cuándo escalar. | 5a |

---

## 3. Matriz de decisión

Escala: 1 = débil, 2 = aceptable, 3 = fuerte. Total = Σ (peso × puntaje), máximo 45.

| # | Criterio | Peso | Disputas | Tarjetas | Cuenta y pagos | Crédito |
| :-: | :-- | :-: | :-: | :-: | :-: | :-: |
| 1 | Volumen de demanda | 2 | 3 | 2 | 3 | 1 |
| 2 | Dolor operativo | 2 | 3 | 2 | 1 | 3 |
| 3 | Soporte de los datos (**veto**) | 3 | 2 | 2 | 2 | **1** |
| 4 | Cobertura de escenarios obligatorios | 3 | 3 | 3 | 1 | 2 |
| 5 | Viabilidad del componente de ML | 2 | 2 | 1 | 1 | 1 |
| 6 | Factibilidad en 5 días | 2 | 2 | 3 | 3 | 1 |
| 7 | Historia de negocio | 1 | 3 | 2 | 2 | 1 |
| | **Total** | | **38** | **33** | **27** | 22 (vetada) |

### Justificación de cada puntaje

**1 · Volumen**
- *Disputas 3:* Queja está en el top 3 de contactos (17,1 %, 117k) y "Cargo no reconocido" + "Cobro indebido" son las dos subcategorías más grandes de quejas (36,5 %).
- *Tarjetas 2:* no existe un motivo de contacto "tarjetas" (solo hay 6 categorías genéricas), así que su volumen no se puede medir. Las tarjetas son el 35 % de los productos afectados en quejas.
- *Cuenta y pagos 3:* Transaccional es el motivo #1 (35,0 %).
- *Crédito 1:* lo más cercano es Comercial, con 8 %.

**2 · Dolor** (peor que el promedio en FCR, escalamiento, seguimiento o AHT)
- *Disputas 3:* Queja es peor en 3 de 4 indicadores, tiene el CSAT más bajo (3,00) y el 20 % de las quejas incumple el SLA.
- *Tarjetas 2:* no se puede aislar. Le damos el valor medio.
- *Cuenta y pagos 1:* Transaccional es el motivo que **mejor** funciona (FCR 91,5 %, AHT 3,4 min, 0 % de sentimiento negativo).
- *Crédito 3:* Comercial es peor en 3 de 4 (FCR 65,2 %, AHT 9,0 min).
- El escalamiento (10 %) y la espera (2 min) son iguales en todos los motivos, así que no discriminan.

**3 · Soporte de los datos**
- *Disputas 2:* `transactions` tiene cliente, producto, monto y moneda, fecha, canal, estado (hay `Reversed` y `Pending`), comercio (23 % de las filas), país y fraude. **Supuesto:** las quejas no se pueden emparejar con transacciones (0 % de coincidencias con cliente + producto + moneda + monto, y `origin_interaction_id` está 100 % vacío). Por eso la política y los casos de prueba se construyen desde `transactions`, y `complaints` sirve como plantilla del caso (tipo, categoría, prioridad, SLA) y como línea base.
- *Tarjetas 2:* `product_status` sí es coherente (las tarjetas bloqueadas, suspendidas o cerradas tienen 0 transacciones). Pero los `response_code` de rechazo se reparten ~25 % cada uno, sin relación con el cupo (el 51, "fondos insuficientes", excede el cupo igual que el resto: ~2 %) ni con el vencimiento (el 54, "tarjeta vencida", no se asocia a tarjetas vencidas). "Explicar un rechazo" sería traducir un código, no diagnosticarlo.
- *Cuenta y pagos 2:* el saldo no tiene nulos y hay pagos `Pending`, pero `last_transaction_date` coincide con la última transacción real solo en el 0,1 % de los productos.
- *Crédito 1 (veto):* `credit_score` **no predice la mora**. Spearman = −0,006, y la mora > 30 días es ~14 % en los 10 deciles (14,9 % en el más bajo, 13,8 % en el más alto). Un modelo de riesgo sería ruido, y no hay solicitudes de crédito.

**4 · Cobertura** (a priori, confirmado con datos)
- *Disputas 3:* los escenarios obligatorios salen solos. Si el cliente no da el monto, el **44 % de los casos tiene 2 o más transacciones candidatas** en 60 días, y ahí aparece la aclaración. Crear el caso requiere confirmación. El fraude y los montos altos se escalan.
- *Tarjetas 3:* bloqueo con confirmación y desbloqueo con escalamiento.
- *Cuenta y pagos 1:* casi solo lectura.
- *Crédito 2.*

**5 · ML**
- En ninguna opción hay un modelo propio que le gane a su baseline con los datos del banco. El texto del cliente predice el motivo **peor que el azar** (macro-F1 0,124 vs. 0,161), el escalamiento tiene AUC 0,50 y el fraude sin `fraud_score` tiene AUC 0,50.
- *Disputas 2:* es la única opción con una señal real (`fraud_score`, AUC 0,84), útil para calibrar el umbral de escalamiento. Además, el router de intenciones (ver sección 5) tiene intenciones más ricas aquí: cargo no reconocido, cobro duplicado, fraude, fuera de alcance.
- *Resto 1:* no hay señal.

**6 · Factibilidad** (a priori, sin cambios)
- *Disputas 2:* tiene más piezas (búsqueda, política, caso, escalamiento).
- *Tarjetas y Cuenta 3.*
- *Crédito 1:* guardrails de crédito.

**7 · Negocio**
- *Disputas 3:* el impacto se estima con datos: 117k contactos con FCR 43,6 % y 63 % de seguimiento, 20 % de SLA incumplido y una compensación mediana de ~USD 252 (en el 6,9 % de las quejas).
- *Tarjetas y Cuenta 2:* requieren supuestos.
- *Crédito 1.*

### ¿Qué tan sólida es la decisión?

- Si Disputas bajara a 1 en ML (es decir, si no contáramos `fraud_score`), quedaría en **36 vs. 33**: sigue ganando por más de 2 puntos, que es el margen de empate de la regla 3.
- Si Tarjetas subiera a 3 en dolor, quedaría en 35: Disputas sigue arriba.
- Hacen falta dos cambios a la vez en contra de Disputas para que la decisión se invierta.

---

## 4. Qué se descartó y por qué

- **Soporte de tarjetas (33):** es la segunda opción. Las acciones de bloqueo tienen datos coherentes, pero los `response_code` son aleatorios, no hay un motivo de contacto medible y ataca un dolor que no se puede demostrar. Si aparece un bloqueo técnico real con Disputas, pasamos a esta opción sin reabrir la discusión.
- **Consultas de cuenta y pagos (27):** tiene el mayor volumen, pero es el motivo que **ya funciona mejor** (FCR 91,5 %) y casi no tiene acciones. Parecería "un chatbot", justo lo que el kickoff pidió evitar.
- **Crédito (22, vetada):** `credit_score` no predice la mora (Spearman −0,006, mora plana por decil). Cualquier evaluación de riesgo o elegibilidad sería inventada.

---

## 5. Componente de ML

El EDA descarta entrenar con los textos del banco. Hay **42 `customer_text` distintos en 171k transcripts**; todos piden el saldo y se reparten igual entre los 6 motivos. Las descripciones de las quejas son 5 plantillas que repiten la categoría ("Queja relacionada con fees"), así que su F1 = 1,0 es fuga de etiqueta.

Lo que sí es viable:

1. **Router de intención con abstención.** Clasifica el mensaje del cliente en {cargo no reconocido, cobro duplicado/indebido, sospecha de fraude, fuera de alcance, ambiguo}. Se entrena o evalúa contra un **set etiquetado propio en español y portugués** (generado y revisado por el equipo), con un baseline explícito (TF-IDF o reglas) para comparar. La abstención cubre el escenario "solicitud no soportada".
2. **Umbral de escalamiento por fraude**, calibrado con `is_fraud` y `fraud_score` (AUC 0,84). La regla inicial queda para el roadmap 2: el máximo de las legítimas es 30, y el 20 % de nulos se trata como riesgo medio.

---

## 6. Problemas de calidad y tratamiento

Detalle en la tabla del chunk 2.8 del notebook. Los que afectan a Disputas:

| Problema | Afectado | Tratamiento |
| :-- | :-- | :-- |
| Timestamps en UTC y particiones en hora local: fecha del evento = partición + 1 día; 1352 transacciones "futuras" del 18-jun entre 00:00 y 05:59 | 25 % de transactions, 33 % de interactions y complaints | Normalizar la zona horaria; usar la partición/`process_date` como fecha de negocio |
| Quejas no enlazables con transacciones ni con llamadas (`origin_interaction_id` vacío) | 100 % | No inventar la relación; los casos de prueba salen de `transactions` |
| `fraud_score` nulo | 20 % | Regla conservadora (riesgo medio → pedir más verificación) |
| `response_code` aleatorio entre rechazos, 5 % nulo | 100 % de los rechazos | Solo traducir el código a texto; nunca afirmar la causa |
| `last_transaction_date` incoherente | 99,9 % | Recalcular desde `transactions` |
| `expiration_date` anterior a la transacción | 44 % de las compras con tarjeta | No usar en reglas |
| `subcategory` nula en quejas | 10 % | "Sin subcategoría" |
| Nulos en `closing_date`, `compensation_granted` y `resolution_satisfaction` | 93–96 % | Significan "no aplica" (caso abierto o sin compensación); no imputar |

Lo que está bien: 0 duplicados, 0 huérfanos en las 9 relaciones con datos, rangos numéricos válidos y un esquema estable durante los 3 años.

---

## 7. Idioma

**No hay portugués en los datos:** `detected_language` = `es` en el 100 % de los 171k transcripts. Se reporta como limitación. Las interacciones en portugués de la demo y de la evaluación saldrán de nuestro set propio (sección 5), y el sistema debe responder en el idioma del cliente. En la base de agentes hay 129 con portugués (68 + 61), un dato útil para el handoff.

---

## 8. Siguientes pasos (roadmap 2)

1. Definir la política de disputas: umbrales de monto por tipo de transacción (p. ej., p90 de compras = USD 450; transferencias hasta USD 10k), ventana de reclamo, qué se revierte, qué se escala.
2. Diseñar las herramientas sobre `transactions` (buscar candidatas, ver detalle, crear caso con el esquema de `complaints`, escalar con handoff).
3. Construir el set de evaluación en español y portugués (normal, ambiguo, fuera de alcance, fraude/escalamiento).
4. Pipeline: normalización de zona horaria y recálculo de `last_transaction_date`.
