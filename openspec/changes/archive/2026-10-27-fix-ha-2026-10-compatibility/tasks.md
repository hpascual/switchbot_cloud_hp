# Tasks

## 1. Restaurar la platform vacuum

- [x] 1.1 Eliminar `VacuumEntityFeature.BATTERY` de `_attr_supported_features` en `custom_components/switchbot_cloud_hp/vacuum.py`; verificar que el módulo ya no referencia `BATTERY` con `grep -n "BATTERY" custom_components/switchbot_cloud_hp/vacuum.py` sin resultados.
- [x] 1.2 Confirmar que `python -m compileall custom_components/switchbot_cloud_hp/vacuum.py` termina sin errores y que `VacuumEntityFeature` solo declara features existentes en HA 2026.10.4.

## 2. Batería de vacuum como sensor

- [x] 2.1 Añadir `VACUUM_DEVICE_TYPES` en `custom_components/switchbot_cloud_hp/const.py` con todos los `device_type` de vacuum ya mapeados; verificar que la tupla contiene los mismos valores que la condición actual de `__init__.py`.
- [x] 2.2 Usar `VACUUM_DEVICE_TYPES` en el mapeo de `custom_components/switchbot_cloud_hp/__init__.py`; verificar que los vacuums siguen añadiéndose a `devices_data.vacuums`.
- [x] 2.3 Añadir los tipos de `VACUUM_DEVICE_TYPES` a `SENSOR_DESCRIPTIONS_BY_DEVICE_TYPES` en `sensor.py` con `BATTERY_DESCRIPTION`, y añadir el coordinador del vacuum a `devices_data.sensors` reutilizando `coordinator_for_device`; verificar que cada vacuum produce un sensor `battery` sin duplicar coordinadores.
- [x] 2.4 Verificar que el unique ID del nuevo sensor (`<device_id>_battery`) no colisiona con entidades existentes del mismo dispositivo.

## 3. Eliminar deprecación del sensor de CO2

- [x] 3.1 Importar `UnitOfRatio` desde `homeassistant.const` en `sensor.py` y sustituir `CONCENTRATION_PARTS_PER_MILLION` por `UnitOfRatio.PARTS_PER_MILLION` en `CO2_DESCRIPTION`; verificar con `grep -rn "CONCENTRATION_PARTS_PER_MILLION" custom_components/` sin resultados.
- [x] 3.2 Confirmar que el valor nativo del sensor de CO2 sigue siendo `ppm` y que `python -m compileall custom_components/switchbot_cloud_hp/sensor.py` pasa.

## 4. Auditoría de compatibilidad con HA 2026.10.4

- [x] 4.1 Enumerar los símbolos importados desde `homeassistant.*` en todos los módulos de `custom_components/switchbot_cloud_hp/` y contrastarlos con el código fuente de HA Core 2026.10.4; verificar que ningún símbolo esté ausente.
- [x] 4.2 Identificar constantes `DeprecatedConstantEnum` usadas por la integración y sustituirlas por su alternativa vigente o documentar su fecha de retirada; verificar que no quedan referencias a constantes deprecadas.
- [x] 4.3 Revisar el uso de features de entidad (`VacuumEntityFeature`, `CoverEntityFeature`, `ClimateEntityFeature`, `FanEntityFeature`, `HumidifierEntityFeature`, `LockEntityFeature`) contra los enums de 2026.10.4; verificar que todas las features usadas existen.

## 5. Verificación final y documentación

- [x] 5.1 Ejecutar `python -m compileall custom_components` y confirmar que compila todo el paquete.
- [ ] 5.2 Instalar el cambio en una instancia con HA Core 2026.10.4 y verificar que el config entry carga sin `ImportError`/`AttributeError`, que las entidades vacuum responden a start/pause/fan speed/dock y que aparece el sensor de batería.
- [ ] 5.3 Revisar el log de HA tras el arranque y confirmar que no aparecen avisos de deprecación originados por `switchbot_cloud_hp`.
- [x] 5.4 Actualizar `README.md` si el cambio de batería a sensor o los requisitos de versión alteran la experiencia del usuario; verificar que el texto coincide con el comportamiento implementado.

## Workflow follow-up

- Archivar el cambio una vez validado en una instancia real de Home Assistant 2026.10.4.
