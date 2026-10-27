# Design

## Context

Ver `proposal.md`. La integración declara `switchbot-api==2.11.0` y no fija una
versión mínima de Home Assistant. El fallo actual ocurre en tiempo de
importación de la platform `vacuum`, antes de que el config entry termine de
cargarse.

Hechos observados en Home Assistant Core:

- `VacuumEntityFeature.BATTERY` existía en 2026.8.3 y ya no existe en 2026.10.4.
- `StateVacuumEntity` tampoco expone `battery_level` ni `battery_icon`; Home
  Assistant indica que la batería debe publicarse como sensor independiente.
- `CONCENTRATION_PARTS_PER_MILLION` sigue existiendo en 2026.10.4, pero es un
  `DeprecatedConstantEnum` con retirada prevista en 2027.8. Su sustituto es
  `UnitOfRatio.PARTS_PER_MILLION`.

## Goals / Non-Goals

**Goals:**

- Restaurar la carga completa del config entry en HA Core 2026.10.
- Conservar la información de batería de los vacuum mediante una entidad sensor
  dedicada, siguiendo la recomendación de Home Assistant.
- Eliminar el aviso de deprecación del sensor de CO2.
- Detectar y corregir otras incompatibilidades de la misma naturaleza dentro de
  la integración.

**Non-Goals:**

- No se cambia el modelo de datos del coordinador ni la lógica de webhooks.
- No se añaden dispositivos nuevos al mapeo.
- No se actualiza `switchbot-api` ni se modifican dependencias salvo necesidad
  demostrada.
- No se reescriben platforms no afectadas.

## Decisions

### 1. Eliminar `VacuumEntityFeature.BATTERY` y publicar la batería como sensor

Se quita la feature `BATTERY` de `_attr_supported_features` en
`SwitchBotCloudVacuum`. La batería se expone con `BATTERY_DESCRIPTION` en la
platform `sensor`, reutilizando el coordinador ya cacheado por
`coordinator_for_device`.

Alternativas consideradas:

- Mantener `_attr_battery_level` en la entidad vacuum: descartado porque la
  clase base de HA 2026.10 ya no lo soporta.
- Omitir la batería: descartado porque degrada funcionalidad visible para el
  usuario.

Impacto: los usuarios verán una entidad `sensor.*_battery` nueva para cada
vacuum. Los unique IDs nuevos (`<device_id>_battery`) no colisionan con las
entidades vacuum existentes.

### 2. Lista compartida de tipos de vacuum

Los tipos de dispositivo vacuum se necesitan ahora en el mapeo de plataformas
(`__init__.py`) y en el mapeo de sensores (`sensor.py`). Se extrae una constante
`VACUUM_DEVICE_TYPES` en `const.py` para evitar que ambas listas se desincronicen.

Alternativa considerada: duplicar la lista en `sensor.py`. Descartado por el
riesgo de que un vacuum nuevo tenga entidad pero no sensor de batería.

### 3. Sustituir la constante obsoleta de concentración

Se importa `UnitOfRatio` desde `homeassistant.const` y se usa
`UnitOfRatio.PARTS_PER_MILLION` en `CO2_DESCRIPTION`. El valor (`"ppm"`) y la
entidad resultante no cambian; solo desaparece el aviso de deprecación.

### 4. Auditoría acotada de APIs de Home Assistant

Antes de cerrar el cambio se revisan los símbolos importados desde
`homeassistant.*` en todos los módulos de la integración contra el código fuente
de HA Core 2026.10.4. El criterio es: si un símbolo no existe o es
`DeprecatedConstantEnum` con retirada anunciada, se corrige o se documenta. No
se busca una actualización general de la integración.

## Risks / Trade-offs

- **Nuevas entidades sensor para vacuums** → pueden aparecer como entidades
  nuevas en el registro. Mitigación: unique ID estable y `_attr_name = None`
  heredado del patrón de sensores; documentar en el resumen de la release.
- **Lista de dispositivos vacuum incompleta** → un modelo no listado no tendría
  sensor de batería. Mitigación: centralizar la lista y cubrir todos los tipos
  ya presentes en el mapeo actual.
- **Auditoría basada en una versión concreta de HA** → una versión futura puede
  volver a romper. Mitigación: dejar constancia de la versión revisada y de los
  símbolos deprecados con fecha de retirada en las tareas/notas del cambio.
- **Sin tests automatizados en el repositorio** → la validación es estática más
  una prueba manual en una instancia real. Mitigación: compilar los módulos y
  verificar el setup en HA 2026.10.4 antes de publicar.

## Migration Plan

1. Aplicar los cambios de código.
2. Validar sintaxis con `python -m compileall custom_components`.
3. Instalar en una instancia HA 2026.10.4 y comprobar que el config entry carga
   sin `ImportError`, que las entidades vacuum funcionan y que aparece el sensor
   de batería.
4. Rollback: revertir el cambio; no hay migración de datos ni cambios en
   `entry.data`.

## Open Questions

- Ninguna que afecte al alcance. Si la auditoría encuentra un símbolo dudoso, se
  resolverá durante la implementación consultando la fuente de HA 2026.10.4.
