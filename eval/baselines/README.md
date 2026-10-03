# Baselines de evaluación

B0 lee `baseline_metrics` de gold. Son agregados del histórico completo utilizado
en Fase 2, aunque el gold de servicio tenga una muestra de clientes. No representa
la carga del set conversacional ni un runner que atienda sus casos.

```powershell
.venv\Scripts\python.exe -m eval.baselines.status_quo
```

Escribe `eval/reports/b0.json`: FCR ponderado por contactos, resolución y SLA de
disputas, con poblaciones y denominadores. La mediana no tiene numerador de ratio.
Duraciones nulas no se imputan y los 5.623 valores observados no representan todas
las 24.491 disputas.

B1 usa la opción A acordada: mismo backend, política, datos, herramientas,
orquestador y reglas de extracción; intención por palabras clave y respuestas
por plantillas. No es un bot independiente de formulario fijo. La comparación
con S mide la aportación del clasificador y Gemini sobre esa infraestructura.

```powershell
.venv\Scripts\python.exe -m eval.runner --system B1 --split dev
.venv\Scripts\python.exe -m eval.baselines.verify_b1 eval/reports/<run_id>
.venv\Scripts\python.exe -m eval.graders eval/reports/<run_id>
```

El runner activa `NLU_MODE=keywords`, vacía `GEMINI_API_KEY` en el subproceso y
usa SQLite en memoria. El runner existente además fija una ruta de modelo inexistente;
su advertencia de fallback es esperada. Backend ya implementa el modo keywords.
La auditoría comprueba manifest, integridad de IDs, extractor rules, versión
stub-keywords, plantillas, tokens y costo cero. Los turnos de botones tienen
versión `none`, porque no invocan NLU. Un costo cero por sí solo no prueba B1.

El grader de handoff se enchufa automáticamente en `eval.graders`. Recibe los
casos operativos y el cliente del caso de evaluación, además del paquete.
Comprueba esquema, campos no vacíos, dueño, segmento/país, ancla y hechos de
transacción, hechos de tarjetas/perfil, caso operativo, prioridad, SLA y cola.
Fuentes desconocidas o no disponibles dan `grader_error`, nunca un pase.
El estado mutable de una tarjeta no se verifica contra el snapshot gold; si
aparece como hecho, requiere evidencia operativa adicional. La validación de
acciones y confirmaciones pertenece a los graders generales de Ariela.

```powershell
.venv\Scripts\python.exe -m eval.impacto --rate 0.35 --min-rate 0.30 --max-rate 0.40 --rate-source "escenario ilustrativo"
```

Escribe `eval/reports/impacto.json`. No hay tasa predeterminada que se pueda
confundir con un resultado medido. Después de las tres corridas finales, pasar
su media, mínimo y máximo y sus IDs en `--rate-source`. El rango entre corridas
no es un intervalo de confianza.

## Datos necesarios en un clon limpio

Se versionan solo cinco archivos de `data/runs/20260929T234658Z-7cf922c1/`:
demo_scenarios, metricas_problema, policy_calibration, backend_acceptance y policy.
`ultima_corrida()` descubre `demo_scenarios.json`; no requiere manifest ni bases
de trabajo. La política de esa corrida es la histórica 1.1.0, no la vigente 1.3.0
usada en evaluación. No sustituir una por otra.

Los reportes de ejecución se generan localmente bajo `eval/reports/`, excluido de
Git. Este código permite reproducirlos. Las bases grandes y manifest completo
siguen excluidos. `data/gold/gold.duckdb` ya está versionado por el equipo.

## Validación del 1-oct-2026

Corrida dev: `20261001T233946Z-B1-without_gemini-r1-dev`, 41/41 terminados,
0 errores del runner, 0 max_turns. Auditoría B1: 53 spans de NLU, todos rules;
costo y tokens cero. Graders 1.1.0: resolución automática segura 15/38 y
handoffs completos 14/14. Son resultados de desarrollo, no finales held-out.
No se volvió a ejecutar el held-out para desarrollar estos módulos.
