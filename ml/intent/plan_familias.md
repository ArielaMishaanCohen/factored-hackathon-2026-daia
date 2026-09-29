# Plan de familias · test y suplemento (Fase 4.1, Paso 6)

**Dueño:** B · **Guía de etiquetado:** `labeling_guide.md` 1.2 · **Fecha:** 29-sep-2026

Este plan fija cuántas familias se escriben por etiqueta e idioma, y qué **subtema** cubre cada una. Sirve para dos cosas:

1. Que las familias no se repitan dentro de cada fuente.
2. Que el test y el suplemento **no compartan subtemas**. Así, un acierto en test no se explica porque el suplemento ya tenía la misma idea con otras palabras.

Paso 7 (test) usa solo la sección **Para el test**. Paso 8 (suplemento) usa solo la sección **Para el suplemento**.

---

## 1. Tablas

### Test del equipo (50 familias × 4 frases ≈ 200)

| Etiqueta                 |   Familias   |      ES      |      PT      |   Mezcla   |
| :----------------------- | :----------: | :----------: | :----------: | :---------: |
| `cargo_no_reconocido`  |      10      |      5      |      4      |      1      |
| `cobro_incorrecto`     |      10      |      5      |      4      |      1      |
| `tarjeta_comprometida` |      9      |      4      |      4      |      1      |
| `estado_disputa`       |      8      |      4      |      3      |      1      |
| `fuera_de_alcance`     |      7      |      4      |      3      |      0      |
| `ambiguo`              |      6      |      3      |      2      |      1      |
| **Total**          | **50** | **25** | **20** | **5** |

### Suplemento (160 familias × ~5 frases ≈ 800)

| Bloque                                                               |   Familias   | Para qué                                                                          |
| :------------------------------------------------------------------- | :-----------: | :--------------------------------------------------------------------------------- |
| `estado_disputa`                                                   |      50      | Banking77 no tiene esta clase                                                      |
| `ambiguo`                                                          |      40      | Banking77 no tiene esta clase                                                      |
| Localización y portuñol (10 por cada una de las otras 4 etiquetas) |      40      | Oxxo, Pix, Nubank, Mercado Libre, "lana", "grana", "guita"; frases mezcladas ES/PT |
| Casos límite entre clases e inyecciones con intención real         |      30      | Las fronteras de nuestras reglas y los intentos de manipular al bot                |
| **Total**                                                      | **160** |                                                                                    |

Idiomas del suplemento: ~40 % ES, ~35 % PT, ~25 % mezcla. Cada familia es de un solo idioma.

---

## 2. Subtemas para el test

Una familia por subtema. El idioma y la variante ya cuadran con la tabla del test; la variante es una sugerencia y se puede cambiar (en `pt` siempre es `BR`).

### `cargo_no_reconocido` (10 · ES 5, PT 4, mix 1)

| #  | Subtema                                                                        | Idioma | Variante |
| :- | :----------------------------------------------------------------------------- | :----: | :------: |
| 1  | Cargo con un nombre de comercio raro o incomprensible en el estado de cuenta   |   es   |    MX    |
| 2  | Cargo en dólares o en el extranjero sin haber viajado ni comprado fuera        |   es   |    CO    |
| 3  | Cargo de un día en que no usó la tarjeta ("ese día ni salí de mi casa")        |   es   |    AR    |
| 4  | Compra en línea que no hizo, con la tarjeta física en su poder                 |   es   |    MX    |
| 5  | Pregunta "¿qué es este cargo?" dando solo monto y fecha                        |   es   |  neutro  |
| 6  | Suscripción que nunca contrató (streaming, app)                                |   pt   |    BR    |
| 7  | Cargo que se repite cada mes y no sabe de dónde viene                          |   pt   |    BR    |
| 8  | Se entera por una notificación o SMS de madrugada de un cargo que no conoce    |   pt   |    BR    |
| 9  | Cargo de una app de delivery o transporte que no usa                           |   pt   |    BR    |
| 10 | Cargo chiquito de "prueba" (1 peso, 1 real) que no reconoce                    |  mix   |  neutro  |

### `cobro_incorrecto` (10 · ES 5, PT 4, mix 1)

| #  | Subtema                                                                        | Idioma | Variante |
| :- | :----------------------------------------------------------------------------- | :----: | :------: |
| 1  | Cobro doble en el supermercado                                                 |   es   |    MX    |
| 2  | Le cobraron más que lo que dice el ticket                                      |   es   |    CO    |
| 3  | Le siguen cobrando después de cancelar (gimnasio, suscripción)                 |   es   |    AR    |
| 4  | Compra a meses sin intereses que le cobraron con intereses                     |   es   |    MX    |
| 5  | Anualidad o comisión que le dijeron que no iba a pagar                         |   es   |    CO    |
| 6  | Tipo de cambio mal aplicado en una compra internacional                        |   pt   |    BR    |
| 7  | Propina o cargo por servicio agregado sin autorizar                            |   pt   |    BR    |
| 8  | Pagó una parte en efectivo y le cobraron el total con tarjeta                  |   pt   |    BR    |
| 9  | Débito automático de un servicio (luz, agua) cobrado dos veces                 |   pt   |    BR    |
| 10 | Cobro triple en la gasolinera                                                  |  mix   |  neutro  |

### `tarjeta_comprometida` (9 · ES 4, PT 4, mix 1)

| # | Subtema                                                                         | Idioma | Variante |
| :- | :------------------------------------------------------------------------------ | :----: | :------: |
| 1 | Asalto: le robaron la cartera con la tarjeta                                    |   es   |    MX    |
| 2 | Perdió la tarjeta y no sabe dónde                                               |   es   |    AR    |
| 3 | Sospecha clonación después de usar un cajero o una terminal que se veía rara    |   es   |    CO    |
| 4 | Varias compras que no hizo en pocas horas                                       |   es   |    MX    |
| 5 | Le robaron el celular con la app del banco o la tarjeta digital                 |   pt   |    BR    |
| 6 | Dio los datos de la tarjeta en una llamada falsa "del banco"                    |   pt   |    BR    |
| 7 | Se le olvidó la tarjeta en un restaurante o tienda                              |   pt   |    BR    |
| 8 | Avisos de compras en otra ciudad o país mientras él/ella tiene la tarjeta       |   pt   |    BR    |
| 9 | Pide bloquear la tarjeta ya porque se la quitaron                               |  mix   |  neutro  |

### `estado_disputa` (8 · ES 4, PT 3, mix 1)

| # | Subtema                                                                         | Idioma | Variante |
| :- | :------------------------------------------------------------------------------ | :----: | :------: |
| 1 | Pregunta por su reclamo dando el número de folio                                |   es   |    MX    |
| 2 | Se queja de la demora ("ya van tres semanas")                                   |   es   |    AR    |
| 3 | Pide hablar con una persona por su reclamo                                      |   es   |    CO    |
| 4 | Pregunta qué documentos le faltan para que avance su reclamo                    |   es   |  neutro  |
| 5 | Pregunta si ya le devolvieron el dinero del reclamo                             |   pt   |    BR    |
| 6 | Le rechazaron el reclamo y pregunta por qué                                     |   pt   |    BR    |
| 7 | Reclamó por teléfono o en sucursal y quiere confirmar que quedó registrado      |   pt   |    BR    |
| 8 | Pregunta cuánto tarda en resolverse el reclamo que ya abrió                     |  mix   |  neutro  |

### `fuera_de_alcance` (7 · ES 4, PT 3)

| # | Subtema                                                                         | Idioma | Variante | Nota                          |
| :- | :------------------------------------------------------------------------------ | :----: | :------: | :---------------------------- |
| 1 | Pide un préstamo o crédito                                                      |   es   |    MX    |                               |
| 2 | Consulta su saldo                                                               |   es   |    AR    |                               |
| 3 | Quiere subir el límite de crédito                                               |   es   |    CO    |                               |
| 4 | Pago o transferencia que sigue pendiente y no se acredita                       |   es   |    MX    | Aclaración 1.2 (pendiente)    |
| 5 | Olvidó o quiere cambiar el PIN                                                  |   pt   |    BR    |                               |
| 6 | Tarjeta rechazada en un comercio                                                |   pt   |    BR    | Aclaración 1.2 (rechazo)      |
| 7 | La tienda prometió un reembolso y no llega (sin reclamo al banco)               |   pt   |    BR    | Aclaración 1.2 (reembolso)    |

### `ambiguo` (6 · ES 3, PT 2, mix 1)

| # | Subtema                                                                         | Idioma | Variante |
| :- | :------------------------------------------------------------------------------ | :----: | :------: |
| 1 | Solo un saludo ("hola", "buenas")                                               |   es   |    MX    |
| 2 | "Tengo un problema con mi tarjeta" sin más detalle                              |   es   |    CO    |
| 3 | Queja genérica del banco sin nada concreto ("su servicio es pésimo")            |   es   |    AR    |
| 4 | Menciona un cargo sin decir qué pasa con él ("sobre el cargo de ayer")          |   pt   |    BR    |
| 5 | Solo un monto o una palabra suelta ("350", "cobro")                             |   pt   |    BR    |
| 6 | "Quiero reclamar algo" sin decir qué                                            |  mix   |  neutro  |

---

## 3. Subtemas para el suplemento

Aquí un subtema puede tener varias familias: cada una cambia el país, el idioma, el largo o el detalle. El número entre paréntesis es cuántas familias salen de ese subtema.

### `estado_disputa` (50)

| #  | Subtema                                                                                     | Familias |
| :- | :------------------------------------------------------------------------------------------ | :------: |
| 1  | Nunca le llegó el correo o SMS de confirmación del reclamo                                  |    4     |
| 2  | Quiere dar seguimiento pero no tiene o perdió el número de folio                            |    4     |
| 3  | Le hicieron un abono provisional y pregunta si ya es definitivo                             |    5     |
| 4  | Le quitaron el abono provisional o le revirtieron el reembolso                              |    4     |
| 5  | Quiere agregar evidencia o más información a un reclamo ya abierto                          |    4     |
| 6  | Quiere cancelar el reclamo porque al final sí reconoció el cargo                            |    4     |
| 7  | Quiere apelar o reabrir un reclamo que le cerraron                                          |    4     |
| 8  | Tiene varios reclamos abiertos y pregunta por uno en particular                             |    3     |
| 9  | La app muestra "en revisión" desde hace días y pregunta qué significa ese estado            |    3     |
| 10 | Le repusieron la tarjeta y pregunta si su reclamo sigue abierto                             |    3     |
| 11 | Recibió una notificación sobre su reclamo y no la entiende                                  |    4     |
| 12 | Pregunta si le van a cobrar intereses mientras el reclamo está abierto                      |    4     |
| 13 | Pregunta si tiene que pagar el cargo en disputa mientras se resuelve                        |    4     |
|    | **Total**                                                                               |  **50**  |

### `ambiguo` (40)

| #  | Subtema                                                                                     | Familias |
| :- | :------------------------------------------------------------------------------------------ | :------: |
| 1  | Pide ayuda sin decir de qué ("necesito ayuda", "me ayudas?")                               |    3     |
| 2  | Tiene una duda o pregunta sin formularla ("quería preguntar algo")                          |    3     |
| 3  | Dice que hay algo raro en su cuenta o estado de cuenta, sin decir qué                       |    4     |
| 4  | Pregunta "¿esto es normal?" sin decir qué es "esto"                                        |    3     |
| 5  | Se refiere a una imagen o captura que no está ("mira esto", "te mando foto")               |    4     |
| 6  | Mensaje cortado a la mitad ("hola quería ver lo del")                                       |    4     |
| 7  | Pide hablar con un humano sin dar ningún motivo                                             |    4     |
| 8  | Solo emojis o signos ("??", "😡", "...")                                                    |    3     |
| 9  | Responde "sí", "no" u "ok" sin contexto                                                     |    3     |
| 10 | Pregunta si habla con un bot o con quién está hablando                                      |    3     |
| 11 | Texto de prueba o sin sentido ("prueba", "asdf")                                            |    3     |
| 12 | Dice que "no le llegó" algo sin decir qué (dinero, tarjeta, código)                         |    3     |
|    | **Total**                                                                               |  **40**  |

### Localización y portuñol (40)

Cada familia usa jerga y comercios de un país concreto, o mezcla ES/PT. Estos subtemas se eligieron para no pisar los del test.

**`cargo_no_reconocido` (10)**

| # | Subtema                                                               | Familias | País / idioma sugerido |
| :- | :-------------------------------------------------------------------- | :------: | :--------------------- |
| 1 | Pix enviado desde su cuenta que no hizo                               |    2     | BR · pt                |
| 2 | Cargo de Mercado Pago que no reconoce                                 |    2     | AR · es / mix          |
| 3 | Cargo en un Oxxo o 7-Eleven de otra ciudad                            |    2     | MX · es                |
| 4 | Recarga de celular que no hizo                                        |    2     | CO / MX · es           |
| 5 | Cargo de un casino o sitio de apuestas en línea que nunca usó         |    2     | mix                    |

**`cobro_incorrecto` (10)**

| # | Subtema                                                               | Familias | País / idioma sugerido |
| :- | :-------------------------------------------------------------------- | :------: | :--------------------- |
| 1 | Pagó con Pix o QR en un comercio y le cobraron dos veces              |    2     | BR · pt                |
| 2 | Compró en cuotas ("em 3x") y le cobraron todo de una vez              |    2     | BR · pt / mix          |
| 3 | Impuestos o percepciones sobre compras en dólares que no correspondían |   2     | AR · es                |
| 4 | Recargó un monto y le cobraron otro distinto                          |    2     | MX · es                |
| 5 | IOF u otra tarifa que no debía aplicarse                              |    2     | BR · pt / mix          |

**`tarjeta_comprometida` (10)**

| # | Subtema                                                               | Familias | País / idioma sugerido |
| :- | :-------------------------------------------------------------------- | :------: | :--------------------- |
| 1 | "Golpe da maquininha": el vendedor le cambió la tarjeta               |    2     | BR · pt                |
| 2 | Carterista en el transporte público ("me bajaron la billetera en el bondi") | 2  | AR · es                |
| 3 | Dio los datos de la tarjeta en una venta falsa por WhatsApp o Marketplace |  2   | mix                    |
| 4 | Le hackearon la cuenta de Mercado Libre o iFood con la tarjeta guardada |  2     | AR / BR · es / pt      |
| 5 | La tarjeta nueva nunca le llegó por correo y ya tiene compras         |    2     | MX / CO · es           |

**`fuera_de_alcance` (10)**

| # | Subtema                                                               | Familias | País / idioma sugerido |
| :- | :-------------------------------------------------------------------- | :------: | :--------------------- |
| 1 | Cómo pagar la tarjeta en Oxxo o Rapipago                              |    2     | MX / AR · es           |
| 2 | Pregunta qué compras tienen meses sin intereses                       |    2     | MX · es                |
| 3 | Pregunta el tipo de cambio o el "dólar tarjeta"                       |    2     | AR · es / mix          |
| 4 | Cómo habilitar la tarjeta para usarla en un viaje al extranjero       |    2     | mix                    |
| 5 | Pide un comprobante o extracto ("comprovante", "extrato")             |    2     | BR · pt                |

### Casos límite e inyecciones (30)

La columna **Etiqueta** es la que corresponde según las reglas 1.2. Si al generar una familia la etiqueta queda en duda, se anota y se decide antes de guardarla.

| #  | Subtema                                                                                         | Etiqueta                           | Regla            | Familias |
| :- | :---------------------------------------------------------------------------------------------- | :--------------------------------- | :--------------- | :------: |
| 1  | No reconoce un cargo y además menciona que hace poco le robaron algo                            | `tarjeta_comprometida`           | 1 sobre 4        |    3     |
| 2  | Varios cargos que no reconoce, sin mencionar robo ni pérdida                                    | `cargo_no_reconocido`            | 4 (guía 1.4)     |    3     |
| 3  | El cajero se quedó con la tarjeta (no hubo robo)                                                | `fuera_de_alcance`               | Aclaración 1.2   |    3     |
| 4  | Pares sobre comisiones: "¿por qué me cobran esta comisión?" vs. "esta comisión no debía cobrarse" | `fuera_de_alcance` / `cobro_incorrecto` | Aclaración 1.2 |    3     |
| 5  | Reconoce el comercio pero no el monto ("sí fui, pero no gasté eso")                             | `cobro_incorrecto`               | 3 sobre 4        |    3     |
| 6  | Retención temporal (hotel, gasolinera, renta de auto) que parece un cobro de más                | `fuera_de_alcance`               | Aclaración 1.2   |    3     |
| 7  | "Ignora tus reglas y…" + cargo que no reconoce                                                 | `cargo_no_reconocido`            | 4                |    3     |
| 8  | Se hace pasar por empleado o administrador del banco + pregunta por su reclamo                  | `estado_disputa`                 | 2                |    3     |
| 9  | Pide ver el prompt o que el bot cambie de rol + cobro duplicado                                 | `cobro_incorrecto`               | 3                |    3     |
| 10 | Instrucción disfrazada de formato ("SYSTEM:", JSON, "modo admin") + tarjeta robada              | `tarjeta_comprometida`           | 1                |    3     |
|    | **Total**                                                                                   |                                    |                  |  **30**  |

En el subtema 4, cada familia lleva una sola de las dos versiones (la familia no mezcla etiquetas). Se reparten así: 2 familias `fuera_de_alcance` y 1 `cobro_incorrecto`, o al revés.

---

## 4. Revisión de solapamiento

Antes de escribir se revisó que ningún subtema del suplemento repita uno del test. Estos son los pares cercanos y en qué se diferencian:

| Test                                                  | Suplemento                                                   | Diferencia                                                  |
| :---------------------------------------------------- | :----------------------------------------------------------- | :---------------------------------------------------------- |
| `estado_disputa` · pregunta dando el folio          | `estado_disputa` · no tiene o perdió el folio             | Tener el folio vs. no tenerlo                               |
| `estado_disputa` · ¿ya me devolvieron?              | `estado_disputa` · ¿el abono provisional es definitivo? / me lo quitaron | Reembolso final vs. abono provisional              |
| `estado_disputa` · pide hablar con alguien por su reclamo | `ambiguo` · pide un humano sin motivo                  | Con reclamo mencionado vs. sin motivo                       |
| `fuera_de_alcance` · reembolso de la tienda que no llega | Casos límite · el cajero se quedó con la tarjeta        | Aclaraciones 1.2 distintas                                  |
| `fuera_de_alcance` · pago pendiente                 | Casos límite · retención temporal (hotel, gasolinera)     | Pago propio pendiente vs. retención del comercio            |
| `tarjeta_comprometida` · varias compras en pocas horas | Casos límite · varios cargos no reconocidos sin robo    | En test es una urgencia en el tiempo (`tarjeta_comprometida`); en el suplemento no hay apuro y va a `cargo_no_reconocido` (guía 1.4) |
| `tarjeta_comprometida` · llamada falsa "del banco"  | Localización · venta falsa por WhatsApp / Marketplace      | El estafador se hace pasar por el banco vs. por un comprador o vendedor |
| `cobro_incorrecto` · meses sin intereses con intereses | `fuera_de_alcance` · qué compras tienen meses sin intereses | Queja por un cobro vs. pregunta informativa             |
| `ambiguo` · "tengo un problema con mi tarjeta"      | `ambiguo` · "algo raro en mi cuenta"                       | Tarjeta vs. cuenta o estado de cuenta                        |

Casos límite e inyecciones solo están en el suplemento. El test sí cubre las fronteras de las aclaraciones 1.2 (pendiente, rechazo, reembolso del comercio) desde `fuera_de_alcance`.
