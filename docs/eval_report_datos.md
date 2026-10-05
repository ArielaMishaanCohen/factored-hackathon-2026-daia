# Aporte de Datos al reporte de Fase 6

Estado al 1-oct-2026: implementación, validación dev y nueve ejecuciones finales
completadas. Resultados finales e impacto actualizado en [eval_corridas_finales.md](eval_corridas_finales.md).
Las secciones siguientes conservan la evidencia de desarrollo y el ejemplo
ilustrativo inicial. El [reporte conjunto final](eval_report.md) integra los resultados,
las alertas revisadas y las limitaciones. Los ejemplos de desarrollo de este anexo
no sustituyen los números finales.

## B0: contexto histórico, no es la misma carga

Fuente: `baseline_metrics` de `data/gold/gold.duckdb`, fecha de referencia
2026-06-17. Histórico de contactos y quejas: 2023-06-17 a 2026-06-17.

| Métrica | Valor | Evidencia |
|---|---:|---|
| FCR Queja | 43,60 % | 51.021 / 117.021 contactos |
| FCR global | 76,65 % | 526.030 / 686.296 contactos |
| Resolución media de disputas | 15,48 días | 87.041 días / 5.623 valores observados |
| Resolución mediana de disputas | 15 días | n = 5.623; no es un ratio |
| SLA incumplido de disputas | 20,16 % | 4.938 / 24.491 |
| Disputas abiertas o en proceso | 69,82 % | 17.099 / 24.491 |

No comparar directamente el FCR de todos los contactos con la resolución
automática del set estratificado. Tampoco interpretar duraciones nulas como cero.

## B1 y handoffs

B1 comparte política y orquestador con S; reemplaza intención por palabras clave
y usa extracción por reglas y respuestas por plantillas. Corrida local dev
`20261001T233946Z-B1-without_gemini-r1-dev`: 41 casos completados, sin errores del
runner ni max_turns. Auditoría: 53 spans NLU rules, modelos stub-keywords,
0 tokens, USD 0. Graders 1.1.0: resolución automática segura 15/38 (39,47 %),
completitud de handoff 14/14. El resultado final debe obtenerse sobre el mismo
held-out que S, no extrapolar estos números de desarrollo.

El grader contrasta hechos con gold y casos creados con `res.cases`; no trata
los casos operativos como si estuvieran en gold. Acepta fechas UTC equivalentes
(`Z` y `+00:00`). Fuentes no comprobables producen grader_error. No califica
semánticamente el texto libre del resumen ni reemplaza los graders de seguridad.

## Proyección offline, no medición en producción

Ejemplo ilustrativo solicitado: tasa central 35 %, mínimo 30 %, máximo 40 %.
Las 24.491 disputas en 1.097 días equivalen a 8.148,78/año al anualizar con 365
días. No se confunde el histórico de tres años con un volumen anual observado.
Duración media de Queja: 434,61 segundos sobre 100.727 valores no nulos de
117.021 contactos. Se supone un contacto ahorrado por disputa automatizada.

| Escenario ilustrativo | Disputas/año sin humano | Horas/año ahorradas |
|---|---:|---:|
| 30 % | 2.444,63 | 295,13 |
| 35 % | 2.852,07 | 344,31 |
| 40 % | 3.259,51 | 393,50 |

La mezcla real de disputas puede diferir del set. El rango no es un intervalo
de confianza. Las 17.099 abiertas/en proceso y las 4.938 con SLA incumplido
pueden solaparse: no se suman ni se afirma que estos casos se evitarían.
Recalcular con media y rango de las corridas finales y registrar sus IDs.

## Limitaciones para el reporte conjunto

- Cuatro casos held-out con transacciones demo de fraude/zona gris previamente
  expuestas, según la revisión de ML. Conservar el set congelado; separar sus
  métricas cruzando con `demo_scenarios.json` y declarar exposición.
- Student tiene n pequeña. Informar denominadores por segmento e idioma.
- Gold no tiene clientes de Brasil; portugués es idioma del guion, no país.
- Dataset sintético, ventana de reclamo y SLA sintéticos. No son política legal.
- B0 es contexto histórico; B1 sí comparte carga y política con S.
- Grader actualizado a 1.1.0: al integrar, recalificar las salidas guardadas con
  esa versión, preservando la identificación de primera corrida y corridas finales.

## Proveniencia de la muestra revisada

La muestra original revisada conserva
SHA-256 `965e2eba67c21032b2120318cf82a49d6a1ca37001d270b9f4d966a495630740`.
La copia actual de Git tiene SHA-256
`e4bca31710d2d356b94e89f16082a342e003bd7342e13516c7d05440e5c1d8f8`.
Comparando por case_id, las filas comunes cambian solo las tres consulta_gold
indicadas. Además, la muestra actual sustituye siete IDs y agrega la columna
tarjeta_bloqueada. Es otra versión de la muestra; el hash anterior sigue siendo
correcto para el archivo que se revisó. No se alteró ninguna de las dos copias.

## Reproducibilidad y comprobaciones

- Suite completa local sin Gemini: **425 pruebas aprobadas** (una advertencia
  de deprecación de Starlette). Incluye pruebas de datos, backend, ML y graders.
- Payload de la corrida de datos probado en un directorio temporal limpio:
  cinco archivos, **53.118 bytes**, sin manifest ni work.duckdb. Funcionan el
  descubrimiento de corrida, lectura de semillas y cálculo de B0/impacto desde
  los agregados. No se regeneró el set congelado.
- `.gitattributes` fija LF en `eval/cases/*.jsonl`. Windows había convertido
  esos archivos a CRLF, alterando el hash de bytes sin cambiar sus registros.
  Tras restituir LF, heldout coincide con el hash congelado del runner:
  `4560d282690ae4923bb4e627005c354dd45b74a25482a64758c92cb3366b7cd3`.
- Durante la implementación no se ejecutó una nueva corrida held-out ni se modificó backend/ML.
  El generador descubre la corrida por sus semillas y el grader de handoff recibe
  el contexto de los casos operativos.
