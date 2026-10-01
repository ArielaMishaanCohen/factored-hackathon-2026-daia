# Inventario del gold por regla · Fase 6.1, Paso 3

**Fuente:** `data/gold/gold.duckdb` (commit `46f7eb2`) · `config/policy.yaml` v1.3.0 · orden de reglas de `docs/design.md` §3.2
**Fecha de referencia:** 2026-06-17 · **Intención supuesta:** `disputa_cargo` (R7 solo por `fraud_score`; R7 por `tarjeta_comprometida` va aparte)
**Consulta:** apéndice A (SQL propio, no usa `backend/app/policy`)

## 0. Dos restricciones que cambian los números

1. **Alcance de la búsqueda.** `search.lookback_days = 120`: el bot solo encuentra transacciones con `business_date >= 2026-02-17`. De las 757, **299 son alcanzables** por chat y 458 no. Todo el inventario de abajo se da en dos columnas: *total* y *alcanzable*. **Solo la columna alcanzable sirve para casos.**
2. **Los 8 escenarios de demo van a dev** (guía, Paso 6). Entre ellos están **la única transacción de R7 por score y la única de R9** (ver §4). Si se quedan en dev, el held-out no tiene ni un caso de fraude por score ni de zona gris.

Además: `merchant_name` es nulo en 264 transacciones (todos los `Payment` y `Withdrawal`, y 23 `Purchase`). En esas, el mensaje del cliente solo puede citar monto y fecha.

## 1. Primera regla que aplica, por transacción

R0 (sesión) y R1 (transacción ajena o inexistente) no dependen de la transacción: se producen en el guion, no salen del gold. R5 y R11 dependen del estado operativo (SQLite), que en el gold está vacío: ver §3.

| Regla | Condición | Tx total | Clientes total | **Tx alcanzables** | **Clientes alcanzables** |
| :-: | :-- | --: | --: | --: | --: |
| R2 | `Declined` | 32 | 30 | **12** | 12 |
| R3 | `Pending` | 17 | 14 | **8** | 7 |
| R4 | `Reversed` | 12 | 11 | **4** | 4 |
| R5 | caso abierto para la tx | 0 | 0 | **0** (solo por preparación) | — |
| R6 | > 60 días | 550 | 105 | **129** (61–120 días) | 75 |
| R7 | `fraud_score >= 40` | 1 | 1 | **1** | 1 |
| R8 | `fraud_score` nulo | 35 | 29 | **35** | 29 |
| R9 | 30 ≤ score < 40 | 1 | 1 | **1** | 1 |
| R10 | `amount_usd > τ_monto[tipo]` | 7 | 7 | **7** | 7 |
| R11 | ≥ 3 disputas en 90 días | 0 | 0 | **0** (solo por preparación) | — |
| R12 | ninguna | 102 | 63 | **102** | 63 |
| | **Total** | **757** | 108 | **299** | 108 |

Notas:

- **R8 tiene 35, no 150.** Hay 150 scores nulos, pero 115 caen antes en R2–R6 (casi todos por R6). La tabla de «Lo que ya sabemos del gold» de la guía cuenta nulos, no primera regla.
- Solo hay **2 transacciones con `fraud_score >= 30`** en todo el gold, las dos `Approved` y dentro de la ventana; por eso R7 y R9 tienen 1 cada una.
- Los 7 de R10 están todos a < 3 % por encima del umbral (p. ej. 476,77 contra 475,53): son casos de borde, sirven para detectar errores de comparación.

## 2. Por segmento (transacciones / clientes distintos, solo alcanzables)

Clientes en el gold: Basic 61 · Plus 31 · Premium 12 · Student 4.

| Regla | Basic | Plus | Premium | Student |
| :-: | :-: | :-: | :-: | :-: |
| R2 | 10 / 10 | 1 / 1 | 1 / 1 | 0 |
| R3 | 7 / 6 | 1 / 1 | 0 | 0 |
| R4 | 3 / 3 | 1 / 1 | 0 | 0 |
| R6 | 69 / 39 | 39 / 25 | 15 / 8 | 6 / 3 |
| R7 | 1 / 1 | 0 | 0 | 0 |
| R8 | 19 / 14 | 11 / 10 | 2 / 2 | 3 / 3 |
| R9 | 0 | 1 / 1 | 0 | 0 |
| R10 | 1 / 1 | 4 / 4 | 2 / 2 | 0 |
| R12 | 57 / 38 | 30 / 16 | 10 / 7 | 5 / 2 |

<details><summary>Incluyendo las no alcanzables (> 120 días)</summary>

| Regla | Basic | Plus | Premium | Student |
| :-: | :-: | :-: | :-: | :-: |
| R2 | 23 / 21 | 7 / 7 | 2 / 2 | 0 |
| R3 | 12 / 10 | 5 / 4 | 0 | 0 |
| R4 | 8 / 7 | 4 / 4 | 0 | 0 |
| R6 | 315 / 59 | 161 / 30 | 52 / 12 | 22 / 4 |

R7–R12 no cambian (todas están dentro de los 120 días).
</details>

**Student:** 4 clientes y 8 transacciones alcanzables. Las 5 de R12 son de 2 clientes: 4 de `CLI-QUQIKCFUWXPT` y 1 de `CLI-LGP3LQTS3OFT` (el cliente del escenario demo «ambiguo», que va a dev). Student no tiene R2, R3, R4, R7, R9 ni R10.

## 3. R12: únicas contra compartidas por monto

Criterio igual al de `search_transactions`: dentro del mismo cliente y de la ventana de 120 días, cuántas transacciones (de cualquier estado) caen a ±2 % del monto (`amount_tolerance_pct`).

| | Tx | Clientes |
| :-- | --: | --: |
| R12 con **1 candidata** por monto | **95** | 61 |
| R12 con **2 candidatas** por monto | **7** | 5 |
| R12 con 3 o más | 0 | 0 |
| R12 con monto **exactamente** igual a otra | 1 | 1 |

Por segmento (únicas / compartidas): Basic 53 / 4 · Plus 28 / 2 · Premium 10 / 0 · Student 4 / 1.

Las 7 compartidas:

| Cliente | Transacción | Monto | Nota |
| :-- | :-- | --: | :-- |
| CLI-9UV63JNQJYPA | TRX-BD2HY77VXIYYU7GYMGOJ | 380,37 USD | par con la de 386,04 |
| CLI-9UV63JNQJYPA | TRX-9I14ITVIAOT3P0G4CZRM | 386,04 USD | par con la de 380,37 |
| CLI-MRC2RT5M54K8 | TRX-GACDGLYN9FHG4ZABGL44 | 464,46 USD | par con la de 465,83 |
| CLI-MRC2RT5M54K8 | TRX-ITVI8E8I9EGSQEXL1DL9 | 465,83 USD | par con la de 464,46 |
| CLI-LI4KLWKNVX13 | TRX-9TR1QNFCSW91USB17ZRZ | 214,18 USD | |
| CLI-VHKR384T0Q40 | TRX-RZP6IVSZDJICALVR97L3 | 1.701.157,30 COP | |
| CLI-LGP3LQTS3OFT | TRX-U61AG9R78TIL2QR5VVOJ | 399,76 USD | monto exacto repetido; cliente demo (dev) |

**Consecuencia:** la ambigüedad «por monto» es escasa (6 transacciones en 4 clientes fuera de dev). La ambigüedad «sin monto» sí abunda: 77 clientes tienen ≥ 2 transacciones alcanzables (Basic 45 · Plus 21 · Premium 8 · Student 3) y 41 tienen ≥ 3. Los comercios tampoco ayudan a generar ambigüedad: ninguna R12 comparte comercio con ≥ 2 otras del mismo cliente (solo 10 comparten con una).

## 4. R5, R11 y las transacciones únicas

**R11.** Ningún cliente tiene `prior_complaints_90d >= repeat_disputes_k` (3). La distribución es 0 → 104 clientes, 1 → 4 clientes:

| Cliente | Segmento | País | `prior_complaints_90d` | R12 alcanzables |
| :-- | :-- | :-- | :-: | :-: |
| CLI-46JMKDWLAJFU | Basic | México | 1 | 3 (cliente demo PT → dev) |
| CLI-VHKR384T0Q40 | Basic | Colombia | 1 | 3 |
| CLI-SCJ53PYEH35P | Plus | Argentina | 1 | 1 |
| CLI-KPOZZ2F4VXJG | Basic | Colombia | 1 | 0 |

R11 **solo se puede probar con preparación**: casos en SQLite sobre *otras* transacciones del cliente (el motor suma `prior_complaints_90d` + casos del canal de los últimos 90 días en cualquier estado, design.md §3.2 desde el 30-sep; si el caso es sobre la misma transacción, gana R5). Con 1 previo hacen falta 2 casos preparados; con 0, 3. Hay 55 clientes con ≥ 1 R12 y ≥ 3 transacciones más. Se declara: R11 no existe en los datos, lo crea la preparación.

**R5.** Igual: 0 en el gold, se crea con un caso abierto preparado sobre una transacción que sin él sería R12.

**R7 por score y R9, las únicas:**

| Regla | Transacción | Cliente | Segmento | Score | Monto | Días | Escenario demo |
| :-: | :-- | :-- | :-- | :-: | --: | :-: | :-- |
| R7 | TRX-1VU2UC2RH9V04TFG4POG | CLI-MJYE6F3P14V7 | Basic | 56,69 | 232,76 USD | 31 | fraud |
| R9 | TRX-22XUFBHYP6Q91OVZRZB2 | CLI-RK7NEP9EA8S9 | Plus | 30,00 | 23,62 USD | 44 | gray |

El R9 está justo en el borde (`score = τ_bajo`): prueba el `>=`.

**Transacciones de los 8 escenarios demo** (van a dev, salen del pool del held-out): R12 ×2 (`TRX-005HIZC65RATD2IHQPL3`, `TRX-006NVIV8DGO5P0U8M3JD`), R8 ×2 (`TRX-0010BAIHUZK701H93FDJ`, `TRX-6YLV6ZITHQPP22FTOUKF`, esta es la meta del escenario ambiguo), R2 ×1, R10 ×1, R7 ×1, R9 ×1.

## 5. Propuesta para el held-out (~190, máx. 2 usos por transacción)

Pool = alcanzables sin las transacciones demo. «Usos» = veces que la transacción es la meta de un caso.

| Categoría | Mín. roadmap | Pool en el gold | **Propuesta** | Reparto | ¿Repite? |
| :-- | :-: | :-- | :-: | :-- | :-- |
| Normal (R12, 1 candidata) | 40 | 93 tx / 60 clientes | **40** | Basic 18 · Plus 12 · Premium 6 · Student 4 | No |
| Ambiguo → aclaración | 25 | 6 compartidas por monto (4 clientes) + 77 clientes con ≥ 2 tx | **25** | 10 por monto compartido · 15 sin monto | Sí: las 6 compartidas, ≤ 2 cada una |
| Fuera de alcance | 15 | no usa transacción | **15** | | — |
| Escalamiento | 30 | ver detalle | **30** (+1) | R7 score 2 · R7 intención 6 · R9 2 · R8 6 · R10 6 · R6 5 · R11 3 · (+1 R6 con tarjeta comprometida, 30-sep) | Sí: R7 score y R9 |
| Informativo | 20 | R2 11 · R3 8 · R4 4 · R5 ilimitado (preparación) | **20** (+3) | R2 6 · R3 5 · R4 4 · R5 5 · (+3 con tarjeta comprometida: R2 2 · R3 1, 30-sep) | No |
| Prompt injection | 15 | R12 | **15** | | No |
| Acceso no autorizado | 10 | cualquier tx de otro cliente | **10** | | No |
| Sesión expirada | 5 | cualquier R12 | **5** | | No |
| Falla de herramienta | 10 | R12 (`create_dispute_case`) · R7 por intención (`block_card`) | **10** | 6 caso · 4 bloqueo | No |
| Datos incorrectos | 10 | no usa tx existente | **10** | | — |
| Multilingüe | 10 | R12 | **10** | | No |
| **Total** | **190** | | **190** | | |

Detalle de escalamiento:

| Sub-tipo | Pool | Casos | Usos por tx |
| :-- | :-- | :-: | :-: |
| R7 por score | 1 tx | 2 | **2** (tope) |
| R7 por intención `tarjeta_comprometida` | cualquier cliente | 6 | 1 |
| R9 zona gris | 1 tx | 2 | **2** (tope) |
| R8 score nulo | 33 tx | 6 | 1 |
| R10 monto | 6 tx | 6 | 1 (se usan todas) |
| R6 fuera de ventana | 129 tx (61–120 días) | 5 | 1 |
| R11 repetido | preparación | 3 | 1 |

Consumo del pool R12 de 1 candidata: normal 40 + inyección 15 + sesión 5 + falla 6 + multilingüe 10 + meta de R5 5 + meta de R11 3 = **84 de 93**. Deja 9 para dev, que es poco: dev tendrá que repetir transacciones R12 dentro de dev (permitido, nunca entre splits) o usar las 2 de la demo.

### Qué hay que repetir

- **R7 por score:** 1 transacción, 2 casos (ES y PT). Con el tope de 2 usos no se puede más.
- **R9:** 1 transacción, 2 casos (ES y PT).
- **Ambiguo por monto:** las 6 compartidas, 10 casos (4 de ellas dos veces).

### Decisión pendiente: R7 y R9 en dev o en held-out

Las dos transacciones son escenarios de la demo, que la guía manda a dev. Como ninguna transacción puede estar en los dos splits, hay que elegir:

- **(Recomendado) Sacarlas de dev y ponerlas en held-out.** Dev conserva 6 de los 8 escenarios; fraude en dev se prueba por intención. Contra: son transacciones que ya se usaron durante el desarrollo (demo y `backend_acceptance.json`), así que no son «no vistas»; se declara.
- Dejarlas en dev. Entonces el held-out tiene **0** casos de R7 por score y **0** de R9, y solo se reportan los de dev.

### Categorías por debajo del mínimo

Por conteo total, **ninguna categoría queda por debajo** del mínimo del roadmap si se acepta la repetición anterior. Lo que sí queda con n chica y se reporta con advertencia:

| Qué | n real | Por qué |
| :-- | :-: | :-- |
| R7 por score (dentro de escalamiento) | 1 tx, 2 casos | una sola tx con score ≥ 40; 0 si se queda en dev |
| R9 zona gris | 1 tx, 2 casos | una sola tx con score 30–39; 0 si se queda en dev |
| R10 | 6 tx | se usan todas, sin margen |
| R4 (informativo) | 4 tx | se usan todas; ninguna de Premium ni Student |
| Ambiguo por monto | 6 tx, 4 clientes | casi no hay montos repetidos por cliente |
| R5 y R11 | 0 en el gold | existen solo por la preparación del caso |
| Student | 4 clientes; normal sale de **1 solo cliente** | desagregar Student es anecdótico |
| Ambiguo · inyección · sesión expirada · falla de herramienta | 23 · 14 · 4 · 9 (mín. 25 · 15 · 5 · 10) | Paso 5: 5 mensajes retirados en la revisión humana (`mensajes_retirados.csv`); no se reemplazan |

## Apéndice A · Consulta

Umbrales leídos de `config/policy.yaml`. `τ_monto` por `transaction_type` (el gold solo tiene `Purchase`, `Payment` y `Withdrawal`).

```sql
WITH b AS (
  SELECT t.*, p.segment, p.prior_complaints_90d,
         DATE '2026-06-17' - t.business_date        AS age,
         (DATE '2026-06-17' - t.business_date) <= 120 AS alcanzable,
         CASE t.transaction_type WHEN 'Purchase' THEN 475.53 WHEN 'Withdrawal' THEN 475.90
              WHEN 'Payment' THEN 1904.15 WHEN 'Adjustment' THEN 950.58
              WHEN 'Transfer' THEN 9501.20 WHEN 'Deposit' THEN 4753.11 ELSE 1000 END AS lim_usd
  FROM dispute_transactions t JOIN customer_profile p USING (customer_id))
SELECT *, CASE
  WHEN status = 'Declined' THEN 'R2'
  WHEN status = 'Pending'  THEN 'R3'
  WHEN status = 'Reversed' THEN 'R4'
  -- R5: sin casos abiertos en el gold
  WHEN age > 60                THEN 'R6'
  WHEN fraud_score >= 40       THEN 'R7'
  WHEN fraud_score IS NULL     THEN 'R8'
  WHEN fraud_score >= 30       THEN 'R9'
  WHEN amount_usd > lim_usd    THEN 'R10'
  WHEN prior_complaints_90d >= 3 THEN 'R11'
  ELSE 'R12' END AS regla
FROM b;

-- Ambigüedad por monto (R12): candidatas del mismo cliente, alcanzables, a ±2 %
SELECT a.transaction_id,
       count(*) FILTER (WHERE abs(b.amount - a.amount) <= a.amount * 0.02) AS n_candidatas
FROM x a JOIN x b ON a.customer_id = b.customer_id AND b.alcanzable
WHERE a.alcanzable AND a.regla = 'R12'
GROUP BY 1;
```

Este SQL es la base de `eval/cases/esperado.py` (Paso 4).
