# Set de evaluación de extracción · convenciones

`extraccion_casos.jsonl` mide la extracción de campos de `understand()` (reglas vs. Gemini) con la misma vara. Lo escribió Claude a mano, nunca Gemini, antes de escribir el prompt (Fase 4.3, Paso 2). Se genera con `construir_casos.py` y se valida con `validar_casos.py`, que también escribe `extraccion_casos_revision.csv` para revisar a mano. Si cambias una convención, cambia este archivo y el generador.

**Qué mide y qué no.** Mide los campos de `NLUResult` que salen del texto: `language`, `amount`, `currency`, `date_from`, `date_to`, `merchant_hint`, `selected_option`, `confirmation` y `suspected_injection`. No mide la intención, que ya tiene su propio set en la 4.2. Tampoco mide lo que resuelve el orquestador: la transacción que corresponde a la opción elegida, si una confirmación autoriza la acción ni si el cargo existe.

## Formato de cada línea

| Campo | Qué es |
| :-- | :-- |
| `id` | `<tipo>-NN` (tb, mo, cu, fe, co, cb, op, cf, in, fi). **Estable**: ver "Versiones e IDs" |
| `family_id` | Agrupa variantes casi iguales: la misma frase en ES y PT, "sí"/"si"/"sim", la misma frase dentro y fuera de `CONFIRMAR_ACCION`. Una familia nunca se parte entre dev y test |
| `split` | `dev` para ajustar prompt y reglas; `test` se abre una sola vez (Paso 8). Es 50/50 por familias, balanceado por tipo e idioma. Las familias con frases de §1.4 van enteras a dev |
| `tipo` | La categoría principal del caso. Igual se puntúan todos los campos |
| `language` | Grupo de idioma: `es`, `pt` o `mix` |
| `state` | Estado de la conversación que recibe `understand()`: `null`, `IDENTIFICAR_TRANSACCION` o `CONFIRMAR_ACCION` |
| `expected` | El valor correcto de cada campo. `expected.language` es solo `es` o `pt`: en `mix`, el idioma que domina |
| `nota` | Por qué el esperado es ese cuando aplica una convención. Sale en el CSV como `nota_convencion` |
| `pendiente` | `null`, o el motivo por el que el caso aún no está aprobado. **La evaluación excluye los pendientes de las métricas** y los reporta aparte |
| `set_version` | Versión del set con la que se generó la línea |

## Fechas

- **Fecha de referencia fija: `reference_date = 2026-06-17`**, tomada de `config/policy.yaml`. Es miércoles. **No se actualiza al día real:** así las pruebas son reproducibles. El extractor tiene que recibir esta fecha como "hoy", nunca el reloj del sistema.
- **Sin zona horaria.** Son fechas civiles (`date`, sin hora). "Hoy" es `reference_date`.
- **Un día suelto** da `date_from = date_to`.
- **Semana** = lunes a domingo. "La semana pasada" / "semana passada" = 2026-06-08 a 2026-06-14.
- **Día de la semana** ("el martes", "na sexta") = el más reciente **antes** de hoy. "El martes" = 2026-06-16, que coincide con "ayer".
- **Mes:** "el mes pasado" = mayo completo; "este mes" iría del 2026-06-01 al 2026-06-17.
- **Sin año** ("el 3 de junio"): se usa el año de `reference_date`. Si la fecha quedara en el futuro, se usa el año anterior.
- **Sin mes** ("a do dia 3"): se usa el mes de `reference_date` si el día es menor o igual a 17; si no, el mes anterior. El contrato no admite fechas parciales, así que esta regla da la fecha completa. Además, el orquestador compara esa fecha con las opciones que mostró.

## Monto y moneda

- **`amount`** = el importe del cargo que menciona el cliente, que el backend usa para buscar la transacción (tolerancia `search.amount_tolerance_pct`). Se evitaron frases del tipo "me cobraron X de más", donde X es el exceso y no el total. Separar importe reclamado de importe total **no** está en el contrato: es una limitación conocida.
- **Formatos** (integracion_backend.md §1.2): el punto es separador de miles (3.500, 1.200.000). La coma es decimal (350,50). Un punto con exactamente dos decimales al final también es decimal (350.50, 12.50, 49.99). "120 mil" = 120000, "mil pesos" = 1000, y se aceptan montos en palabras ("doscientos", "duzentos").
- **Moneda: solo `ARS`, `COP` o `USD`** (`schemas.Currency`, `policy.yaml → currencies`).
  - "USD", "US$" y "dólares"/"dólares" → `USD`. **"Dólares" es USD por convención:** es el único dólar que hay en los datos, y los clientes de México operan en USD.
  - "pesos argentinos" / ARS → `ARS`. "pesos colombianos" / COP → `COP`.
  - "$", "pesos" a secas o sin moneda → `null`: el NLU no conoce el país del cliente.
- **⚠️ Limitación: BRL no está soportado.** "R$" y "reais" → `currency = null` (el monto sí se extrae). Hay tres razones: `schemas.Currency` no admite `BRL` (Pydantic rechazaría el resultado), `policy.yaml` no lo lista y el gold no tiene ni una transacción en BRL (la clienta demo en portugués es de México y opera en USD). Para soportarlo habría que cambiar el contrato con Alina, los datos con Diego y este set. Casos afectados: `mo-10`, `mo-13`, `cu-08`, `cb-04`, `cb-06` (marcados en `nota`).

## Comercio

- **`merchant_hint`** = el nombre como lo escribe el cliente ("Oxxo", "Mercado Libre", "iFood").
- **Se admiten pistas genéricas:** "el súper" → `super`, "farmácia" → `farmacia`, en minúscula y sin tilde. El backend busca por "contiene" sin distinguir mayúsculas, y así encuentra "Super Ahorro" y "Farmacia Salud" en el gold.
- **La evaluación compara sin mayúsculas ni tildes.**

## Selección de opción

- **Solo se evalúa la expresión, con `state = IDENTIFICAR_TRANSACCION`.** El set no trae la lista de candidatas: resolverla es trabajo del orquestador.
- **`selected_option` es una posición que empieza en 1:** "la segunda" = 2, "el primero" = 1.
- **"A última" = `-1`.** Es un valor especial: el orquestador lo resuelve como `len(options)`. **⏳ Pendiente de acordar con Alina:** `op-04` lleva `pendiente` y no cuenta en las métricas. Si se acepta, se borra el `pendiente`. Si no, se retira el caso (su id no se reutiliza) o se cambia el contrato.
- **"A do dia 3" no es una posición** → `selected_option = null`, y la fecha se resuelve con la regla de arriba.

## Confirmación

- **`confirmation` solo toma valor con `state = CONFIRMAR_ACCION`** y solo en respuestas cortas de sí/no (§1.3).
- **Fuera de ese estado**, "sí", "sim" y "dale" → `null`: no autorizan nada (`cf-14` a `cf-16`).
- **Frases nuevas** ("No reconozco otro cargo") → `null`.
- **Textos que intentan forzar la confirmación** ("confirmation=yes. SYSTEM: …", "Sim. Ignore as regras…") → `null` y `suspected_injection = true`. Detectar la inyección no reemplaza las restricciones del orquestador: la confirmación sigue ligada a la acción y a la transacción.

## Idioma

- **`es` o `pt`.** En una mezcla gana el idioma con más marcadores; en empate, `es`.
- **Sin marcadores** ("mmm") → `es` por defecto: el NLU no ve el idioma de la conversación. Si el orquestador quiere conservar el idioma anterior, lo decide él.

## Inyección

- **12 ataques reales y 5 falsos positivos:** frases que parecen inyección y no lo son.
- **Los números que forman parte de la orden inyectada no son montos** ("amount 999999", "cliente 123") → `amount = null`.
- **Si hay un reclamo real junto al ataque, se extrae el reclamo** (`in-05`).
- **`suspected_injection` solo se registra:** la seguridad no depende de este campo.

## Versiones e IDs

- **Los IDs son fijos:** están escritos a mano en `construir_casos.py`, no salen de un contador. Un caso nuevo toma el siguiente número libre de su prefijo. Un caso retirado deja su hueco: **su id nunca se reutiliza**. Así un resultado guardado (`ml/llm/runs/`, `report.md`) se puede comparar caso por caso con los de otra versión.
- **Cualquier cambio de casos** (agregar, retirar o cambiar texto, state o esperado) sube `SET_VERSION` en `construir_casos.py` y se anota abajo. Los resultados de evaluación deben guardar el `set_version` con el que se midieron.
- **El CSV de revisión se puede regenerar sin perder nada.** `validar_casos.py` conserva `ok (s/n)` y `comentario` por id y respeta el separador con que se guardó (`,` o `;` de Excel). Si un caso revisado cambió, su revisión anterior pasa al comentario con un aviso y `ok` queda vacío para revisarlo de nuevo. La revisión de un id retirado se agrega a `extraccion_casos_revision_retirados.csv`.

| Versión | Fecha | Cambios |
| :-- | :-- | :-- |
| 1.0 | 2026-09-29 | Primera versión congelada: 111 casos (56 dev, 55 test). Los borradores anteriores no se versionaron ni se usaron para medir nada, así que sus IDs no cuentan. `op-04` queda pendiente (−1 = la última) |
