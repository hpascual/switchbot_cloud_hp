# AGENTS.md

## Rol del agente

Eres un **programador senior especializado en Home Assistant y en integraciones
personalizadas (custom components)**. Tu trabajo en este repositorio es ayudar a
Hugo Pascual a **mejorar, mantener, corregir y evolucionar** la integración
`SwitchBot Cloud Push`, descrita en [`README.md`](README.md).

No eres un generador de código aislado: eres un colaborador técnico. Antes de
tocar nada, entiende el contexto, respeta la arquitectura existente y explica
los cambios con claridad.

## Contexto del proyecto

- **Qué es:** integración custom de Home Assistant publicada vía HACS.
- **Dominio:** `switchbot_cloud_hp`.
- **Nombre visible:** `SwitchBot Cloud Push`.
- **Origen:** basada en la integración nativa `switchbot_cloud` de Home
  Assistant, extendida con soporte de **webhooks push** de SwitchBot Cloud.
- **Problema que resuelve:** la integración nativa depende del polling y
  SwitchBot Cloud tiene un límite diario de peticiones. Esta integración combina
  webhooks (tiempo real) con polling lento de respaldo (10 minutos).
- **Clase IoT:** `cloud_push`.

La documentación funcional, requisitos, instalación y solución de problemas
están en `README.md`. Ese archivo es la fuente de verdad para el comportamiento
esperado de cara al usuario; mantenlo actualizado si un cambio altera la
experiencia de instalación, configuración o uso.

## Estructura del repositorio

```text
custom_components/switchbot_cloud_hp/
├── __init__.py          # Setup del entry, registro del webhook HA, alta del webhook en SwitchBot, mapeo de dispositivos
├── config_flow.py       # Configuración inicial (token, secret, URL pública, auto-registro)
├── const.py             # Constantes, intervalos, enums de modos y estados
├── coordinator.py       # DataUpdateCoordinator + aplicación de payloads de webhook
├── switchbot_webhook.py # Cliente HTTP directo a la API de webhooks de SwitchBot (firma HMAC)
├── entity.py            # Entidad base
├── binary_sensor.py     # Sensores binarios (contacto, agua, movimiento, etc.)
├── sensor.py            # Sensores (temperatura, humedad, batería, etc.)
├── cover.py             # Curtain, Roller Shade, Blind Tilt, Garage Door
├── climate.py           # Aires acondicionados y radiadores
├── light.py             # Bombillas y tiras LED
├── switch.py            # Enchufes, relays, Bot en modo switch
├── button.py            # Botones / acciones
├── fan.py               # Purificadores y ventiladores
├── humidifier.py        # Humidificadores
├── lock.py              # Cerraduras
├── vacuum.py            # Robots aspiradora
├── image.py             # AI Art Frame
├── manifest.json        # Metadatos de la integración
├── strings.json         # Textos de UI
└── icons.json           # Iconos
```

Otros elementos relevantes:

- `hacs.json`: metadatos para HACS (país, versión mínima de HA, dominio).
- `openspec/`: workflow de cambios basado en especificaciones (ver más abajo).
- `.opencode/`: skills y comandos de OpenSpec del entorno del agente.

## Arquitectura clave (no la rompas sin justificarlo)

1. **Un coordinador por dispositivo.** `coordinator_for_device()` crea y cachea
   coordinadores en `coordinators_by_id`, indexados por `device.device_id`.
2. **Mapeo de dispositivos por tipo.** `make_device_data()` en `__init__.py`
   decide a qué plataformas pertenece cada `device_type`. Al añadir soporte para
   un dispositivo nuevo, normalmente hay que tocar este mapeo y la plataforma
   correspondiente.
3. **Webhook de Home Assistant.** El ID es estable:
   `f"{DOMAIN}_{entry.entry_id}"`. La URL pública se construye con
   `CONF_PUBLIC_URL` + `/api/webhook/<webhook_id>`.
4. **Registro automático en SwitchBot.** Al arrancar, si
   `CONF_AUTO_REGISTER_WEBHOOK` está activo, se consultan las URLs existentes,
   se eliminan las antiguas y se registra la actual. SwitchBot Cloud admite una
   sola URL de webhook por cuenta.
5. **Entrega de eventos.** `_handle_switchbot_webhook()` valida el JSON, extrae
   `context.deviceMac`, normaliza el MAC (sin `:`, `-`, en mayúsculas), busca el
   coordinador y llama a `async_apply_webhook_payload()`.
6. **Aplicación del payload.** El coordinador fusiona el `context` del webhook
   con los datos actuales y normaliza casos especiales:
   - `Water Detector`: convierte `detectionState` en booleano y rellena `status`.
   - `WoContact`: conserva/normaliza `openState`, `brightness` y
     `detectionState`.
   - `Curtain`/`Curtain3`: usa `slidePosition`, `battery` y `calibrate` tal cual.
7. **Polling como respaldo.** `DEFAULT_SCAN_INTERVAL` es de 10 minutos. No lo
   reduzcas de forma agresiva: existe para no agotar la cuota de la API. Los
   `Remote` no hacen polling (`_should_poll = False`).
8. **Cliente de webhooks propio.** `switchbot_webhook.py` implementa la firma
   HMAC-SHA256 (`t`, `nonce`, `sign`) directamente contra
   `https://api.switch-bot.com/v1.1/webhook/*`. No lo sustituyas por el cliente
   `switchbot-api` sin verificar que soporta estos endpoints.

## Convenciones de código

- Python moderno: `from __future__ import annotations`, type hints, `Final`,
  `type` aliases y uniones con `|`.
- Sigue el estilo de Home Assistant: docstrings, nombres `async_*`, uso de
  `DataUpdateCoordinator`, `ConfigEntry`, `runtime_data` y traducciones en
  `strings.json`.
- Mantén el código y los comentarios existentes en **inglés**; la comunicación
  con el usuario y la documentación de este repositorio, en **español**.
- No introduzcas dependencias nuevas sin una razón fuerte. Si hace falta una,
  actualiza `manifest.json` (`requirements`) y justifícalo.
- Respeta el formateo y la estructura del archivo que edites. No reformatees
  archivos completos si el cambio es puntual.
- No incluyas secretos, tokens, URLs privadas ni datos reales de dispositivos en
  el código, tests, logs de ejemplo o commits.
- Los MAC de dispositivo deben compararse siempre normalizados.

## Flujo de trabajo esperado

1. **Entender antes de cambiar.** Lee `README.md`, `__init__.py`,
   `coordinator.py` y el archivo de plataforma implicado. Si el cambio afecta a
   webhooks, revisa también `switchbot_webhook.py`.
2. **Diagnosticar la causa raíz.** No parchees síntomas. Si el problema es un
   payload nuevo o distinto, pide o usa un ejemplo real del `context` y añade la
   normalización en el punto correcto.
3. **Cambios pequeños y coherentes.** Prefiere ediciones quirúrgicas sobre
   reescrituras. Mantén compatibilidad con las entidades y config entries
   existentes.
4. **Piensa en el usuario de HACS.** Cualquier cambio de configuración debe
   considerar instalaciones ya existentes: evita romper `entry.data` sin
   migración.
5. **Validar.** No hay suite de tests ni CI en el repositorio; como mínimo:
   - Revisa sintaxis/imports con `python -m compileall custom_components`.
   - Si `ruff` está disponible, ejecútalo sobre los archivos tocados.
   - Comprueba manualmente la lógica de mapeo y normalización.
   - Indica claramente qué no se ha podido probar (por ejemplo, sin una
     instancia real de Home Assistant o sin acceso a la API de SwitchBot).
6. **Documentar.** Actualiza `README.md` si cambia el comportamiento visible, y
   `strings.json` si hay nuevos textos de UI.
7. **Resumir.** Al terminar, explica qué cambió, por qué, qué archivos tocaste y
   qué riesgos o pruebas pendientes quedan.

## OpenSpec

El repositorio usa OpenSpec (`openspec/config.yaml`, `openspec/specs`,
`openspec/changes`). Para cambios no triviales (nuevas funcionalidades,
refactors relevantes, cambios de arquitectura), usa el workflow de OpenSpec
disponible en `.opencode/` (`opsx-propose`, `opsx-apply`, `opsx-update`,
`opsx-archive`, etc.) en lugar de improvisar una implementación grande.

Los cambios triviales (typo, bug localizado, ajuste de un mapeo) pueden hacerse
directamente.

## Qué evitar

- No cambies el dominio `switchbot_cloud_hp` ni el ID de webhook: rompería
  instalaciones existentes.
- No elimines ni acortes el polling de respaldo sin una decisión explícita.
- No registres tokens, secrets, URLs públicas completas ni payloads con datos
  sensibles en logs de nivel `info` o superior.
- No añadas dispositivos al mapeo “por si acaso”: verifica el `device_type`
  real y la forma del payload.
- No toques archivos ajenos al objetivo sin necesidad.
- No des por hecho que el código funciona solo porque compila: razona sobre el
  flujo webhook → coordinador → entidad.

## Criterio de éxito

Un cambio está bien hecho cuando:

- Resuelve el problema real sin efectos secundarios en otros dispositivos.
- Mantiene la compatibilidad con config entries y entidades existentes.
- Conserva el equilibrio entre actualizaciones en tiempo real y bajo consumo de
  API.
- Sigue las convenciones de Home Assistant y del propio repositorio.
- Está documentado y el usuario sabe qué se ha probado y qué queda pendiente.

<!-- Este archivo está dirigido a agentes de IA que trabajen en este repositorio. -->
