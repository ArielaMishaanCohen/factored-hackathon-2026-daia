# Correcciones puntuales: sesión, demo y tarjeta robada

## Uso

1. Aplicar los archivos modificados de este ZIP sobre el proyecto de trabajo. No reemplazar la base `data/ops.sqlite` del despliegue con una copia del ZIP: para limpiar el escenario usar el botón nuevo.
2. Reconstruir el frontend y reiniciar el backend como hacen habitualmente. Si usan Docker, reconstruir la imagen para incorporar los botones.
3. **Nueva conversación** vacía el chat visible y el próximo mensaje recibe otro `conversation_id`. Conserva casos y bloqueos: R5 sigue evitando duplicados.
4. **Reiniciar demo** pide confirmación y elimina conversaciones, casos, bloqueos simulados, acciones pendientes vinculadas, handoffs y trazas del cliente conectado. Conserva otros clientes, datos gold, secuencias de IDs y registros de seguridad. Después pueden ejecutar nuevamente el escenario. No se reinicia automáticamente al cambiar de escenario.
5. El endpoint es `POST /api/auth/demo/reset`, sin cuerpo, con el Bearer del cliente. Devuelve 204; exige cliente autenticado y `DEMO_MODE=true`. Con demo desactivada devuelve 404. No permite indicar otro cliente en el cuerpo.
6. Ante «me robaron mi tarjeta la tengo que cancelar», se ofrece el bloqueo sin pedir cargos. Si hay varias tarjetas, pregunta sus últimos cuatro dígitos. El cliente confirma, se bloquea y se verifica. Después puede reportar un cargo si realmente no lo reconoce; no se abre una disputa automáticamente.

El bloqueo sigue siendo el mock del proyecto: no cancela un plástico bancario real. Si el mensaje ya identifica un cargo concreto, se conserva el flujo existente: bloqueo y luego confirmación independiente de la disputa según la política.

## Archivos modificados

- `backend/app/config.py`: valor de desarrollo cuando JWT_SECRET está ausente o vacío; conserva el valor configurado cuando existe.
- `backend/app/store.py`: reinicio por cliente en memoria y SQLite.
- `backend/app/main.py`: endpoint de reinicio; exclusión mutua entre chat y reinicio para evitar que un turno en curso reponga datos borrados.
- `backend/app/tools/data_source.py`: consulta de tarjetas propias en gold o stubs, independiente de las transacciones.
- `backend/app/orchestrator.py`: bloqueo independiente de cargos, selección por últimos cuatro dígitos, verificación y enlace de confirmación con la conversación actual; no repetir bloqueos ya aplicados.
- `backend/app/responder/templates.py`: mensajes nuevos ES/PT.
- `frontend/src/api/client.ts`, `frontend/src/App.tsx`, `frontend/src/i18n.ts`: conexión del endpoint y dos botones con textos ES/PT; confirmación antes de borrar la demo y actualización del panel del agente.
- `docs/design.md`: actualización del párrafo que antes exigía identificar una transacción antes de bloquear.
- `tests/test_reset_y_bloqueo_directo.py`: ocho pruebas de regresión nuevas.
- Este documento.

Los demás archivos del ZIP original se conservan con el mismo contenido, incluidos los datos. No se modificaron umbrales, clasificador, prompts ni reglas de R5.

## Validación realizada y pendiente

- Sintaxis Python: compilación correcta del backend y del archivo nuevo de pruebas.
- Seis comprobaciones aisladas del core ejecutadas correctamente con los modelos Pydantic, herramientas de tarjetas/casos, política, confirmaciones, SQLite y orquestador reales. Se sustituyeron adaptadores no disponibles; se usó el NLU de palabras clave y las plantillas, sin Gemini ni gold.
- Comprobado: frase de robo → confirmación → bloqueo sin caso; tarjeta ya bloqueada; cancelación sin bloqueo y derivación a fraude; selección entre varias tarjetas; rechazo de confirmación de otro chat; R5 en conversación nueva y reinicio persistente que conserva otro cliente e IDs.
- No se ejecutó pytest completo, el backend HTTP ni el build del frontend: el entorno de revisión carece de dependencias y no pudo instalarlas. Tampoco se probó Gemini ni el clasificador entrenado en ejecución. No equivale a una validación integral del despliegue.

En el entorno habitual, desde la raíz del proyecto, ejecutar `python -m pytest tests/test_reset_y_bloqueo_directo.py tests/test_r11_y_tarjeta_robada.py tests/test_api_contract.py tests/test_persistencia.py`, y desde `frontend`, `npm run build`. Usar sus dependencias instaladas; este cambio no altera los requirements. Luego probar la frase de robo con el modelo real y repetir un escenario tras **Reiniciar demo**.
