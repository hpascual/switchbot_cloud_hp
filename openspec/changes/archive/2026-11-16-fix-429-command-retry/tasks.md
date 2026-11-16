# Tasks

## 1. Constantes y puerta común de comandos

- [x] 1.1 Añadir en `const.py` las constantes de reintento (`COMMAND_RETRY_MAX_ATTEMPTS`, `COMMAND_RETRY_BASE_DELAY`, `COMMAND_RETRY_FACTOR`, `COMMAND_RETRY_MAX_DELAY`) y verificar con `python -m compileall custom_components`.
- [x] 1.2 En `entity.py`, fijar `self._device_id = device.device_id` en `__init__` y hacer que `send_api_command` lo use en lugar de `_attr_unique_id`; verificar que compila y que el valor coincide con el unique ID en entidades actuales.
- [x] 1.3 Añadir a `send_api_command` el parámetro `retry_on_rate_limit: bool = True` y el bucle de reintento con backoff exponencial y tope de intentos; verificar que el camino feliz hace una sola llamada y sin esperas.
- [x] 1.4 Parsear `Retry-After` (segundos o fecha HTTP), usarlo como espera y abortar con `HomeAssistantError` si supera `COMMAND_RETRY_MAX_DELAY`; verificar con un caso unitario de `Retry-After` grande.
- [x] 1.5 Capturar `aiohttp.ClientResponseError` (429 reintentable, otros estados no), `aiohttp.ClientError` y `asyncio.TimeoutError`, traduciéndolos a `HomeAssistantError` con mensaje legible; verificar con `python -m compileall custom_components`.
- [x] 1.6 Registrar en `debug` cada reintento con número de intento y espera, sin tokens ni URLs privadas; verificar revisando las llamadas al logger en el código y que los tests no capturen datos sensibles.

## 2. Botones por la puerta común

- [x] 2.1 Modificar `button.py` para que `SwitchBotCloudBot.async_press` use `self.send_api_command(..., retry_on_rate_limit=False)` conservando `command_type` y `parameters`; verificar con `python -m compileall custom_components`.
- [x] 2.2 Comprobar que los botones de AI Art Frame envían `device.device_id` (sin sufijo `-next`/`-previous`) como identificador de dispositivo; verificar con un test unitario que inspecciona el argumento recibido por el doble de API.

## 3. Tests unitarios

- [x] 3.1 Crear el andamiaje mínimo de tests (`tests/`, `requirements_test.txt` o equivalente, configuración de `pytest-asyncio`) y verificar que `pytest tests -q` arranca y recolecta.
- [x] 3.2 Implementar un doble de API y una entidad mínima de prueba que reproduzcan `ContentTypeError: 429` con cuerpo vacío; verificar que el test falla con el código previo y pasa tras el cambio.
- [x] 3.3 Añadir casos: éxito al primer intento (una sola llamada), 429→éxito (N llamadas y esperas crecientes), 429 agotado (`HomeAssistantError`), y 429 con `retry_on_rate_limit=False` (una sola llamada, `HomeAssistantError`); verificar con `pytest tests -q`.
- [x] 3.4 Añadir casos de `ClientError`/timeout traducidos a `HomeAssistantError` y de `Retry-After` respetado; verificar con `pytest tests -q`.

## 4. Documentación y verificación final

- [x] 4.1 Actualizar `README.md` con una nota de solución de problemas sobre el 429, el reintento solo en comandos idempotentes y el error legible resultante; verificar leyendo la sección publicada.
- [x] 4.2 Ejecutar `python -m compileall custom_components` y `pytest tests -q` y confirmar que todo pasa; anotar qué no se pudo probar (API real, Home Assistant real).
- [x] 4.3 (Opcional, si `ruff` está disponible) ejecutar `ruff check custom_components/switchbot_cloud_hp/entity.py custom_components/switchbot_cloud_hp/button.py custom_components/switchbot_cloud_hp/const.py tests` y corregir avisos.

## Workflow follow-up

- Archivar el cambio cuando la revisión del proyecto esté satisfecha.
- Verificar el resultado archivado.
