# Spec Delta

## Purpose

Define cómo la integración debe mantenerse compatible con las versiones de Home
Assistant que declara soportar, cargando sin errores y sin usar APIs eliminadas
o deprecadas que rompan el setup o generen avisos de deprecación.

## ADDED Requirements

### Requirement: Carga completa de la integración

La integración SHALL completar el setup de todos sus platforms en Home Assistant
Core 2026.10 o superior, sin fallos de importación provocados por APIs
eliminadas.

#### Scenario: Setup tras actualizar Home Assistant

- **WHEN** Home Assistant Core 2026.10 carga el config entry de `SwitchBot Cloud Push`
- **THEN** todas las platforms configuradas se importan y el entry queda cargado
- **AND** no aparece ningún `ImportError` ni `AttributeError` durante la carga

#### Scenario: Fallo aislado de una platform

- **WHEN** una platform falla al importarse
- **THEN** el error identifica la platform concreta y el símbolo incompatible
- **AND** no se requiere adivinar la causa a partir de trazas de terceros

### Requirement: Compatibilidad de entidades vacuum

Las entidades vacuum SHALL declarar únicamente features soportadas por la
versión de Home Assistant en uso y SHALL seguir exponiendo el nivel de batería
mediante una entidad sensor dedicada.

#### Scenario: Vacuum con batería

- **WHEN** se crea una entidad vacuum de un dispositivo compatible
- **THEN** la entidad se registra correctamente
- **AND** su nivel de batería está disponible como sensor de batería
- **AND** no se declara la feature de batería retirada por Home Assistant

#### Scenario: Comandos de vacuum tras la corrección

- **WHEN** el usuario inicia, pausa, cambia la velocidad del ventilador o envía
  el vacuum a la base
- **THEN** la entidad ejecuta el comando correspondiente sin errores de features

### Requirement: Unidades soportadas en sensores

Los sensores SHALL usar unidades y constantes vigentes en la versión soportada
de Home Assistant, sin recurrir a constantes deprecadas.

#### Scenario: Sensor de CO2

- **WHEN** se crea el sensor de CO2 de un dispositivo que lo soporta
- **THEN** la unidad nativa es partes por millón usando la API vigente
- **AND** no se registra un aviso de constante deprecada de `switchbot_cloud_hp`

### Requirement: Revisión de APIs de Home Assistant

La integración SHALL evitar símbolos de Home Assistant eliminados o deprecados
en el código de las platforms, entidades y helpers que utiliza.

#### Scenario: Análisis de compatibilidad

- **WHEN** se revisa el código de la integración contra la versión objetivo de
  Home Assistant
- **THEN** no quedan referencias a símbolos eliminados ni avisos de deprecación
  originados por la integración
- **AND** las referencias detectadas quedan corregidas o documentadas con su
  alternativa y fecha de retirada
