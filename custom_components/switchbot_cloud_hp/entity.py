"""Base class for SwitchBot via API entities."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import aiohttp
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from switchbot_api import Commands, Device, Remote, SwitchBotAPI

from .const import (
    COMMAND_RETRY_BASE_DELAY,
    COMMAND_RETRY_FACTOR,
    COMMAND_RETRY_MAX_ATTEMPTS,
    COMMAND_RETRY_MAX_DELAY,
    DOMAIN,
    RATE_LIMIT_STATUS,
)
from .coordinator import SwitchBotCoordinator

_LOGGER = logging.getLogger(__name__)


def _parse_retry_after(err: aiohttp.ClientResponseError) -> float | None:
    """Return the Retry-After delay in seconds, if the response provides one."""
    headers = err.headers or {}
    value = headers.get("Retry-After")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        pass

    try:
        retry_at = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=UTC)
    return max(0.0, (retry_at - datetime.now(UTC)).total_seconds())


class SwitchBotCloudEntity(CoordinatorEntity[SwitchBotCoordinator]):
    """Representation of a SwitchBot Cloud entity."""

    _api: SwitchBotAPI
    _switchbot_state: dict[str, Any] | None = None
    _attr_has_entity_name = True

    def __init__(
        self,
        api: SwitchBotAPI,
        device: Device | Remote,
        coordinator: SwitchBotCoordinator,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._api = api
        self._attr_unique_id = device.device_id
        self._device_id = device.device_id
        _sw_version = None
        if self.coordinator.data is not None:
            _sw_version = self.coordinator.data.get("version")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.device_name,
            manufacturer="SwitchBot",
            model=device.device_type,
            sw_version=_sw_version,
        )

    async def send_api_command(
        self,
        command: Commands,
        command_type: str = "command",
        parameters: dict | str | int = "default",
        retry_on_rate_limit: bool = True,
    ) -> None:
        """Send command to device, retrying rate limits on idempotent commands."""
        max_attempts = COMMAND_RETRY_MAX_ATTEMPTS if retry_on_rate_limit else 1
        for attempt in range(1, max_attempts + 1):
            try:
                await self._api.send_command(
                    self._device_id,
                    command,
                    command_type,
                    parameters,
                )
                return
            except aiohttp.ClientResponseError as err:
                if err.status == RATE_LIMIT_STATUS and attempt < max_attempts:
                    delay = _parse_retry_after(err)
                    if delay is not None and delay > COMMAND_RETRY_MAX_DELAY:
                        raise HomeAssistantError(
                            "SwitchBot API rate limit: provider requested a wait of "
                            f"{delay:.0f}s, longer than the {COMMAND_RETRY_MAX_DELAY:.0f}s "
                            "allowed, so the command was not retried"
                        ) from err
                    if delay is None:
                        delay = min(
                            COMMAND_RETRY_BASE_DELAY
                            * COMMAND_RETRY_FACTOR ** (attempt - 1),
                            COMMAND_RETRY_MAX_DELAY,
                        )
                    _LOGGER.debug(
                        "SwitchBot API rate limit on attempt %s/%s, retrying in %.1fs",
                        attempt,
                        max_attempts,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                if err.status == RATE_LIMIT_STATUS:
                    raise HomeAssistantError(
                        "SwitchBot API rate limit (429) reached, the command was not "
                        f"applied after {attempt} attempt(s)"
                    ) from err
                raise HomeAssistantError(
                    f"SwitchBot API error (status {err.status}) while sending the command"
                ) from err
            except TimeoutError as err:
                raise HomeAssistantError(
                    "Timed out sending the command to the SwitchBot API"
                ) from err
            except aiohttp.ClientError as err:
                raise HomeAssistantError(
                    "Could not reach the SwitchBot API while sending the command"
                ) from err

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._set_attributes()
        super()._handle_coordinator_update()

    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""

    async def async_added_to_hass(self) -> None:
        """Run when entity is about to be added to hass."""
        await super().async_added_to_hass()
        self._set_attributes()
