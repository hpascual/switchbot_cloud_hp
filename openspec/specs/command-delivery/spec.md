# command-delivery Specification

## Purpose

Define cómo la integración entrega comandos a la API de SwitchBot de forma
robusta: reintentos acotados ante límites de tasa para comandos idempotentes y
fallos tipados y legibles en Home Assistant cuando el comando no puede aplicarse.

## Requirements

### Requirement: Reintento acotado ante límite de tasa

Ante una respuesta `429` de la API de SwitchBot, la integración SHALL reintentar
el comando idempotente con backoff exponencial hasta un máximo de intentos
configurado, respetando `Retry-After` cuando la respuesta lo incluya.

#### Scenario: Reintento con éxito tras 429

- **WHEN** el primer intento de un comando idempotente recibe `429` y un intento
  posterior recibe una respuesta correcta
- **THEN** el comando se aplica y el servicio termina sin error
- **AND** cada reintento espera un tiempo creciente entre intentos

#### Scenario: Respeto de Retry-After

- **WHEN** la respuesta `429` incluye una cabecera `Retry-After` válida
- **THEN** la integración espera ese intervalo antes del siguiente intento
- **AND** no aplica una espera menor que la indicada por el proveedor

#### Scenario: Agotamiento de intentos

- **WHEN** todos los intentos de un comando idempotente reciben `429`
- **THEN** la integración deja de reintentar al alcanzar el máximo configurado
- **AND** el servicio falla con un error legible que indica el límite de tasa

### Requirement: Reintento limitado a comandos idempotentes

La integración SHALL NOT reintentar comandos no idempotentes, como pulsaciones
de Bot, comandos de remotos IR o botones de AI Art Frame, para evitar efectos
duplicados cuando el primer envío sí llegó a aplicarse.

#### Scenario: Pulsación de Bot ante 429

- **WHEN** una pulsación de Bot recibe `429`
- **THEN** la integración no repite el comando
- **AND** el servicio falla con un error legible que indica el límite de tasa

#### Scenario: Comando de cortina ante 429

- **WHEN** un cambio de posición de cortina recibe `429`
- **THEN** la integración lo trata como comando idempotente y aplica la política
  de reintento acotado

### Requirement: Errores de envío legibles

Cuando el envío de un comando falla por un error de transporte o de respuesta de
la API, la integración SHALL lanzar `HomeAssistantError` con un mensaje legible
en lugar de propagar la excepción cruda de `aiohttp`.

#### Scenario: Cuerpo no JSON en respuesta de error

- **WHEN** la API responde con un estado de error y un cuerpo que no es JSON
- **THEN** la integración captura el fallo de decodificación
- **AND** el servicio falla con un `HomeAssistantError` comprensible
- **AND** Home Assistant no registra el fallo como "Unexpected exception"

#### Scenario: Timeout o error de conexión

- **WHEN** la petición a la API agota el tiempo de espera o sufre un error de
  conexión
- **THEN** la integración lanza un `HomeAssistantError` con el motivo del fallo
- **AND** no reintenta comandos no idempotentes

### Requirement: Camino feliz sin sobrecoste

Cuando la API responde correctamente al primer intento, la integración SHALL
enviar el comando una sola vez y no realizar llamadas adicionales ni esperas de
reintento.

#### Scenario: Comando aceptado a la primera

- **WHEN** un comando recibe una respuesta correcta en el primer intento
- **THEN** se realiza exactamente una llamada a la API
- **AND** no se aplica ningún retraso de backoff

### Requirement: Diagnóstico de reintentos

La integración SHALL registrar en nivel `debug` los reintentos por límite de
tasa, incluyendo el número de intento y la espera aplicada, sin exponer tokens,
secrets ni URLs privadas.

#### Scenario: Reintentos visibles en debug

- **WHEN** un comando reintenta por `429` con `switchbot_api` en nivel `debug`
- **THEN** el log muestra cada reintento y la espera aplicada
- **AND** el log no contiene credenciales ni datos sensibles
