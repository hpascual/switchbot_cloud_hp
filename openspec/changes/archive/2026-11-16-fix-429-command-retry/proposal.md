# Proposal

## Why

Un `429` (límite de tasa) de la API de SwitchBot rompe el envío de comandos con
una excepción cruda (`aiohttp.ContentTypeError`) que Home Assistant registra
como "Unexpected exception", sin reintento y sin aviso legible. El 2026-11-16 la
cortina `cover.cortina_sala` (`FE70648E46FB`) no se abrió en la rutina de la
mañana por este motivo y quedó cerrada toda la mañana.

La causa está en `switchbot_api==2.11.0`: `_request` decodifica el cuerpo como
JSON antes de comprobar `status >= 400`, así que ante un 429 con cuerpo no JSON
revienta antes del manejo previsto y nunca se lanza `SwitchBotConnectionError`.
El 429 no se trata en ninguna versión hasta la 2.14.0, por lo que subir el pin no
lo resuelve.

## What Changes

- `SwitchBotCloudEntity.send_api_command` deja de ser transparente al fallo:
  - reintenta ante `429` con backoff exponencial y número máximo de intentos,
    respetando `Retry-After` cuando el proveedor lo envía;
  - captura `ContentTypeError`, `ClientResponseError`, `ClientError` y timeouts
    de `aiohttp`;
  - al agotar los intentos, o ante errores no reintentables, lanza
    `HomeAssistantError` con un mensaje legible en lugar de dejar escapar la
    excepción cruda.
- El reintento se aplica **solo a comandos idempotentes**. `send_api_command`
  expone un parámetro de política de reintento (activado por defecto) que los
  llamadores desactivan para comandos no idempotentes: `Bot PRESS`, botones de
  `AI Art Frame` y comandos de remotos IR.
- `button.py` pasa a enrutar sus comandos por `send_api_command` en vez de
  llamar directamente a `self._api.send_command`, con el reintento desactivado
  por no idempotencia, para que también reciba el manejo de errores legible.
- Se añaden tests unitarios con una sesión `aiohttp` simulada que reproduce el
  `ContentTypeError` de un `429` con cuerpo vacío.

No cambia: dominio, webhook, mapeo de dispositivos, intervalo del coordinator,
config entry, entidades visibles para el usuario, el flujo de Node-RED, ni el
pin `switchbot-api==2.11.0` en `manifest.json`.

## Capabilities

### New Capabilities

- `command-delivery`: entrega robusta de comandos a la API de SwitchBot:
  política de reintento ante límite de tasa, respeto de `Retry-After`,
  distinción entre comandos idempotentes y no idempotentes, y traducción de
  fallos de transporte/API a errores legibles de Home Assistant.

### Modified Capabilities

<!-- Ninguna: home-assistant-compatibility no cambia sus requisitos. -->

## Impact

- Código: `custom_components/switchbot_cloud_hp/entity.py` (núcleo del cambio),
  `custom_components/switchbot_cloud_hp/button.py` (enrutado por la puerta
  común) y constantes de reintento en `const.py`.
- Dependencias: ninguna nueva; se usa `aiohttp` y utilidades de Home Assistant
  ya presentes. `switchbot-api` se mantiene en `2.11.0`.
- Tests: nueva cobertura unitaria de `send_api_command`; el repositorio no tenía
  suite previa, así que se introduce el mínimo andamiaje necesario.
- Usuario: ante un 429 el servicio falla con un `HomeAssistantError` legible y,
  en comandos idempotentes, puede completarse tras los reintentos.
- Riesgo residual: si el 429 persiste más allá de los intentos configurados, el
  comando seguirá sin aplicarse, pero de forma visible y tipada.
