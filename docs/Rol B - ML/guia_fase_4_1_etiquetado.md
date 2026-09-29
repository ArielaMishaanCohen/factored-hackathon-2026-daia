# Guía paso a paso · Fase 4.1 · Set etiquetado de intenciones (v2)

**Para:** rol B (ML) · **Fecha:** lunes 28-sep-2026 · **Meta:** tener el set listo el **martes 29 en la tarde**, para entrenar los modelos (4.2) el martes en la noche y el miércoles.

> Cómo usar esta guía: ve paso por paso, en orden. Cada paso dice **qué es**, **qué haces tú** y **qué le escribes a Claude** (en un bloque que puedes copiar y pegar). Cuando termines un paso, marca la casilla `[x]`. Si algo sale raro, pégale a Claude el error completo y pregúntale.

**Qué cambió respecto a la v1:** ya no escribimos todo el set a mano. Train y val salen de **Banking77** (consultas bancarias reales escritas por personas, en inglés), traducidas y re-etiquetadas con nuestras reglas, más un **suplemento** generado para lo que Banking77 no tiene. El **test** lo sigue escribiendo el equipo, y ahora es más chico (~200 frases). La guía de etiquetado sube a la versión 1.2.

---

## Paso 0 · Entender qué estamos haciendo (lee esto una vez, 5 min)

Nuestro chatbot recibe mensajes como *"no reconozco un cargo de 350 en Oxxo"*. Lo primero que tiene que hacer es entender **qué quiere el cliente** (la **intención**). Hay 5 intenciones más una etiqueta extra:

| Etiqueta                 | Qué quiere el cliente                                                                       | Ejemplo                                    |
| :----------------------- | :------------------------------------------------------------------------------------------- | :----------------------------------------- |
| `cargo_no_reconocido`  | Ve un cargo que**no sabe de dónde salió**                                            | "No reconozco un cobro de 1.200 pesos"     |
| `cobro_incorrecto`     | **Sí** sabe qué compró, pero le cobraron mal (doble, de más, después de cancelar) | "Me cobraron dos veces el súper"          |
| `tarjeta_comprometida` | Le robaron, perdió o clonaron la tarjeta, o hay**varias** compras en poco tiempo      | "Me robaron la tarjeta"                    |
| `estado_disputa`       | Pregunta cómo va un reclamo que**ya hizo**                                            | "¿Cómo va mi reclamo?"                   |
| `fuera_de_alcance`     | Pide otra cosa (préstamo, saldo, PIN, límite, pago pendiente…)                            | "Quiero un préstamo"                      |
| `ambiguo`              | No se entiende qué quiere sin preguntarle                                                   | "Tengo un problema con mi tarjeta", "hola" |

### Las tres fuentes del set

| Fuente                    | Qué es                                                                                                                 | Quién escribe                                  | `origin`                        | ¿Puede ir a test? |      Tamaño aprox. |
| :------------------------ | :---------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------- | :-------------------------------- | :----------------: | ------------------: |
| **Banking77**       | Consultas reales de clientes de un banco (inglés), filtradas a las clases que nos sirven                               | Personas (dataset público); Claude traduce     | `externo_traducido`             |         No         |              ~1.850 |
| **Suplemento**      | Lo que Banking77 no tiene:`estado_disputa`, `ambiguo`, portuñol, jerga latinoamericana, inyecciones, casos límite | Claude genera, tú revisas                      | `llm`                           |         No         | ~800 (160 familias) |
| **Test del equipo** | El examen final                                                                                                         | Tú escribes en español; Claude traduce PT/mix | `equipo` / `equipo_traducido` |  Sí (solo esta)  |  ~200 (50 familias) |

### Tres ideas clave (son las que el jurado va a revisar)

1. **Train y test vienen de fuentes distintas.** El modelo aprende con Banking77 + suplemento y se evalúa con frases que escribiste tú. No puede "aprenderse el estilo del autor" del test, porque ese autor nunca aparece en train. Esto evita la fuga por construcción, y es más fuerte que solo separar por familia.
2. **Familias y split por familia.** En el suplemento y el test escribimos una *idea base* y varias formas de decirla. Todas comparten `family_id` y **una familia entera va a un solo split**. Train/val se dividen 80/20 por familia; el test es aparte.
3. **Acuerdo entre personas (kappa).** Dos personas etiquetan las mismas ~100 frases sin verse, y medimos cuánto coinciden con el **kappa de Cohen** (> 0,8 es muy bueno). Ahora importa más: también mide si el re-etiquetado de Banking77 con nuestras reglas es consistente.

### Qué vas a entregar al final de la 4.1

- [ ] `ml/intent/data/frases.jsonl` → todas las frases (la fuente de verdad)
- [ ] `ml/intent/data/train.jsonl`, `val.jsonl`, `test.jsonl`
- [ ] Kappa de Cohen calculado sobre ~100 frases
- [ ] `ml/intent/data_report.md` → conteos por fuente, etiqueta, idioma y split
- [ ] Decisión nueva en `docs/decisions.md` (y D4.1 marcada como reemplazada)

### Tamaño objetivo

~2.850 frases: ~2.650 en train/val y ~200 en test. Idiomas: ~50 % español, ~40 % portugués, 5–10 % mezcla ("portuñol"). La mezcla solo sale del suplemento y del test, porque Banking77 no se traduce a portuñol.

### Calendario sugerido

| Cuándo              | Pasos                                      | Tu tiempo                            |
| :------------------- | :----------------------------------------- | :----------------------------------- |
| Lunes en la noche    | 1 a 5 (Banking77 listo y traducido)        | ~1,5 h (sobre todo revisar)          |
| Martes en la mañana | 6 a 8 (plan de familias, test, suplemento) | ~2,5 h                               |
| Martes al mediodía  | 9 (armar el dataset)                       | ~15 min                              |
| Martes en la tarde   | 10 a 12 (kappa, documentación, subir)     | ~1,5 h (con otra persona 30–40 min) |

> Pídele hoy a alguien del equipo 30–40 min del martes en la tarde para el kappa (Paso 10).

---

## Paso 1 · Preparar el repo (5 min)

**Qué es:** traer lo último del equipo.

**Estado:** el `.gitignore` ya está corregido (`/data/` en vez de `data/`, así `ml/intent/data/` sí se sube). Falta solo el `git pull`. Hazlo **tú desde tu terminal**, porque Claude no tiene tus credenciales de GitHub:

```
git pull
```

Si te sale un conflicto, pégale a Claude la salida completa.

- [X] `git pull` hecho
- [ ] Avisaste al equipo del cambio en `.gitignore` (1 línea)

---

## Paso 2 · Aprender las reglas de etiquetado (15 min)

**Qué es:** leer las reglas para decidir la etiqueta cuando una frase podría ser de dos clases.

**Qué haces tú:** abre [ml/intent/labeling_guide.md](../../ml/intent/labeling_guide.md) (versión 1.2). Lo más importante es el **orden de las reglas** (gana la primera que se cumpla) y las **aclaraciones nuevas de la 1.2** (pagos pendientes, reembolsos del comercio, comisiones, pagos rechazados). Esas aclaraciones son decisiones: si alguna no te convence, cámbiala ahora, antes de etiquetar nada.

1. ¿Robo, pérdida, clonación o *varias* compras que no hizo en poco tiempo? → `tarjeta_comprometida` (guía 1.4: varios cargos sin apuro → `cargo_no_reconocido`)
2. ¿Pregunta por un reclamo que ya le hizo al banco? → `estado_disputa`
3. ¿Reconoce el comercio pero el cobro está mal? → `cobro_incorrecto`
4. ¿No reconoce el cargo? → `cargo_no_reconocido`
5. ¿Pide otra cosa? → `fuera_de_alcance`
6. ¿No se puede saber sin preguntar? → `ambiguo`

**Practica con Claude (opcional, recomendado):**

```
Hazme un quiz de 10 frases (mezcla español y portugués) para practicar las reglas
de ml/intent/labeling_guide.md versión 1.2, incluyendo las aclaraciones nuevas.
Dame una frase a la vez, yo te digo la etiqueta, y tú me corriges explicando qué
regla aplica. Incluye casos difíciles entre clases.
```

- [ ] Hecho

---

## Paso 3 · Bajar Banking77 y proponer el mapeo de clases (20 min tuyos)

**Qué es:** Banking77 tiene 77 clases; nosotros, 6. Hay que decidir qué clase de Banking77 corresponde a cuál nuestra, o si se descarta.

**Mapeo propuesto (lo validas tú en este paso):**

| Nuestra etiqueta                            | Clases de Banking77                                                                                                                                                                            | Nota                                                                                                                         |
| :------------------------------------------ | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------- |
| `cargo_no_reconocido`                     | `card_payment_not_recognised`, `cash_withdrawal_not_recognised`, `direct_debit_payment_not_recognised`                                                                                   |                                                                                                                              |
| `cobro_incorrecto`                        | `transaction_charged_twice`, `extra_charge_on_statement`, `card_payment_wrong_exchange_rate`, `wrong_exchange_rate_for_cash_withdrawal`, `wrong_amount_of_cash_received`             |                                                                                                                              |
| `cobro_incorrecto` o `fuera_de_alcance` | `card_payment_fee_charged`, `cash_withdrawal_charge`                                                                                                                                       | Depende de cada frase (aclaración de comisiones). Van a revisión en el Paso 4.                                             |
| `tarjeta_comprometida`                    | `compromised_card`, `lost_or_stolen_card`                                                                                                                                                  |                                                                                                                              |
| `fuera_de_alcance` (negativos difíciles) | `declined_card_payment`, `pending_card_payment`, `request_refund`, `Refund_not_showing_up`, `reverted_card_payment?`, `balance_not_updated_after_card_payment`, `card_swallowed` | Se parecen a nuestras clases pero no lo son. Son los ejemplos más valiosos para`fuera_de_alcance`.                        |
| `fuera_de_alcance` (resto)                | Muestra aleatoria del resto de clases                                                                                                                                                          | Para que el modelo vea pedidos variados.                                                                                     |
| Por decidir                                 | `lost_or_stolen_phone`                                                                                                                                                                       | Si habla solo del celular, ¿es`fuera_de_alcance` o `tarjeta_comprometida`? Decide y agrégalo a la guía de etiquetado. |

**Escríbele a Claude:**

```
Paso 3 de docs/Rol B - ML/guia_fase_4_1_etiquetado.md. Crea
ml/intent/sources/banking77_prepare.py que:
1. Descargue PolyAI/banking77 (train + test originales, juntos) desde Hugging Face
   y lo guarde en /data/external/banking77.csv (no se sube a git).
2. Verifique que los nombres de clase del mapeo propuesto de la guía existan tal
   cual en el dataset y me avise si alguno no coincide.
3. Cree ml/intent/b77_mapeo.csv con una fila por cada una de las 77 clases:
   b77_label, n_frases, 3 ejemplos, label_propuesta (según la guía, o
   "descartar" / "fuera_de_alcance_resto"), decision (vacía para que yo la llene).
Córrelo y muéstrame la tabla de las clases que NO son "fuera_de_alcance_resto".
```

**Qué haces tú:** abre `b77_mapeo.csv` y llena la columna `decision` (copia la propuesta si estás de acuerdo; cámbiala si no). Lee los 3 ejemplos de cada clase antes de decidir.

- [X] `b77_mapeo.csv` revisado y con `decision` llena

---

## Paso 4 · Filtrar, muestrear y re-etiquetar Banking77 (45 min tuyos)

**Qué es:** quedarnos con ~1.850 frases balanceadas y corregir las que, según nuestras reglas, no corresponden a la etiqueta de su clase.

**Por qué re-etiquetar:** las fronteras de Banking77 no son las nuestras. Una frase de `card_payment_not_recognised` que dice *"I was charged twice"* es `cobro_incorrecto` por nuestra regla 3. Una que dice *"my card was stolen and there's a payment I don't know"* es `tarjeta_comprometida` por la regla 1.

**Tope por etiqueta (para que no domine `fuera_de_alcance`):** `cargo_no_reconocido` ~450 · `cobro_incorrecto` ~450 · `tarjeta_comprometida` ~350 (o todas si hay menos) · `fuera_de_alcance` ~600 (≈ 350 negativos difíciles + 250 del resto).

**Escríbele a Claude:**

```
Paso 4 de la guía de la 4.1. Con ml/intent/b77_mapeo.csv (columna decision):
1. Filtra /data/external/banking77.csv, asigna label_inicial según el mapeo y
   muestrea con semilla 42 hasta los topes por etiqueta de la guía, estratificando
   por clase original de Banking77. Elimina duplicados exactos (ignorando
   mayúsculas y puntuación).
2. Marca como "sospechosa" cada frase donde las reglas de
   ml/intent/labeling_guide.md 1.2 sugieran otra etiqueta (robo/pérdida/clonación,
   duplicados, reclamo ya hecho, comisión dudosa, etc.). Para cada sospechosa pon
   label_sugerida y el motivo en una línea.
3. Guarda todo en ml/intent/b77_seleccion.csv con columnas: b77_idx, b77_label,
   text_en, label_inicial, sospechosa, label_sugerida, motivo, label_final
   (label_final = label_inicial en las no sospechosas; vacía en las sospechosas).
4. Dime cuántas frases quedaron por etiqueta y cuántas sospechosas hay.
```

**Qué haces tú:** filtra `sospechosa = sí` y llena `label_final` en cada una. Si dudas en alguna, anota el caso: puede convertirse en regla nueva de la guía.

- [X] Sospechosas revisadas (todas con `label_final`)

---

## Paso 5 · Traducir Banking77 a español y portugués (20 min tuyos)

**Qué es:** cada frase se traduce a **un solo idioma**: ~55 % a español y ~45 % a portugués brasileño. Nunca la misma frase a los dos, porque serían casi duplicados entre idiomas.

**Reglas de traducción:** registro de chat informal (como se escribe por WhatsApp), misma intención, localización **mínima** (libras → pesos o reais, nombres de apps genéricos). No agregar ni quitar información. El ruido (typos, sin tildes) **no** se agrega aquí: lo agrega el script del Paso 9, de forma medible.

**Escríbele a Claude:**

```
Paso 5 de la guía de la 4.1. Traduce ml/intent/b77_seleccion.csv:
1. Asigna language con semilla 42: 55 % "es" y 45 % "pt", estratificado por
   label_final. variant: "neutro" para es, "BR" para pt.
2. Traduce text_en en lotes, en registro de chat informal, sin cambiar la
   intención, con localización mínima (moneda y nombres genéricos). No agregues
   typos: eso lo hace noise.py después.
3. Guarda ml/intent/b77_traducido.csv con: b77_idx, b77_label, text_en, text,
   language, variant, label (= label_final).
4. Si en alguna frase la traducción cambia el sentido o la etiqueta ya no aplica,
   márcala en una columna "revisar" con el motivo.
Al final dame 30 frases al azar (15 es, 15 pt) junto a su original en inglés para
que yo las revise.
```

**Qué haces tú:** revisa las 30 de muestra y todas las marcadas en `revisar`. Si ves un error sistemático (por ejemplo, un término mal traducido siempre igual), díselo a Claude para que lo corrija en todo el archivo.

- [X] Muestra revisada y marcadas resueltas

---

## Paso 6 · Plan de familias del suplemento y del test (15 min)

**Qué es:** decidir cuántas familias escribir de cada etiqueta e idioma. Ahora las familias son solo para el suplemento (generado) y para el test (tuyo).

**Test del equipo (50 familias × 4 frases ≈ 200):**

| Etiqueta                 |   Familias   |      ES      |      PT      |   Mezcla   |
| :----------------------- | :----------: | :----------: | :----------: | :---------: |
| `cargo_no_reconocido`  |      10      |      5      |      4      |      1      |
| `cobro_incorrecto`     |      10      |      5      |      4      |      1      |
| `tarjeta_comprometida` |      9      |      4      |      4      |      1      |
| `estado_disputa`       |      8      |      4      |      3      |      1      |
| `fuera_de_alcance`     |      7      |      4      |      3      |      0      |
| `ambiguo`              |      6      |      3      |      2      |      1      |
| **Total**          | **50** | **25** | **20** | **5** |

**Suplemento (160 familias × ~5 frases ≈ 800):**

| Bloque                                                               |   Familias   | Para qué                                                                          |
| :------------------------------------------------------------------- | :-----------: | :--------------------------------------------------------------------------------- |
| `estado_disputa`                                                   |      50      | Banking77 no tiene esta clase                                                      |
| `ambiguo`                                                          |      40      | Banking77 no tiene esta clase                                                      |
| Localización y portuñol (10 por cada una de las otras 4 etiquetas) |      40      | Oxxo, Pix, Nubank, Mercado Libre, "lana", "grana", "guita"; frases mezcladas ES/PT |
| Casos límite entre clases e inyecciones con intención real         |      30      | Las fronteras de nuestras reglas y los intentos de manipular al bot                |
| **Total**                                                      | **160** |                                                                                    |

Idiomas del suplemento: ~40 % ES, ~35 % PT, ~25 % mezcla. Cada familia es de un solo idioma.

**Escríbele a Claude:**

```
Crea ml/intent/plan_familias.md con las dos tablas del Paso 6 de la guía de la
4.1 (test y suplemento). Para cada etiqueta sugiere una lista de subtemas para
que las familias no se repitan (p. ej., estado_disputa: pregunta por número de
folio, se queja de la demora, pregunta si ya le devolvieron, pide hablar con
alguien por su reclamo...). Separa los subtemas en dos listas: "para el test" y
"para el suplemento", sin repetir subtemas entre ambas.
```

- [X] `plan_familias.md` listo

---

## Paso 7 · Escribir el test (la parte más importante, ~1,5 h)

**Qué es:** escribir **tú, a mano**, las 50 familias del test: una semilla y 3 paráfrasis por familia. Que lo escriba una persona, y que sea una fuente distinta a train, es lo que hace creíble la evaluación.

**Escríbele a Claude:**

```
Crea ml/intent/test_para_escribir.csv con las 50 familias del test según
ml/intent/plan_familias.md: family_id (t001 a t050), label, language, variant
(vacía), subtema, semilla, parafrasis_1, parafrasis_2, parafrasis_3, notas.
En las familias pt y mix yo escribo en español; la traducción va después.
Llena solo las columnas de planificación; el texto lo escribo yo.
```

**Consejos para escribir:**

- Escribe como escribe la gente real por WhatsApp: sin tildes, con errores, con "lana", "plata", "grana", "q", "xq".
- Mezcla frases cortas ("cobro doble oxxo") y largas (una historia de 2–3 líneas).
- Pon montos a veces sí y a veces no; fechas relativas ("ayer", "la semana pasada").
- Varía los países: MX (pesos, Oxxo, "lana"), CO (pesos, "plata", Éxito), AR (pesos, "guita", Mercado Libre), BR (reais, "grana", Pix, Nubank, iFood).
- Las 3 paráfrasis deben ser distintas de verdad (otro orden, otro largo, otro detalle), no la misma frase con una palabra cambiada.
- En `notas` escribe cualquier duda de etiqueta.

**Cuando termines, pide la traducción:**

```
Ya llené ml/intent/test_para_escribir.csv. En las familias pt, traduce semilla y
paráfrasis a portugués brasileño informal de chat (con "vc", "q", "n", jerga como
"grana", conservando mis errores y abreviaturas). En las mix, escribe una mezcla
natural de español y portugués. No cambies la intención; si alguna cambia de
sentido al traducir, avísame en notas. Guarda mis borradores en español en
columnas aparte (no entran al set) y marca estas frases como equipo_traducido.
Luego revisa: ¿hay filas vacías, etiquetas que según la guía 1.2 no corresponden,
o familias casi iguales? Dime cuáles, pero NO las cambies: yo decido.
```

- [X] Test escrito (50 familias). **Nota (29-sep):** por falta de tiempo se generó con ChatGPT y lo revisó el equipo (`origin: llm_externo`, guía 1.3). Queda como limitación declarada en el Paso 11 y como pendiente: ver "Pendientes" al final.
- [X] PT/mix traducidas (dudas de etiqueta: t005, t007, t047, t050)

---

## Paso 8 · Generar el suplemento (45 min tuyos, revisando)

**Qué es:** Claude genera las 160 familias del suplemento a partir de los subtemas del plan. **No lee el test** para hacerlo, así no se "contagia" de tus frases.

**Escríbele a Claude:**

```
Paso 8 de la guía de la 4.1. Genera el suplemento según la tabla y los subtemas
"para el suplemento" de ml/intent/plan_familias.md. IMPORTANTE: no abras ni leas
ml/intent/test_para_escribir.csv.
Para cada familia (s001 a s160): una semilla y 4 paráfrasis en el mismo idioma y
variante, con la misma etiqueta según ml/intent/labeling_guide.md 1.2. Varía
largo, jerga, montos, fechas y país. Las de inyección deben tener una intención
real clara. No agregues typos: eso lo hace noise.py.
Guárdalo en ml/intent/suplemento_llm.csv (family_id, label, language, variant,
subtema, text) y dame 5 familias al azar por bloque para que las revise.
```

**Tu revisión (no te la saltes):** además de la muestra, recorre el archivo filtrando por etiqueta y borra o corrige las frases que:

- cambiaron de intención (ej. la familia es `estado_disputa` y la frase no menciona ningún reclamo previo),
- suenan falsas o demasiado formales,
- son casi idénticas a otra.

- [X] Suplemento generado y revisado

---

## Paso 9 · Ruido y armado final (15 min)

**Qué es:** agregar las imperfecciones de forma **medible y reproducible**, y juntar todo en el formato final con un script que valide que no haya fuga.

**Por qué el ruido va por script:** así sabemos exactamente qué frase tiene qué imperfección (campo `noise`), las proporciones quedan documentadas y en la 4.2 podemos medir cuánto le afecta el ruido al modelo. El test **no** lleva ruido artificial: tiene el ruido natural de cómo escribiste.

**Escríbele a Claude:**

```
Paso 9 de la guía de la 4.1.
A) Crea ml/intent/noise.py con semilla 42, que aplique a cada frase de train/val
   (Banking77 traducido y suplemento, nunca test) cero o más transformaciones,
   registrándolas en una lista:
   sin_tildes (~50 %), minusculas (~40 %), sin_puntuacion (~40 %),
   abreviaturas es/pt tipo q, xq, tb, vc, n, pq (~30 %), typo por intercambio u
   omisión de una letra (~25 %), letras o signos repetidos (~10 %), emoji (~10 %).
   ~30 % de las frases quedan sin ruido. Que no rompa montos ni números.
B) Crea ml/intent/build_dataset.py que:
   1. Lea b77_traducido.csv, suplemento_llm.csv y test_para_escribir.csv.
   2. Aplique noise.py a train/val y guarde también el texto sin ruido en un CSV
      intermedio (no en el JSONL) para poder hacer la ablación con/sin ruido.
   3. Divida el pool Banking77 + suplemento en train/val 80/20 POR FAMILIA con
      semilla 42, estratificando por label y language. El test es aparte.
   4. Genere ml/intent/data/frases.jsonl, train.jsonl, val.jsonl y test.jsonl con
      el formato de ml/intent/labeling_guide.md 1.2 (id con prefijo b/s/t, source,
      source_ref, noise, split).
   5. FALLE con un mensaje claro si: una familia aparece en dos splits; hay alguna
      frase origin llm o externo_traducido en test; hay textos duplicados
      (normalizados); hay valores fuera de los permitidos; o alguna frase de test
      tiene similitud coseno TF-IDF > 0,9 con alguna de train/val (reporta los pares).
   6. Imprima tablas de conteos por split × label × language y por source × origin.
Córrelo y muéstrame la salida. Agrégalo al Makefile como "make dataset".
```

- [X] `make dataset` corre sin errores

---

## Paso 10 · Medir el acuerdo entre personas (kappa) (~1 h, necesitas a otra persona)

**Qué es:** comprobar que otra persona pone las mismas etiquetas que tú.

**Aquí sí necesitas a alguien más del equipo, unos 30–40 min.** El kappa mide si **dos personas** coinciden. No vale que Claude sea la segunda persona, porque tradujo y generó parte del set. No hace falta que esa persona sepa portugués: si una frase no se entiende, eso también es un dato.

**Escríbele a Claude:**

```
Crea ml/intent/kappa/muestra_para_etiquetar.csv con 100 frases al azar de
ml/intent/data/frases.jsonl (semilla 42), estratificadas por label y con al
menos 30 de Banking77 y 20 de test, con columnas id, text, label_persona2 (vacía).
Sin la etiqueta original ni la fuente. Guarda aparte
ml/intent/kappa/muestra_respuestas.csv con id, label y source.
```

**Qué haces tú:**

1. Mándale `muestra_para_etiquetar.csv` y `ml/intent/labeling_guide.md` a la persona.
2. Que llene `label_persona2` **sin preguntarte nada y sin ver tus etiquetas**.
3. Cuando te lo devuelva, guárdalo en la misma carpeta.

**Luego escríbele a Claude:**

```
Ya tengo ml/intent/kappa/muestra_para_etiquetar.csv lleno. Crea
ml/intent/kappa/compute_kappa.py que calcule el kappa de Cohen (sklearn) entre
la etiqueta original y label_persona2, en total y por source, muestre la matriz
de confusión y liste los desacuerdos. Córrelo y explícame el resultado en
palabras simples.
```

**Si hay desacuerdos:** revísenlos juntos y decidan la etiqueta correcta con las reglas. Si ninguna regla alcanza, **agreguen una regla** a `labeling_guide.md` y suban la versión a 1.3. Después:

```
Corrige en las fuentes (b77_seleccion.csv / suplemento_llm.csv /
test_para_escribir.csv) las etiquetas que decidimos cambiar: [pega la lista].
Si una regla nueva afecta a otras frases que no estaban en la muestra, búscalas
y muéstramelas antes de cambiarlas. Vuelve a correr make dataset.
```

- [X] Muestra lista (`ml/intent/kappa/`, 29-sep)
- [ ] Kappa calculado: ______ (Banking77: ______ · test: ______) · **Pospuesto (29-sep):** falta la segunda persona. Ver "Pendientes".
- [ ] Desacuerdos resueltos (y guía actualizada si hizo falta)

---

## Paso 11 · Documentar (20 min)

**Qué es:** dejar por escrito lo que hiciste. Esto vale puntos directos en "Rationale y documentación" y en "Machine Learning".

**Escríbele a Claude:**

```
Con la salida de make dataset y el kappa:
1. Crea ml/intent/data_report.md con: las tres fuentes (Banking77 filtrado,
   traducido con Claude y re-etiquetado con nuestras reglas, citando el paper y la
   licencia CC-BY-4.0; suplemento generado con Claude y revisado; test generado con
   ChatGPT a partir del plan de familias y revisado por el equipo, con PT/mix
   traducido con Claude, origin llm_externo), el mapeo de clases y cuántas frases se
   re-etiquetaron, el esquema de ruido y sus proporciones reales, tablas por
   split × label × language × origin, el kappa (total y por fuente) y cómo se
   resolvieron los desacuerdos, y limitaciones: Banking77 viene de un neobanco
   británico (otro dominio), el portugués es traducido y no nativo, el test no está
   escrito a mano sino generado con ChatGPT (otro autor que el suplemento, pero
   con el estilo limpio de un LLM: puede sobrestimar el desempeño con clientes
   reales; pendiente reemplazarlo por un test escrito a mano), val sale de la misma distribución que train (el umbral puede
   quedar optimista en test).
2. En docs/decisions.md marca D4.1 como "Reemplazada por Dx.y" (no la borres) y
   agrega la nueva decisión con la siguiente numeración libre de la Fase 4, con
   el formato del archivo: contexto, alternativas (A: todo escrito por el equipo,
   B: todo generado con IA, C: solo Banking77 traducido, D: modelo preentrenado de
   Banking77, E: híbrido), decisión (E), por qué y cómo validamos (kappa > 0,8 y la
   ablación de fuentes en la 4.2). En la decisión, di que el test se generó
   con ChatGPT (origin llm_externo) por falta de tiempo, que es una limitación y
   que queda pendiente un test escrito a mano. Actualiza el índice.
3. En docs/roadmap_fases_1_a_8.md, sección 4.1, actualiza el origen y el tamaño
   del set para que coincidan con lo que hicimos.
```

- [X] `data_report.md` listo (kappa como pendiente en la sección 5)
- [X] Decisión nueva en `decisions.md` (D4.2) y D4.1 marcada como reemplazada
- [X] Roadmap 4.1 actualizado

---

## Paso 12 · Subir a GitHub (5 min)

**Escríbele a Claude:**

```
Revisa git status y muéstrame qué archivos se van a subir para la Fase 4.1.
Verifica que /data/external/banking77.csv NO esté incluido. Haz commit.
```

Luego, desde tu terminal: `git pull` y `git push` (Claude no tiene tus credenciales).

- [ ] Subido. Avísale al equipo: "Set de intenciones listo: X frases (train/val/test = …), kappa = Y".

---

## Pendientes

- [ ] **Kappa (Paso 10).** Pospuesto el 29-sep por falta de tiempo. La muestra ya está en `ml/intent/kappa/` (100 frases, semilla 42). Cuando alguien la etiquete, seguir el Paso 10 desde "Luego escríbele a Claude" y actualizar la sección 5 de `data_report.md` y la validación de D4.2.
- [ ] **Test escrito a mano.** El test actual (`t001`–`t050`) lo generó ChatGPT (`origin: llm_externo`). Si hay tiempo, reescribirlo a mano con el mismo `plan_familias.md` (o al menos las semillas), volver a traducir PT/mix, marcarlo `equipo` / `equipo_traducido` y quitar la limitación de `data_report.md` y de `decisions.md`. Si un candidato de la 4.2 es un modelo de OpenAI, esto pasa a ser obligatorio.

---

## Qué sigue (Fase 4.2, no es parte de esta guía)

Con el set listo se entrenan y comparan los candidatos en **el mismo test**. Con las nuevas fuentes conviene agregar:

- **Ablación de fuentes:** el mismo modelo entrenado con (a) solo Banking77, (b) solo suplemento y (c) ambos. Muestra con evidencia por qué elegimos el híbrido.
- **Ablación de ruido:** con y sin `noise.py` en train.
- **Candidatos preentrenados:** un clasificador de Banking77 ya entrenado (con traducción al inglés y mapeo de clases) y un modelo zero-shot multilingüe (NLI). Son baselines de "lo que ya existe".

**Antes de ver el test** hay que escribir el criterio de selección. La guía está en `docs/Rol B - ML/guia_fase_4_2_clasificador.md`.

---

## Si te trabas

| Te pasa esto                 | Escríbele a Claude                                                                                      |
| :--------------------------- | :------------------------------------------------------------------------------------------------------- |
| Un error en la terminal      | "Me salió este error, explícamelo y arréglalo: [pega el error completo]"                              |
| No sabes qué etiqueta poner | "¿Qué etiqueta lleva esta frase según labeling_guide.md 1.2 y por qué?: [frase]"                     |
| No sabes si vas bien         | "Revisa en qué paso de docs/Rol B - ML/guia_fase_4_1_etiquetado.md voy según los archivos que existen" |
| Algo de git se ve raro       | "Explícame qué muestra git status y qué debería hacer"                                               |

---

## Decisiones ya tomadas (28-sep, v2)

1. **Fuentes:** train/val = Banking77 (filtrado, traducido y re-etiquetado) + suplemento generado con Claude. Test = escrito por el equipo. Ninguna frase de Banking77 ni del suplemento entra al test.
2. **Por qué no todo generado ni todo Banking77:** todo generado con una sola IA hace que el modelo aprenda su estilo y es menos creíble. Banking77 solo no tiene `estado_disputa` ni `ambiguo`, está en inglés y viene de otro dominio (neobanco británico). El híbrido cubre ambos huecos.
3. **Traducción:** siempre con Claude, nunca con Gemini (es candidato en la 4.2). Cada frase de Banking77 se traduce a un solo idioma. Se declara como limitación que el portugués no es nativo.
4. **Ruido:** lo agrega un script con semilla fija y se registra por frase. El test no lleva ruido artificial.
5. **Quién hace el trabajo:** tú haces todo el set con Claude. La única excepción es el kappa (Paso 10): ahí necesitas a otra persona del equipo durante 30–40 min.
