# Documentación de la entrega · DAIA

El [README principal](../README.md) presenta el problema, la demo, el video, la presentación y las instrucciones de ejecución. Este índice organiza la evidencia de la entrega sin exigir leer los registros de trabajo en orden cronológico.

## Lectura principal

| Pregunta | Evidencia |
|---|---|
| ¿Por qué este problema? | [Justificación y alternativas](decisions_fase_0.md), [EDA](NOTAS_DATOS.md) |
| ¿Qué hace y cómo se controla? | [Arquitectura y contratos](design.md), [política vigente](../config/policy.yaml) |
| ¿Cómo se prepararon y validaron los datos? | [Contratos de datos](data_contracts.md), notebooks [EDA](../analysis/01_exploracion.ipynb) y [calibración](../analysis/02_politica.ipynb) |
| ¿Por qué se eligió el modelo? | [Model card](../ml/intent/model_card.md), [criterio de selección](../ml/intent/criterio_seleccion.md) |
| ¿Qué aporta Gemini? | [Evaluación de extracción y redacción](../ml/llm/report.md), [pruebas de inyección](../ml/llm/inyeccion.md) |
| ¿Cómo se midió el sistema completo? | [Reporte final](eval_report.md), [corridas finales](eval_corridas_finales.md), [análisis de errores](eval_analisis_errores.md) |
| ¿Qué significa la proyección de impacto? | [B0, denominadores y supuestos](eval_report_datos.md), reporte final §8 |
| ¿Cómo se opera y qué falta para producción? | [Operación](operations.md) |

## Evidencia de las corridas

[fase6_corridas_finales.zip](evidence/fase6_corridas_finales.zip) contiene 46 archivos: los manifiestos, resultados, calificaciones y métricas de las nueve corridas, tres auditorías B1, resumen agregado, B0, proyección de impacto y snapshot de hashes. Incluye también copias históricas de dos reportes; los documentos de esta carpeta son la versión editorial vigente.

El ZIP se incluye como evidencia compacta, sin bases completas ni credenciales. Sus resultados corresponden al código y versiones registrados en los manifiestos; recalificarlos con código posterior puede cambiar los veredictos. Para inspeccionar la evidencia original no se necesita AWS ni Gemini.

Para recalificar, extraer el ZIP en la raíz del proyecto (las rutas internas comienzan por `eval/reports/`, `reports/` y `docs/`) en una **copia separada del repositorio**, para preservar los documentos actuales. Con la versión del grader registrada y gold disponible:

```bash
python -m eval.graders eval/reports/20261001T234945Z-S-with_gemini-r1-heldout
```

La recalificación modifica `grades.jsonl` y `metrics.json` de esa copia. Para ejecutar nuevas conversaciones, usar el comando de evaluación del README; eso sí puede invocar Gemini y generar costos.

## Figuras

- [Sankey de desenlaces](figures/sankey_desenlaces_S.png) y [matriz adversarial](figures/matriz_adversarial.png).
- [Paridad por idioma](figures/datos/03_paridad_idioma.png).
- [Pareto de contactos](figures/datos/04a_pareto_contactos.png), [demanda en UTC](figures/datos/04b_demanda_hora_dia.png) y [fraud score por resultado](figures/datos/04c_fraud_score_resultado.png).
- [Fuentes, agregados y límites de las figuras](figures/datos/README.md). No se evaluó EN; Queja no equivale a contactos de disputas; las distribuciones de fraude están normalizadas por grupo.

## Anexos metodológicos

Se conservan porque permiten revisar el criterio previo, las alternativas, las fuentes y las limitaciones; no son instrucciones pendientes del equipo.

- [Registro histórico de decisiones](decisions.md).
- Intenciones: [datos](../ml/intent/data_report.md), [guía de etiquetas](../ml/intent/labeling_guide.md), [familias](../ml/intent/plan_familias.md), [comparación](../ml/intent/comparacion_candidatos.md), [test](../ml/intent/resultados_test.md), [ablaciones](../ml/intent/ablaciones.md) y [costo del umbral](../ml/thresholds/costo_umbral.md).
- Gemini: [casos de extracción](../ml/llm/extraccion_casos.md); los pendientes históricos excluidos de la medición no se reincorporaron para mejorar sus números.
- Evaluación: [set congelado](../eval/cases/README.md), [esquema](../eval/cases/SCHEMA.md), [inventario de datos](../eval/cases/inventario.md), [formato de resultados](../eval/FORMATO_RESULTADOS.md) y [baselines](../eval/baselines/README.md).

## Contenido de la entrega

Se incluyen el código, las pruebas, configuración sin secretos, prompts versionados, modelo de servicio, gold reducido, datasets de evaluación, métricas pequeñas, figuras y evidencia final. El gold reducido permite arrancar la demo sin reconstruir S3.

Se excluyen `.env`, bases operativas SQLite, gold completo, Silver/Parquet, bases de trabajo de `data/runs/`, caches, dependencias instaladas y reportes intermedios generados. No se necesitan para probar la demo. Regenerar el histórico o algunas figuras sí requiere los insumos locales/S3 documentados.

Los límites de seguridad, los datos sintéticos, el test generado, el acuerdo de etiquetas no medido y los ajustes posteriores a la primera corrida se mantienen visibles: retirarlos haría que la entrega sobreestimara su evidencia.
