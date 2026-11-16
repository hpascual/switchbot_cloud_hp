# Design

## Context

Ver `proposal.md` — Why. Estado actual relevante:

- `switchbot_api==2.11.0` ejecuta `body = await response.json()` antes de
  comprobar `status >= 400`. Ante un `429` con cuerpo no JSON lanza
  `aiohttp.ContentTypeError` y nunca llega a `SwitchBotConnectionError`.
- `ContentTypeError` hereda de `ClientResponseError`, por lo que el estado HTTP
  queda disponible en `err.status`; no hace falta parsear el mensaje.
- `SwitchBotCloudEntity.send_api_command` (`entity.py:47`) es la puerta común de
  casi todas las plataformas; `button.py:103` es la excepción y llama directo a
  `self._api.send_command` usando `self._device_id`.
- En `button.py`, las entidades de AI Art Frame ajustan `_attr_unique_id` a
  `"{device_id}-{key}"`, por lo que `send_api_command` (que hoy usa
  `_attr_unique_id`) no serviría tal cual para ellas.
- El repositorio no tiene suite de tests ni infraestructura de CI.

## Goals / Non-Goals

**Goals:**

- Centralizar reintento y traducción de errores en la puerta común de comandos.
- Permitir que cada llamador declare si su comando es idempotente.
- Dejar `button.py` dentro de esa puerta sin romper sus unique IDs.
- Poder verificar el comportamiento con tests unitarios sin Home Assistant real.

**Non-Goals:**

- Corregir o bifurcar `switchbot_api`; el pin permanece en `2.11.0`.
- Reintentar comandos no idempotentes.
- Cambiar el polling del coordinator, el webhook o el mapeo de dispositivos.
- Introducir un cliente HTTP propio para comandos.

## Decisions

### D1. Interceptar en `send_api_command`, no en la librería

Se envuelve la llamada a `self._api.send_command` con el manejo de `aiohttp` y la
política de reintento. Alternativas descartadas: subir el pin (el 429 no se trata
hasta 2.14.0) y monkeypatchear la librería (frágil y fuera del control del
proyecto). Mantener el arreglo en la integración deja el comportamiento explícito
y testeable.

### D2. Reintento opt-out mediante parámetro explícito

`send_api_command` incorpora `retry_on_rate_limit: bool = True`. Los comandos
idempotentes (posición/abrir/cerrar cortina, encendido/apagado, clima, etc.)
conservan el valor por defecto. Los llamadores no idempotentes lo desactivan:

- `SwitchBotCloudBot.async_press` (Bot `PRESS` y botones de AI Art Frame).
- Comandos de remotos IR, si en el futuro pasan por esta puerta.

Se prefiere un booleano explícito por llamada frente a inferir idempotencia por
tipo de dispositivo o por comando: la decisión queda visible en el sitio de
llamada y no depende de tablas que pueden quedar desactualizadas.

### D3. Clasificación del 429 y del resto de errores

Se capturan, en este orden:

1. `aiohttp.ClientResponseError` (incluye `ContentTypeError`): si
   `err.status == 429` y el comando es reintentable, se aplica backoff; cualquier
   otro estado se traduce de inmediato a `HomeAssistantError`.
2. `aiohttp.ClientError` y `asyncio.TimeoutError`: se traducen a
   `HomeAssistantError` sin reintento (evita duplicar comandos no idempotentes y
   no hay señal de que un timeout sea transitorio seguro de repetir en todos los
   casos).
3. Cualquier otra excepción no se captura aquí: se deja propagar para no ocultar
   errores de programación.

`ContentTypeError` se reconoce por `err.status`, no por el texto del mensaje, para
no depender del formato de aiohttp.

### D4. Backoff, límite de intentos y `Retry-After`

- Constantes en `const.py`: `COMMAND_RETRY_MAX_ATTEMPTS = 3`,
  `COMMAND_RETRY_BASE_DELAY = 1.0` (segundos), `COMMAND_RETRY_FACTOR = 2.0`,
  `COMMAND_RETRY_MAX_DELAY = 8.0`.
- Espera del intento `n`: `min(BASE * FACTOR ** (n - 1), MAX_DELAY)`.
- Si la respuesta incluye `Retry-After`, se parsea como segundos o como fecha
  HTTP; se usa como espera.
- Si `Retry-After` supera `COMMAND_RETRY_MAX_DELAY`, **no** se reintenta: se lanza
  `HomeAssistantError` explicando que el proveedor pide una espera mayor que el
  máximo permitido. Así se respeta el requisito de no esperar menos que lo
  indicado sin bloquear la llamada de servicio durante minutos.

### D5. Identificador de dispositivo estable en la puerta común

`SwitchBotCloudEntity.__init__` fija `self._device_id = device.device_id` y
`send_api_command` usa `self._device_id` en vez de `_attr_unique_id`. Para las
entidades actuales ambos valores coinciden (sin cambio observable); para los
botones de AI Art Frame evita enviar el sufijo `-next`/`-previous` como MAC.
Esto habilita D2 para `button.py` sin tocar sus unique IDs.

### D6. `button.py` enrutado por la puerta común

`SwitchBotCloudBot.async_press` pasa a llamar a
`self.send_api_command(..., retry_on_rate_limit=False)`, conservando
`command_type` y `parameters` de su `entity_description`. El Bot y los botones de
AI Art Frame ganan el manejo legible de errores sin reintento.

### D7. Traducción a `HomeAssistantError`

El mensaje incluye la operación y el motivo, sin tokens, secrets ni URL completa.
Ejemplo: `"No se pudo enviar el comando al dispositivo: límite de tasa de la API
de SwitchBot (429) tras 3 intentos"`. Se registra en `debug` cada reintento con
número de intento y espera aplicada; en `warning`/`error` sólo el fallo final.

### D8. Tests unitarios sin Home Assistant real

Se añade `tests/` con `pytest` y `pytest-asyncio`:

- un doble de API cuyo `send_command` lanza `aiohttp.ContentTypeError` con
  `status=429` y cuerpo vacío, reproduciendo la línea 222 de la librería;
- un objeto mínimo con `_api`, `_device_id` y el método `send_api_command`
  (instanciado vía `object.__new__` de la entidad o una subclase de prueba) para
  no levantar el harness completo de HA;
- `asyncio.sleep` parcheado para no esperar de verdad;
- casos: éxito al primer intento (una sola llamada), 429→éxito (N llamadas y
  esperas), 429 agotado (N intentos y `HomeAssistantError`), 429 con
  `retry_on_rate_limit=False` (una sola llamada y `HomeAssistantError`), y
  `ClientError`/timeout traducidos.

## Risks / Trade-offs

- **Comando idempotente aplicado pese a 429** → el reintento podría repetirlo; es
  el compromiso aceptado para comandos idempotentes y se mitiga no reintentando
  los no idempotentes.
- **Bloqueo de la llamada de servicio durante el backoff** → acotado por
  `COMMAND_RETRY_MAX_ATTEMPTS` y `COMMAND_RETRY_MAX_DELAY` (máximo ~1+2+4 s con
  los valores propuestos).
- **`Retry-After` muy grande** → se corta el reintento y se falla con error
  legible en lugar de esperar minutos.
- **Dependencia de `err.status` en `ContentTypeError`** → es parte del contrato de
  `ClientResponseError` en aiohttp; si cambiara, los tests lo detectarían.
- **Nueva suite de tests en un repo sin CI** → se documenta cómo ejecutarla; no se
  añade pipeline en este cambio.

## Migration Plan

- Sin migración de `entry.data` ni cambios de configuración: se despliega con la
  actualización del custom component vía HACS.
- Rollback: revertir `entity.py`, `button.py`, `const.py` y eliminar `tests/`; no
  hay estado persistido afectado.
- Verificación manual: con la nube sana, un comando de cortina debe generar una
  única petición; con 429 simulado en debug, deben verse los reintentos y, al
  agotarse, un `HomeAssistantError` legible.

## Open Questions

- El disparador concreto del límite de tasa (volumen de polling frente a ráfaga
  de comandos) queda fuera de este cambio; no altera el diseño ni las tareas.
