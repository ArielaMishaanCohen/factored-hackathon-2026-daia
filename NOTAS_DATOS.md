Existe un data_backup_20260831/ que no tiene call_transcripts ni satisfaction_surveys, y su transactions está incompleto (453 archivos contra 1097). Usamos data/ como fuente de verdad y lo documentamos.
Hay un marketing_campaigns.csv suelto en la raíz, duplicado. Se ignora.
campaign_sends tiene 1083 días en vez de 1097: faltan particiones, probablemente las "llegadas tardías" que mencionaban.
Conclusión: no podemos entrenar un clasificador con los transcripts. Eso va al slide de limitaciones, y los jueces lo van a valorar porque demuestra que miramos los datos de verdad.
1. Las descripciones de quejas son inservibles. Hay solo 5 textos distintos en 67,095 quejas, y cada uno es literalmente "Queja relacionada con {categoría}". Entrenar un clasificador de texto ahí sería leakage puro: la etiqueta viene escrita dentro del texto. Descartado.

2. Los montos son ruido. Todas las monedas tienen el mismo rango, de ~50 a ~5,000. Pero 5,000 COP es ~1 dólar y 5,000 USD es mucho dinero. El generador ignoró la moneda. Además, el 67% de las disputas no tiene moneda (16,364 de 24,491). Consecuencia práctica: no podemos usar claimed_amount para reglas de umbral sin cruzarlo con la transacción real. Otra nota de calidad.

3. Los transcripts son 546 plantillas en 171k filas, y 546 variantes no alcanzan para entrenar nada serio. Confirmado.