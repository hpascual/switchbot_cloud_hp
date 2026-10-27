# Proposal

## Why

Tras actualizar Home Assistant Core de 2026.8.3 a 2026.10.4, la integración
`SwitchBot Cloud Push` deja de cargarse: la plataforma `vacuum` importa
`VacuumEntityFeature.BATTERY`, que ya no existe en esta versión de HA. El fallo
de importación aborta el setup completo del config entry, por lo que ninguna
entidad de la integración queda disponible. Además, el sensor de CO2 usa
`CONCENTRATION_PARTS_PER_MILLION`, marcado como obsoleto y previsto para
eliminación en HA Core 2027.8.

## What Changes

- Eliminar el uso de `VacuumEntityFeature.BATTERY` en `vacuum.py` y exponer la
  batería mediante un sensor dedicado, ya que HA 2026.10 no admite
  `battery_level` en las entidades vacuum.
- Sustituir `CONCENTRATION_PARTS_PER_MILLION` por `UnitOfRatio.PARTS_PER_MILLION`
  en `sensor.py`.
- Revisar el resto de APIs de Home Assistant usadas por la integración
  (entidades, features, constantes y helpers) para detectar otros símbolos
  eliminados o deprecados en HA Core 2026.10 y corregirlos en el mismo cambio.
- No se modifica el dominio, el webhook, el mapeo de dispositivos, el polling ni
  la configuración existente.

## Capabilities

### New Capabilities

- `home-assistant-compatibility`: garantiza que la integración carga y funciona
  con las versiones soportadas de Home Assistant, sin usar APIs eliminadas ni
  constantes obsoletas que rompan el setup o generen avisos de deprecación.

### Modified Capabilities

<!-- Ninguna: el proyecto todavía no tiene specs principales. -->

## Impact

- Código afectado: `custom_components/switchbot_cloud_hp/vacuum.py`,
  `custom_components/switchbot_cloud_hp/sensor.py` y cualquier otro módulo que
  el análisis de compatibilidad identifique.
- Sin cambios en `manifest.json` ni en dependencias externas, salvo que la
  revisión detecte la necesidad de subir la versión mínima de HA.
- Sin cambios en la configuración de entradas existentes ni en las entidades
  visibles para el usuario.
- `README.md` se actualiza solo si el comportamiento visible o los requisitos
  de versión cambian.
