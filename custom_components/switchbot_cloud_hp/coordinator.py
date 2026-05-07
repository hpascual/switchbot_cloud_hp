"""SwitchBot Cloud coordinator."""

from __future__ import annotations

from asyncio import timeout
from logging import getLogger
from typing import Any

from switchbot_api import Device, Remote, SwitchBotAPI, SwitchBotConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = getLogger(__name__)

type Status = dict[str, Any] | None


class SwitchBotCoordinator(DataUpdateCoordinator[Status]):
    """SwitchBot Cloud coordinator."""

    config_entry: ConfigEntry
    _api: SwitchBotAPI
    _device_id: str
    _device_mac: str
    _manageable_by_webhook: bool
    _webhooks_connected: bool = False

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api: SwitchBotAPI,
        device: Device | Remote,
        manageable_by_webhook: bool,
    ) -> None:
        """Initialize SwitchBot Cloud."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

        self._api = api
        self._device_id = device.device_id
        self._device_mac = self._normalize_mac(device.device_id)
        self._should_poll = not isinstance(device, Remote)
        self._manageable_by_webhook = manageable_by_webhook

    @property
    def device_id(self) -> str:
        """Return SwitchBot device id."""
        return self._device_id

    @property
    def device_mac(self) -> str:
        """Return normalized SwitchBot device MAC."""
        return self._device_mac

    @staticmethod
    def _normalize_mac(value: str | None) -> str:
        """Normalize MAC/device id for matching webhook payloads."""
        if not value:
            return ""
        return value.replace(":", "").replace("-", "").upper()

    def webhook_subscription_listener(self, connected: bool) -> None:
        """Call when webhook status changed.

        In the original integration, polling is disabled when webhook is connected.
        For this custom integration we keep polling enabled as a backup.
        """
        if self._manageable_by_webhook:
            self._webhooks_connected = connected
            self.update_interval = DEFAULT_SCAN_INTERVAL

    def manageable_by_webhook(self) -> bool:
        """Return whether device can be managed by webhook."""
        return self._manageable_by_webhook

    async def _async_update_data(self) -> Status:
        """Fetch data from API endpoint."""
        if not self._should_poll:
            return None

        try:
            _LOGGER.debug("Refreshing %s", self._device_id)
            async with timeout(10):
                status: Status = await self._api.get_status(self._device_id)
                _LOGGER.debug("Refreshing %s with %s", self._device_id, status)
                return status

        except SwitchBotConnectionError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    def async_apply_webhook_payload(self, context: dict[str, Any]) -> None:
        """Apply SwitchBot webhook context to coordinator data.

        Expected examples:

        Contact Sensor:
        {
            "deviceMac": "B0E9FED68EA1",
            "deviceType": "WoContact",
            "battery": 100,
            "brightness": "bright",
            "detectionState": "NOT_DETECTED",
            "openState": "close"
        }

        Water Detector:
        {
            "deviceMac": "E77603060B58",
            "deviceType": "Water Detector",
            "battery": 100,
            "detectionState": 1
        }

        Curtain3:
        {
            "deviceMac": "FE70648E46FB",
            "deviceType": "WoCurtain3",
            "battery": 35,
            "calibrate": true,
            "slidePosition": 44
        }
        """
        if not context:
            return

        webhook_mac = self._normalize_mac(context.get("deviceMac"))
        if webhook_mac and webhook_mac != self._device_mac:
            _LOGGER.debug(
                "Ignoring webhook for %s because coordinator is %s",
                webhook_mac,
                self._device_mac,
            )
            return

        current_data: dict[str, Any] = dict(self.data or {})
        current_data.update(context)

        device_type = context.get("deviceType")

        # Normalize Water Detector webhook value for existing binary_sensor.py logic.
        # Existing code checks any(data.get(key) for key in ("status", "detectionState")).
        if device_type == "Water Detector":
            detection_state = context.get("detectionState")
            current_data["status"] = bool(detection_state)
            current_data["detectionState"] = bool(detection_state)

        # Normalize Contact Sensor values to match existing entity logic.
        if device_type == "WoContact":
            if "openState" in context:
                current_data["openState"] = context["openState"]

            if "brightness" in context:
                current_data["brightness"] = context["brightness"]

            if "detectionState" in context:
                current_data["detectionState"] = context["detectionState"]

        # Curtain/Curtain3 already uses slidePosition, battery and calibrate.
        # No transformation needed.

        _LOGGER.warning(
            "Applying webhook update for %s: %s",
            self._device_id,
            current_data,
        )

        self.async_set_updated_data(current_data)