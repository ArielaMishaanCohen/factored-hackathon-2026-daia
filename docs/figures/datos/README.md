# Gráficas de Datos para las slides

Figuras de paridad por idioma y tres vistas de evidencia histórica. Cada figura tiene PNG de 2880 × 1440 y SVG editable. `graficas_datos_slides.zip` reúne las figuras, sus agregados y estas notas. El Sankey y la matriz adversarial están en la carpeta superior.

Colores provisionales, configurables al regenerar las figuras: verde `#15803D`, ámbar `#D97706`, rojo `#DC2626`.

## 3. Paridad por idioma

`03_paridad_idioma`: resolución automática segura, corrección del caso y escalamiento omitido. Cada punto es la media de tres corridas; las barras muestran mínimo y máximo entre corridas, **no intervalos de confianza**. Se compara S con Gemini, S sin Gemini y B1.

- Con Gemini, resolución segura: ES 46.50%, PT 46.67%. Sin Gemini: ES 45.68%, PT 41.33%. B1: ES 37.04%, PT 30.67%.
- La mejora con Gemini sobre S sin Gemini es de 0.82 puntos porcentuales en ES y 5.33 en PT. Es una comparación descriptiva de este set; las categorías de casos no están balanceadas entre idiomas.
- `mix` significa mensajes multilingües; no es una evaluación independiente en inglés. **EN no se evaluó** y no se representa con un cero.
- El denominador de resolución segura es de 81 casos ES, 75 PT y 18 mixtos por corrida. En escalamiento omitido, el grupo mixto tiene solo 3 casos esperados de escalamiento. Una diferencia en ese grupo tiene mucha sensibilidad a un único caso.
- Las tres corridas repiten el mismo set congelado: no son tres muestras independientes. Los denominadores de cada métrica aparecen en la figura y en el JSON.

## 4. Evidencia histórica del problema

`04a_pareto_contactos`: motivos de los 686,296 contactos del histórico. Se destaca **Queja** (117,021 contactos), porque esta fuente no tiene una categoría específica de disputas. No se debe presentar esa barra como 117,021 disputas. Como evidencia complementaria, hay 24,491 quejas de disputas entre 67,095 quejas totales, usando las subcategorías Cargo no reconocido y Cobro indebido. Son otra tabla y otro denominador; las subcategorías ausentes no se imputan. El FCR de los contactos de Queja es 43.6%.

`04b_demanda_hora_dia`: conteos acumulados por hora y día de la semana en **UTC**. El diccionario no declara zona horaria para timestamps sin offset; el pipeline los asume UTC. No son horas locales del cliente, promedios por día ni una medición de saturación o capacidad. Las horas se extraen explícitamente en UTC, independientemente de la zona de la computadora.

`04c_fraud_score_resultado`: distribución por la etiqueta sintética `is_fraud`, no por el estado de la transacción. Cada curva se normaliza dentro de su grupo, por lo que su altura no muestra prevalencia. Se excluyen 286,242 scores nulos de 1,429,456 transacciones (20.0%); siguen siendo riesgo desconocido. Las líneas 30 y 40 identifican umbrales de política. Un score bajo no garantiza ausencia de fraude. Esta figura es descriptiva del histórico completo, no una validación temporal ni evidencia de impacto causal.

Todos los datos bancarios son ficticios del hackatón. No se hizo shadow mode ni se midió ahorro observado en producción con estas gráficas.

## Fuentes y reproducción

`datos_graficas.json` conserva agregados, denominadores, IDs de las nueve corridas y SHA-256 del resumen de evaluación. No incluye llaves ni filas de clientes. Las figuras usan `eval/reports/final_summary_datos.json`, el Silver de la corrida `20260929T234658Z-7cf922c1` y sus métricas históricas.

Desde la raíz del proyecto:

```powershell
.venv\Scripts\python.exe analysis/graficas_slides.py
# Cuando tengamos los colores definitivos:
.venv\Scripts\python.exe analysis/graficas_slides.py --green "#15803D" --amber "#D97706" --red "#DC2626"
```

Se necesita tener localmente el Silver y el resumen de evaluación; no se descargan datos de AWS ni se repiten llamadas a Gemini. Esos insumos grandes/locales no están todos versionados. Los PNG, SVG y agregados de esta carpeta sí permiten compartir la entrega sin pasar la base completa. Los argumentos `--summary`, `--silver`, `--historical` y `--output` permiten cambiar las rutas.
