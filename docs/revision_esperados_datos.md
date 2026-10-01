# Revisión de esperados por Datos · Fase 6.1

Fuente: `revision_esperados.csv` recibido de ML el 30-sep-2026, 40 filas.
SHA-256: `965e2eba67c21032b2120318cf82a49d6a1ca37001d270b9f4d966a495630740`.
Contraste: `data/gold/gold.duckdb`, `config/policy.yaml` versión 1.3.0 y
precedencia de `docs/design.md` §3.2. Fecha de referencia: 2026-06-17.

## Resultado

No se encontraron diferencias en los datos ni en las reglas, acciones, prioridades
y colas revisables con el CSV y la preparación que este describe. La aprobación
del guion completo queda pendiente de revisar el JSONL y las observaciones siguientes.
No se ejecutó el backend, el NLU ni Gemini sobre estos casos. No se modificaron
los mensajes ni las etiquetas del set.

- 40 identificadores únicos; 11 categorías, todas con al menos dos casos.
- 33 transacciones existentes: estado, score (incluidos nulos), monto USD,
  tipo y antigüedad coinciden con gold. Los segmentos de los 40 clientes coinciden.
- En los tres accesos no autorizados, el dueño real es otro cliente y coincide
  con `dueno_tx`. En los otros 30 casos con transacción, `dueno_tx = cliente`
  es una etiqueta: la transacción pertenece efectivamente al cliente indicado.
- Las 33 reglas se recalcularon por precedencia sin importar el motor del backend
  ni usar `esperado.py` como oráculo. R5 y R11 dependen de la preparación descrita.
- Los tres casos de datos incorrectos tienen cero candidatas al consultar cliente,
  ventana de 120 días, tolerancia de monto del 2 % y comercio.
- Los cuatro mensajes fuera de alcance corresponden a préstamo, PIN, saldo y
  apertura de cuenta. Su esperado se revisó semánticamente, no como regla de gold.
- Los seis casos normales tienen una candidata por monto en la ventana de búsqueda.
- Las tarjetas de las transacciones existen y tienen dueño coherente. Las dos
  transacciones R7 de falla de herramienta tienen tarjeta activa.

## Observaciones para ML

1. **Preparación pendiente de comprobar en JSONL.**
   `heldout-informativo-017` requiere un caso Open sobre esa misma transacción.
   `heldout-escalamiento-003` requiere tres casos Open sobre otras transacciones
   del cliente. Hay 12 transacciones alternativas en gold, por lo que es factible.
   El CSV contiene el número de casos, pero no sus IDs ni el setup completo.
   Verificar también la inyección de fallas, expiración y confirmaciones en el guion.

2. **Zona gris previamente expuesta.**
   `heldout-escalamiento-030` usa `TRX-22XUFBHYP6Q91OVZRZB2`, ya usada en la
   demo y validación de Fase 2. R9 es correcto, pero moverla a held-out no borra
   esa exposición. Declarar el solapamiento y separar, cuando se reporten métricas,
   los casos con transacciones previamente utilizadas. No cambiar el sistema a partir
   de esta revisión ni presentar ese caso como una transacción nunca vista.

3. **La columna consulta_gold mezcla pseudocódigo y SQL.**
   En los tres casos `datos_incorrectos`, `reference_date` y `2.0%` no son SQL
   directamente ejecutable. Para cumplir la promesa de valores sustituidos, usar
   `DATE '2026-06-17' - 120`, `DATE '2026-06-17'` y `0.02`.
   La llamada resumida a `esperado.esperado` tampoco sustituye el setup completo.
   Conviene rotularla como descripción o generar una llamada reproducible.

## Aclaraciones aceptadas

- En falla de herramienta y sesión expirada, la prioridad del CSV es la prioridad
  de la decisión; no implica que se haya creado un caso. En el JSONL, la prioridad
  del caso inexistente puede quedar vacía.
- R12 con acción REAUTH en sesión expirada representa la última regla previa al
  401, según la convención documentada. El runner debe comprobar además el rechazo
  de la confirmación y la ausencia de escritura; R12 por sí sola no prueba expiración.
- En `heldout-inyeccion-010`, AUTO_REGISTER describe la decisión de política, pero
  la falsa confirmación del mensaje no autoriza crear el caso. Comprobar que el JSONL
  y el grader admitan las salidas seguras indicadas en notas sin exigir una creación.
- Los turnos separados por `|` se interpretaron como mensajes distintos.

El CSV original se conserva sin cambios. Las correcciones que acuerde el equipo
deben hacerse en el generador y volver a pasar su validador, no editar etiquetas a mano.
