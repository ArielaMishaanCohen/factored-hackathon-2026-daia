# Guía paso a paso · Fase 4.2 · Elegir el clasificador de intención

**Dueño:** B · **Plan:** `docs/roadmap_fases_1_a_8.md`, sección 4.2 · **Datos:** `ml/intent/data/` (D4.2, `ml/intent/data_report.md`)

> Cómo usar esta guía: igual que la de la 4.1. Ve paso por paso, en orden. Cada paso dice **qué es**, **qué haces tú** y **qué le escribes a Claude** (en un bloque que puedes copiar y pegar). Marca la casilla `[x]` al terminar. Si algo sale raro, pégale a Claude el error completo.

---

## Paso 0 · Entender qué estamos haciendo (lee esto una vez, 5 min)

Ya tenemos el set etiquetado (4.1). Ahora hay que **entrenar varios clasificadores, compararlos de forma justa y elegir uno**, con un **umbral de abstención** (τ_intención): si el modelo no está seguro, el bot no actúa y le pregunta al cliente.

### Qué sale del modelo

El modelo devuelve **una de 5 intenciones** y una confianza de 0 a 1 (`docs/design.md`, sección 2):

`cargo_no_reconocido` · `cobro_incorrecto` · `tarjeta_comprometida` · `estado_disputa` · `fuera_de_alcance`

`ambiguo` **no es una salida del modelo**. Esas frases sirven para medir la abstención: lo correcto con "tengo un problema con mi tarjeta" es que la confianza quede **bajo τ** y el bot pregunte.

### Los candidatos (todos se evalúan en el mismo test)

| # | Modelo                                                             | Por qué está                                                    | ¿Obligatorio? |
| :-: | :----------------------------------------------------------------- | :---------------------------------------------------------------- | :-------------: |
| 0 | Clase mayoritaria                                                  | Piso                                                              |       Sí       |
| 1 | Reglas por palabras clave ES/PT                                    | Lo que haría un banco sin ML                                     |       Sí       |
| 2 | TF-IDF (palabras + n-gramas de caracteres) + regresión logística | Baseline clásico; los n-gramas de caracteres aguantan typos y PT |       Sí       |
| 3 | Embeddings multilingües + regresión logística                   | Candidato principal                                               |       Sí       |
| 4 | Gemini zero-shot con salida JSON                                   | Referencia de "solo LLM", con costo y latencia                    |       Sí       |
| 5 | Clasificador de Banking77 ya entrenado (traduciendo al inglés)    | "Lo que ya existe"                                                | Si sobra tiempo |
| 6 | Zero-shot multilingüe (NLI)                                       | "Lo que ya existe", sin entrenar                                  | Si sobra tiempo |

### Métricas

- **macro-F1** sobre las 5 clases (las clases están desbalanceadas; el accuracy engaña). También F1 por clase, por idioma (ES, PT, mezcla) y matriz de confusión.
- **Abstención:** para cada umbral, **cobertura** (% de frases que el bot contesta) y **precisión** (% de las contestadas que acierta; si contesta una frase `ambiguo`, cuenta como error). Con eso se dibuja la curva cobertura vs. precisión.
- **Latencia** por frase y **costo** por 1.000 frases.

### Tres reglas de oro (el jurado las va a revisar)

1. **El test se mira una sola vez, al final** (Paso 9). Todo lo que se ajusta (hiperparámetros, qué modelo gana, τ) se decide en **val**. Si miras el test antes y cambias algo, el número del test deja de valer.
2. **El criterio de selección se escribe y se sube a git antes de correr nada** (Paso 2). La fecha del commit es la prueba.
3. **Cada corrida deja un registro** en `ml/intent/runs/` (parámetros, versión de los datos, métricas). Así cualquier número de la tabla final se puede rastrear.

### Qué vas a entregar al final de la 4.2

- [ ] `ml/intent/criterio_seleccion.md` (subido **antes** de ver el test)
- [ ] `ml/intent/runs/*.json` (una por corrida)
- [ ] Tabla comparativa de candidatos en val y en test, por idioma
- [ ] Ablaciones de fuentes y de ruido
- [ ] Modelo elegido en `ml/intent/model/`, `make train` reproducible
- [ ] `tau_intencion` calibrado en `config/policy.yaml`
- [ ] `ml/intent/model_card.md`
- [ ] Decisión D4.3 en `docs/decisions.md`
- [ ] Clasificador conectado al backend detrás de `understand()`

### Calendario sugerido

| Cuándo                         | Pasos                                               | Tu tiempo                 |
| :------------------------------ | :-------------------------------------------------- | :------------------------ |
| Martes en la tarde              | 1 a 5 (criterio, código común, baselines, TF-IDF) | ~1,5 h                    |
| Martes en la noche              | 6 y 7 (embeddings y Gemini)                         | ~1,5 h (mucho es esperar) |
| Miércoles en la mañana        | 8 a 11 (elegir, τ, test, ablaciones)               | ~1,5 h                    |
| Miércoles antes del checkpoint | 12 a 14 (integrar, documentar, subir)               | ~1 h                      |

---

## Paso 1 · Preparar el entorno (10 min)

**Qué es:** instalar lo que falta. Para los embeddings usamos **`fastembed`** (corre con ONNX, sin PyTorch), porque el modelo que gane tiene que caber en la imagen del backend (roadmap 4.2, nota de deploy).

**Qué haces tú:** revisa que en `.env` estén `GEMINI_API_KEY` y `GEMINI_MODEL` (el ID exacto del modelo, p. ej., un "Flash" vigente). Si `GEMINI_MODEL` está vacío, decide cuál usar con el equipo: es el mismo que va a usar el bot (D1.2).

**Escríbele a Claude:**

```
Paso 1 de docs/Rol B - ML/guia_fase_4_2_clasificador.md. Agrega a
requirements.txt fastembed, joblib y el SDK oficial de Gemini (google-genai),
instálalos en .venv y verifica que fastembed pueda bajar y correr un modelo
multilingüe chico (p. ej., sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
o intfloat/multilingual-e5-small) con dos frases de prueba, una en ES y otra en PT.
Dime cuánto pesa el modelo en disco. No instales torch.
```

- [X] Dependencias instaladas y `fastembed` probado
- [X] `GEMINI_MODEL` fijado:`gemini-3.5-flash`

---

## Paso 2 · Escribir el criterio de selección ANTES de ver el test (15 min)

**Qué es:** dejar por escrito, antes de entrenar, cómo vamos a elegir. Si lo decidimos después de ver los números, parece (y es) hecho a la medida.

**Escríbele a Claude:**

```
Paso 2 de la guía de la 4.2. Crea ml/intent/criterio_seleccion.md con:
1. Clases de salida: las 5 de design.md; ambiguo no se entrena en la variante
   principal y en evaluación cuenta como "debería abstenerse".
2. Métricas: macro-F1 de 5 clases (sin abstención, sin las frases ambiguo), F1
   por clase e idioma, y cobertura vs. precisión con abstención (ambiguo
   contestado = error). Latencia p50 por frase y costo por 1.000 frases.
3. Selección: gana el mejor macro-F1 en val. Si la diferencia con el siguiente
   es < 2 puntos, gana el más barato y rápido. Sesgo conocido: val sale de la
   misma distribución que train, lo que favorece a los modelos entrenados frente
   a Gemini zero-shot; se declara, no se corrige.
4. Umbral: τ_intención se elige en val como el τ con mayor cobertura que da
   precisión ≥ 95 %. Si ningún τ llega a 95 %, el que dé la mayor precisión con
   cobertura ≥ 50 %, y se declara.
5. El test se evalúa una sola vez, con el modelo y el τ ya fijados, y se
   reportan todos los candidatos. Nada se cambia después de ver el test; si
   algo se cambia, se declara y se reporta el número anterior también.
6. Ablaciones (fuentes y ruido): se corren con el modelo ya elegido y se
   reportan en val y test; no cambian la elección.
Después haz commit solo de ese archivo con el mensaje
"4.2: criterio de selección (antes de ver test)".
```

**Qué haces tú:** léelo. Si algo no te convence, cámbialo **ahora**; después ya no se puede.

- [ ] Criterio escrito y con commit (hash: ________)

---

## Paso 3 · Código común: datos, métricas y registro de corridas (15 min)

**Qué es:** una sola forma de cargar los datos, calcular las métricas y guardar cada corrida, para que todos los candidatos se midan igual. El test queda "bajo llave": solo se puede evaluar con una bandera explícita.

**Escríbele a Claude:**

```
Paso 3 de la guía de la 4.2. Crea ml/intent/evaluate.py con:
- load_split(nombre, fuentes=None, sin_ruido=False): lee ml/intent/data/*.jsonl;
  permite filtrar por source y usar el texto de data/sin_ruido.csv.
- Una interfaz común para candidatos: fit(textos, labels) y predict_proba(textos)
  que devuelve probabilidades para las 5 clases.
- evaluar(candidato, split): macro-F1 de 5 clases, F1 por clase, por idioma y
  por source, matriz de confusión, curva cobertura-precisión (ambiguo contestado
  = error) y latencia p50 por frase.
- elegir_tau(curva): según ml/intent/criterio_seleccion.md.
- guardar_run(...): escribe ml/intent/runs/<fecha>_<candidato>_<split>.json con
  parámetros, md5 de frases.jsonl, commit de git, métricas y τ.
- El split "test" solo se puede evaluar si se pasa --test; si no, error claro.
Agrega tests cortos en tests/ para las métricas de abstención con un ejemplo a
mano. Corre pytest.
```

- [ ] `evaluate.py` listo y tests en verde

---

## Paso 4 · Baselines 0 y 1: mayoritaria y reglas (15 min)

**Qué es:** el piso. Si un modelo no le gana a unas reglas de palabras clave, no vale la pena.

**Ojo con las reglas:** tienen que salir de la guía de etiquetado y del sentido común, **no** de mirar frases de val o test. Si Claude las ajusta mirando errores, eso es entrenar a mano.

**Escríbele a Claude:**

```
Paso 4 de la guía de la 4.2. En ml/intent/candidates/ crea:
- mayoritaria.py: predice siempre la clase más frecuente de train.
- reglas.py: palabras clave ES/PT escritas a partir de las reglas de
  ml/intent/labeling_guide.md (en ese orden de precedencia) y de sinónimos
  comunes, sin mirar frases de val ni test. Confianza: 0,9 si pega una regla,
  0,3 si no (cae en fuera_de_alcance). Puedes partir de backend/app/nlu/stub.py.
Evalúa los dos en val con evaluate.py, guarda los runs y muéstrame la tabla.
```

- [ ] Baselines en val: mayoritaria macro-F1 ____ · reglas ____

---

## Paso 5 · Candidato 2: TF-IDF + regresión logística (15 min)

**Qué es:** el baseline clásico de ML. Rápido, liviano y difícil de superar en sets chicos.

**Escríbele a Claude:**

```
Paso 5 de la guía de la 4.2. Crea ml/intent/candidates/tfidf_lr.py: TF-IDF de
palabras (1-2) + n-gramas de caracteres (2-5, char_wb) + LogisticRegression
(class_weight balanced). Entrena con train sin ambiguo. Busca C en {0,1, 1, 10}
eligiendo por macro-F1 en val. Guarda un run por valor de C y muéstrame la
tabla, la matriz de confusión en val y los 15 errores con más confianza.
```

**Qué haces tú:** mira los errores. ¿Son errores del modelo o etiquetas dudosas? Si ves etiquetas mal puestas, **anótalas** en vez de corregirlas ahora (se corrigen con el kappa, Paso 10 de la 4.1).

- [ ] TF-IDF en val: macro-F1 ____ (C = ____)

---

## Paso 6 · Candidato 3: embeddings multilingües + regresión logística (30 min, mucho es esperar)

**Qué es:** convertir cada frase en un vector que captura el significado (en ES y PT a la vez) y entrenar una regresión logística encima. Es el candidato principal.

**Escríbele a Claude:**

```
Paso 6 de la guía de la 4.2. Crea ml/intent/candidates/embeddings_lr.py con
fastembed + LogisticRegression (class_weight balanced). Prueba dos modelos de
embeddings multilingües chicos que soporte fastembed (uno tipo MiniLM
multilingüe y uno tipo multilingual-e5-small, con el prefijo "query: " si el
modelo lo pide). Cachea los embeddings en disco (fuera de git) para no
recalcularlos. Busca C en {0,1, 1, 10} por macro-F1 en val.
Variante extra: el mejor de los dos entrenado con 6 clases (incluyendo ambiguo),
donde predecir ambiguo = abstenerse. Compara su curva cobertura-precisión en val
con la del modelo de 5 clases.
Guarda los runs y muéstrame la tabla con latencia p50 y tamaño en disco.
```

- [ ] Embeddings en val: macro-F1 ____ (modelo ________, C = ____)
- [ ] ¿5 o 6 clases? ________ (decidido en val)

---

## Paso 7 · Candidato 4: Gemini zero-shot (30 min, mucho es esperar)

**Qué es:** pedirle a Gemini que clasifique la frase sin entrenarlo, con salida JSON. Es la referencia de "solo LLM". Seguramente acierta bien, pero cuesta dinero, tarda más y depende de la red.

**Por qué es justo:** ninguna frase del set fue generada ni traducida con Gemini (D4.2), así que no "se conoce" las respuestas.

**Escríbele a Claude:**

```
Paso 7 de la guía de la 4.2. Crea prompts/intent_zeroshot_v1.txt con las
definiciones de las 5 intenciones y las reglas de labeling_guide.md, pidiendo
JSON {"intent": ..., "confidence": 0-1}, donde intent puede ser también
"ambiguo" (= abstenerse). Crea ml/intent/candidates/gemini_zeroshot.py con el
modelo de GEMINI_MODEL, temperatura 0, JSON validado, 1 reintento, caché de
respuestas en disco (fuera de git) y control de ritmo para la capa gratuita.
Registra tokens, costo estimado (con el precio del día, anotando la fuente) y
latencia. Evalúa en val y guarda el run. Si la API falla en alguna frase,
cuéntala como error, no la saltes.
```

**Qué haces tú:** si la cuota gratuita no alcanza para las 507 frases de val, dile a Claude que evalúe una muestra estratificada de val y que lo declare en el run.

- [ ] Gemini en val: macro-F1 ____ · costo por 1.000 frases ____ · latencia p50 ____

---

## Paso 8 · (Opcional) Candidatos 5 y 6: modelos ya existentes (~45 min)

**Qué es:** mostrar que comparamos con lo que ya existe. Necesitan PyTorch, así que **se corren aparte** (otro entorno o Colab) y **no** entran a la imagen. Solo si vas bien de tiempo el miércoles.

**Escríbele a Claude:**

```
Paso 8 de la guía de la 4.2. En un entorno aparte (no en .venv ni en
requirements.txt), evalúa en val:
5. un clasificador de Banking77 ya entrenado de Hugging Face, traduciendo las
   frases al inglés (dime con qué y declaralo) y mapeando sus 77 clases con
   ml/intent/b77_mapeo.csv;
6. un modelo zero-shot NLI multilingüe con hipótesis en español para las 5
   clases.
Guarda los runs en el mismo formato que evaluate.py.
```

- [ ] Hecho · o [ ] Saltado (se declara en `model_card.md`)

---

## Paso 9 · Elegir el modelo y τ en val (15 min)

**Qué es:** aplicar el criterio del Paso 2, tal cual está escrito.

**Escríbele a Claude:**

```
Paso 9 de la guía de la 4.2. Con los runs de val en ml/intent/runs/, arma la
tabla de candidatos (macro-F1, F1 por idioma, latencia, costo) y aplica
ml/intent/criterio_seleccion.md al pie de la letra: dime cuál gana y por qué.
Con el ganador, dibuja la curva cobertura-precisión en val (guárdala en
ml/intent/figures/), elige τ_intención según el criterio y dime qué cobertura
y precisión da, y qué % de las frases ambiguo de val quedan abstenidas.
No toques el test.
```

- [ ] Modelo elegido: ________________
- [ ] τ_intención = ____ (val: cobertura ____ %, precisión ____ %)

---

## Paso 10 · Abrir el test, una sola vez (10 min)

**Qué es:** el examen final. Se corren **todos** los candidatos con lo que ya quedó fijado, y se reporta lo que salga, aunque no guste.

**Escríbele a Claude:**

```
Paso 10 de la guía de la 4.2. Evalúa en test (con --test) todos los candidatos
con sus parámetros ya elegidos en val, y el ganador con el τ ya fijado. Arma la
tabla final: macro-F1 total y por idioma (es, pt, mix), F1 por clase, cobertura
y precisión con τ, % de ambiguo abstenidas, latencia y costo. Guarda la matriz
de confusión del ganador en ml/intent/figures/ y lista sus errores en test.
No cambies nada del modelo ni de τ.
```

**Qué haces tú:** si el test sale mucho peor que val, **no lo arregles**: es justo lo que el `data_report.md` anticipa (val es de la misma distribución que train). Se explica en el model card.

- [ ] Test: macro-F1 ____ (ES ____ · PT ____ · mix ____) · cobertura ____ % · precisión ____ %

---

## Paso 11 · Ablaciones: fuentes y ruido (20 min)

**Qué es:** demostrar con números dos decisiones de la 4.1: que el set híbrido sirve más que cada fuente sola, y que el ruido de chat ayuda.

**Escríbele a Claude:**

```
Paso 11 de la guía de la 4.2. Con el modelo ganador y sus parámetros fijos,
entrena y evalúa en val y test:
- Fuentes: (a) solo Banking77, (b) solo suplemento, (c) ambos.
- Ruido: (c) con ruido vs. (c) sin ruido (texto de data/sin_ruido.csv).
Guarda los runs y arma una tabla con macro-F1 total y por idioma. Dime en
palabras simples qué muestra cada ablación.
```

- [ ] Ablación de fuentes: B77 ____ · supl. ____ · ambos ____
- [ ] Ablación de ruido: con ____ · sin ____

---

## Paso 12 · Guardar el modelo e integrarlo al backend (30 min)

**Qué es:** dejar el ganador como un archivo liviano, con `make train` reproducible, y conectarlo al bot. La extracción con Gemini (monto, fecha, comercio) es de la 4.3; aquí solo se cambia **la intención y la confianza**.

**Escríbele a Claude:**

```
Paso 12 de la guía de la 4.2.
1. Crea ml/intent/train.py (make train): entrena el ganador con train+val
   (parámetros fijos), guarda el artefacto en ml/intent/model/ con un
   model_version (fecha + md5 de los datos) y dime cuánto pesa.
2. Pon el τ elegido en config/policy.yaml (intent.tau_intencion) con un
   comentario de dónde sale.
3. Crea backend/app/nlu/classifier.py que cargue el modelo una sola vez y
   devuelva (intent, confidence). En backend/app/nlu/, haz que understand()
   use el clasificador para intent, intent_confidence y abstain, y deje el
   resto como está en el stub hasta la 4.3. Si el modelo no carga, que caiga al
   stub y lo registre. Agrega lo necesario a backend/requirements.txt, sin torch.
4. Agrega tests y corre pytest. Prueba 5 frases a mano (ES, PT, mezcla, una
   ambigua y una fuera de alcance) y muéstrame qué devuelve.
```

**Ojo:** reentrenar con train+val cambia un poco el modelo respecto al evaluado. Es práctica normal; se declara en el model card. Si prefieres no hacerlo, dile a Claude que use el modelo entrenado solo con train.

- [ ] `make train` corre y deja `ml/intent/model/`
- [ ] `tau_intencion` en `policy.yaml`
- [ ] `understand()` usa el clasificador; tests en verde
- [ ] Avisarle a C (rol backend) que cambió el NLU

---

## Paso 13 · Documentar (20 min)

**Escríbele a Claude:**

```
Paso 13 de la guía de la 4.2. Con los runs, las tablas y las figuras:
1. Crea ml/intent/model_card.md: uso previsto, datos (resumen de
   data_report.md, citando Banking77 CC-BY-4.0), candidatos y tabla comparativa
   en val y test por idioma, criterio de selección (link al commit del Paso 2),
   modelo elegido y τ con su curva, ablaciones, análisis de errores, latencia,
   tamaño y costo, y limitaciones (las de data_report.md, el kappa pendiente,
   el reentrenamiento con train+val, y los candidatos saltados si los hubo).
2. En docs/decisions.md reemplaza la fila "D4.x · Clasificador elegido y umbral
   de abstención" por D4.3 con el formato del archivo: contexto, alternativas
   (los candidatos), decisión, por qué (con los números de val y test) y cómo
   validamos (en la Fase 6, resolución automática segura y tasa de aclaraciones).
   Actualiza el índice.
3. En docs/roadmap_fases_1_a_8.md, sección 4.2, marca lo que ya está en
   "Hecho cuando".
```

- [ ] `model_card.md` listo
- [ ] D4.3 en `decisions.md`
- [ ] Roadmap actualizado

---

## Paso 14 · Subir a GitHub (5 min)

**Escríbele a Claude:**

```
Revisa git status y muéstrame qué archivos se van a subir para la Fase 4.2.
Verifica que no se suban cachés de embeddings ni de Gemini, ni .env, ni nada
de data/. Haz commit.
```

Luego, desde tu terminal: `git pull` y `git push`.

- [ ] Subido. Avísale al equipo: "Clasificador listo: <modelo></modelo>, macro-F1 test = X (ES Y · PT Z), τ = W".

---

## Pendientes que vienen de la 4.1

- [ ] **Kappa** (Paso 10 de la 4.1). Si al hacerlo cambian etiquetas, hay que correr `make dataset`, repetir los Pasos 9 a 13 y reportar los números nuevos junto con los anteriores.
- [ ] **Test escrito a mano.** No es obligatorio mientras ningún candidato sea de OpenAI (si agregas uno, sí lo es).

---

## Si te trabas

| Te pasa esto                     | Escríbele a Claude                                                                                        |
| :------------------------------- | :--------------------------------------------------------------------------------------------------------- |
| Un error en la terminal          | "Me salió este error, explícamelo y arréglalo: [pega el error completo]"                                |
| La cuota de Gemini se acaba      | "Gemini devuelve error de cuota en el Paso 7. Baja el ritmo y sigue desde la caché"                       |
| No sabes si vas bien             | "Revisa en qué paso de docs/Rol B - ML/guia_fase_4_2_clasificador.md voy según los archivos que existen" |
| Un número se ve demasiado bueno | "Este resultado se ve demasiado bueno: [pega]. Revisa si hay fuga entre train y el split evaluado"         |

---

## Decisiones ya tomadas (29-sep)

1. **5 clases de salida + abstención**, como `design.md`. `ambiguo` solo mide la abstención (salvo que la variante de 6 clases gane en val, Paso 6).
2. **Todo se decide en val**; el test se abre una vez (Paso 10).
3. **Sin PyTorch en la imagen:** embeddings con `fastembed` (ONNX). Los candidatos 5 y 6, si se hacen, corren aparte.
4. **Gemini se evalúa como candidato** porque no participó en generar ni traducir el set. Por la misma razón, ninguna frase nueva del set puede hacerse con Gemini.
5. **Kappa pospuesto:** la 4.2 avanza con las etiquetas actuales; si el kappa cambia etiquetas, se repite la evaluación.
