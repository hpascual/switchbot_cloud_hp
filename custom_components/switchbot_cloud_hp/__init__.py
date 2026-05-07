"""SwitchBot via API integration."""

from __future__ import annotations

from asyncio import gather
from dataclasses import dataclass, field
from logging import getLogger
from typing import Any

from aiohttp import web
from switchbot_api import (
    Device,
    Remote,
    SwitchBotAPI,
    SwitchBotAuthenticationError,
    SwitchBotConnectionError,
)

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, ENTRY_TITLE
from .coordinator import SwitchBotCoordinator

_LOGGER = getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.FAN,
    Platform.HUMIDIFIER,
    Platform.IMAGE,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.VACUUM,
]


@dataclass
class SwitchbotDevices:
    """Switchbot devices data."""

    binary_sensors: list[tuple[Device, SwitchBotCoordinator]] = field(
        default_factory=list
    )
    buttons: list[tuple[Device, SwitchBotCoordinator]] = field(default_factory=list)
    climates: list[tuple[Remote | Device, SwitchBotCoordinator]] = field(
        default_factory=list
    )
    covers: list[tuple[Device, SwitchBotCoordinator]] = field(default_factory=list)
    switches: list[tuple[Device | Remote, SwitchBotCoordinator]] = field(
        default_factory=list
    )
    sensors: list[tuple[Device, SwitchBotCoordinator]] = field(default_factory=list)
    vacuums: list[tuple[Device, SwitchBotCoordinator]] = field(default_factory=list)
    locks: list[tuple[Device, SwitchBotCoordinator]] = field(default_factory=list)
    fans: list[tuple[Device, SwitchBotCoordinator]] = field(default_factory=list)
    lights: list[tuple[Device, SwitchBotCoordinator]] = field(default_factory=list)
    humidifiers: list[tuple[Device, SwitchBotCoordinator]] = field(default_factory=list)
    images: list[tuple[Device, SwitchBotCoordinator]] = field(default_factory=list)


@dataclass
class SwitchbotCloudData:
    """Data to use in platforms."""

    api: SwitchBotAPI
    devices: SwitchbotDevices


type SwitchbotCloudConfigEntry = ConfigEntry[SwitchbotCloudData]


def _normalize_mac(value: str | None) -> str:
    """Normalize MAC/device id for matching webhook payloads."""
    if not value:
        return ""
    return value.replace(":", "").replace("-", "").upper()


def _webhook_id(entry: SwitchbotCloudConfigEntry) -> str:
    """Return stable Home Assistant webhook id for this config entry."""
    return f"{DOMAIN}_{entry.entry_id}"


def _store_coordinators(
    hass: HomeAssistant,
    entry: SwitchbotCloudConfigEntry,
    coordinators_by_id: dict[str, SwitchBotCoordinator],
) -> None:
    """Store coordinators for webhook lookup."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinators_by_id": coordinators_by_id,
    }


def _find_coordinator_for_webhook(
    hass: HomeAssistant,
    entry: SwitchbotCloudConfigEntry,
    device_mac: str,
) -> SwitchBotCoordinator | None:
    """Find coordinator by SwitchBot webhook deviceMac."""
    domain_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})

    coordinators_by_id: dict[str, SwitchBotCoordinator] = domain_data.get(
        "coordinators_by_id",
        {},
    )

    normalized_mac = _normalize_mac(device_mac)

    return coordinators_by_id.get(normalized_mac)

async def _handle_switchbot_webhook(
    hass: HomeAssistant,
    entry: SwitchbotCloudConfigEntry,
    request: web.Request,
) -> web.Response:
    """Handle SwitchBot Cloud webhook callback."""
    try:
        payload: dict[str, Any] = await request.json()
    except Exception:
        _LOGGER.exception("Invalid SwitchBot webhook payload")
        return web.json_response({"ok": False, "error": "invalid_json"}, status=400)

    _LOGGER.warning("Received SwitchBot webhook payload: %s", payload)

    context = payload.get("context")
    if not isinstance(context, dict):
        _LOGGER.warning("SwitchBot webhook payload without valid context: %s", payload)
        return web.json_response({"ok": False, "error": "missing_context"}, status=400)

    device_mac = _normalize_mac(context.get("deviceMac"))
    if not device_mac:
        _LOGGER.warning("SwitchBot webhook context without deviceMac: %s", context)
        return web.json_response({"ok": False, "error": "missing_device_mac"}, status=400)

    coordinator = _find_coordinator_for_webhook(hass, entry, device_mac)
    if coordinator is None:
        _LOGGER.warning(
            "No coordinator found for SwitchBot webhook deviceMac %s. Context: %s",
            device_mac,
            context,
        )
        return web.json_response({"ok": True, "matched": False})

    coordinator.async_apply_webhook_payload(context)

    return web.json_response(
        {
            "ok": True,
            "matched": True,
            "deviceMac": device_mac,
            "deviceType": context.get("deviceType"),
        }
    )


def _register_webhook(
    hass: HomeAssistant,
    entry: SwitchbotCloudConfigEntry,
) -> None:
    """Register Home Assistant webhook endpoint."""
    webhook_id = _webhook_id(entry)

    async def handle_webhook(
        hass: HomeAssistant,
        webhook_id: str,
        request: web.Request,
    ) -> web.Response:
        """Handle incoming webhook request."""
        return await _handle_switchbot_webhook(hass, entry, request)

    webhook.async_register(
        hass,
        DOMAIN,
        ENTRY_TITLE,
        webhook_id,
        handle_webhook,
        local_only=False,
    )

    _LOGGER.info(
        "Registered SwitchBot Cloud HP webhook. Webhook path: /api/webhook/%s",
        webhook_id,
    )


def _unregister_webhook(
    hass: HomeAssistant,
    entry: SwitchbotCloudConfigEntry,
) -> None:
    """Unregister Home Assistant webhook endpoint."""
    webhook_id = _webhook_id(entry)
    webhook.async_unregister(hass, webhook_id)
    _LOGGER.info("Unregistered SwitchBot Cloud HP webhook %s", webhook_id)


async def coordinator_for_device(
    hass: HomeAssistant,
    entry: SwitchbotCloudConfigEntry,
    api: SwitchBotAPI,
    device: Device | Remote,
    coordinators_by_id: dict[str, SwitchBotCoordinator],
    manageable_by_webhook: bool = False,
) -> SwitchBotCoordinator:
    """Instantiate coordinator and adds to list for gathering."""
    coordinator = coordinators_by_id.setdefault(
        device.device_id,
        SwitchBotCoordinator(hass, entry, api, device, manageable_by_webhook),
    )

    if coordinator.data is None:
        await coordinator.async_config_entry_first_refresh()

    return coordinator


async def make_switchbot_devices(
    hass: HomeAssistant,
    entry: SwitchbotCloudConfigEntry,
    api: SwitchBotAPI,
    devices: list[Device | Remote],
    coordinators_by_id: dict[str, SwitchBotCoordinator],
) -> SwitchbotDevices:
    """Make SwitchBot devices."""
    devices_data = SwitchbotDevices()
    await gather(
        *[
            make_device_data(hass, entry, api, device, devices_data, coordinators_by_id)
            for device in devices
        ]
    )
    return devices_data


async def make_device_data(
    hass: HomeAssistant,
    entry: SwitchbotCloudConfigEntry,
    api: SwitchBotAPI,
    device: Device | Remote,
    devices_data: SwitchbotDevices,
    coordinators_by_id: dict[str, SwitchBotCoordinator],
) -> None:
    """Make device data."""
    if isinstance(device, Remote) and device.device_type.endswith("Air Conditioner"):
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id
        )
        devices_data.climates.append((device, coordinator))

    if (
        isinstance(device, Remote | Device)
        and device.device_type == "Smart Radiator Thermostat"
    ):
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id
        )
        devices_data.climates.append((device, coordinator))
        devices_data.sensors.append((device, coordinator))

    if (
        isinstance(device, Device)
        and (
            device.device_type.startswith("Plug")
            or device.device_type in ["Relay Switch 1PM", "Relay Switch 1"]
        )
    ) or isinstance(device, Remote):
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id
        )
        devices_data.switches.append((device, coordinator))

    if isinstance(device, Device) and device.device_type in [
        "Meter",
        "MeterPlus",
        "WoIOSensor",
        "Hub 2",
        "MeterPro",
        "MeterPro(CO2)",
        "Relay Switch 1PM",
        "Plug Mini (US)",
        "Plug Mini (JP)",
        "Plug Mini (EU)",
    ]:
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id
        )
        devices_data.sensors.append((device, coordinator))

    if isinstance(device, Device) and device.device_type in [
        "K10+",
        "K10+ Pro",
        "Robot Vacuum Cleaner S1",
        "Robot Vacuum Cleaner S1 Plus",
        "K20+ Pro",
        "Robot Vacuum Cleaner K10+ Pro Combo",
        "Robot Vacuum Cleaner S10",
        "Robot Vacuum Cleaner S20",
        "S20",
        "Robot Vacuum Cleaner K11 Plus",
    ]:
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id, True
        )
        devices_data.vacuums.append((device, coordinator))

    if isinstance(device, Device) and device.device_type in [
        "Smart Lock",
        "Smart Lock Lite",
        "Smart Lock Pro",
        "Smart Lock Ultra",
        "Smart Lock Vision",
        "Smart Lock Vision Pro",
        "Smart Lock Pro Wifi",
        "Lock Vision",
        "Lock Vision Pro",
    ]:
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id
        )
        devices_data.locks.append((device, coordinator))
        devices_data.sensors.append((device, coordinator))
        devices_data.binary_sensors.append((device, coordinator))

    if isinstance(device, Device) and device.device_type == "Bot":
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id, True
        )
        devices_data.sensors.append((device, coordinator))
        if coordinator.data is not None:
            if coordinator.data.get("deviceMode") == "pressMode":
                devices_data.buttons.append((device, coordinator))
            else:
                devices_data.switches.append((device, coordinator))

    if isinstance(device, Device) and device.device_type == "Relay Switch 2PM":
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id
        )
        devices_data.sensors.append((device, coordinator))
        devices_data.switches.append((device, coordinator))

    if isinstance(device, Device) and device.device_type.startswith("Air Purifier"):
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id
        )
        devices_data.fans.append((device, coordinator))

    if isinstance(device, Device) and device.device_type in [
        "Motion Sensor",
        "Contact Sensor",
        "Presence Sensor",
    ]:
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id, True
        )
        devices_data.sensors.append((device, coordinator))
        devices_data.binary_sensors.append((device, coordinator))

    if isinstance(device, Device) and device.device_type == "Hub 3":
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id, True
        )
        devices_data.sensors.append((device, coordinator))
        devices_data.binary_sensors.append((device, coordinator))

    if isinstance(device, Device) and device.device_type == "Water Detector":
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id, True
        )
        devices_data.binary_sensors.append((device, coordinator))
        devices_data.sensors.append((device, coordinator))

    if isinstance(device, Device) and device.device_type in [
        "Battery Circulator Fan",
        "Standing Fan",
    ]:
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id
        )
        devices_data.fans.append((device, coordinator))
        devices_data.sensors.append((device, coordinator))

    if isinstance(device, Device) and device.device_type == "Circulator Fan":
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id
        )
        devices_data.fans.append((device, coordinator))

    if isinstance(device, Device) and device.device_type in [
        "Curtain",
        "Curtain3",
        "Roller Shade",
        "Blind Tilt",
    ]:
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id, True
        )
        devices_data.covers.append((device, coordinator))
        devices_data.binary_sensors.append((device, coordinator))
        devices_data.sensors.append((device, coordinator))

    if isinstance(device, Device) and device.device_type == "Garage Door Opener":
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id
        )
        devices_data.covers.append((device, coordinator))
        devices_data.binary_sensors.append((device, coordinator))

    if isinstance(device, Device) and device.device_type in [
        "Strip Light",
        "Strip Light 3",
        "Floor Lamp",
        "Color Bulb",
        "RGBICWW Floor Lamp",
        "RGBICWW Strip Light",
        "Ceiling Light",
        "Ceiling Light Pro",
        "RGBIC Neon Rope Light",
        "RGBIC Neon Wire Rope Light",
        "Candle Warmer Lamp",
    ]:
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id
        )
        devices_data.lights.append((device, coordinator))

    if isinstance(device, Device) and device.device_type == "Humidifier2":
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id
        )
        devices_data.humidifiers.append((device, coordinator))

    if isinstance(device, Device) and device.device_type == "Humidifier":
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id
        )
        devices_data.humidifiers.append((device, coordinator))
        devices_data.sensors.append((device, coordinator))

    if isinstance(device, Device) and device.device_type == "Climate Panel":
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id
        )
        devices_data.binary_sensors.append((device, coordinator))
        devices_data.sensors.append((device, coordinator))

    if isinstance(device, Device) and device.device_type == "AI Art Frame":
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id
        )
        devices_data.buttons.append((device, coordinator))
        devices_data.sensors.append((device, coordinator))
        devices_data.images.append((device, coordinator))

    if isinstance(device, Device) and device.device_type == "WeatherStation":
        coordinator = await coordinator_for_device(
            hass, entry, api, device, coordinators_by_id
        )
        devices_data.sensors.append((device, coordinator))


async def async_setup_entry(
    hass: HomeAssistant, entry: SwitchbotCloudConfigEntry
) -> bool:
    """Set up SwitchBot via API from a config entry."""
    token = entry.data[CONF_API_TOKEN]
    secret = entry.data[CONF_API_KEY]

    api = SwitchBotAPI(
        token=token,
        secret=secret,
        session=async_get_clientsession(hass),
    )

    try:
        devices = await api.list_devices()
    except SwitchBotAuthenticationError as ex:
        _LOGGER.error(
            "Invalid authentication while connecting to SwitchBot API: %s", ex
        )
        return False
    except SwitchBotConnectionError as ex:
        raise ConfigEntryNotReady from ex

    _LOGGER.warning("Devices: %s", devices)

    coordinators_by_id: dict[str, SwitchBotCoordinator] = {}

    switchbot_devices = await make_switchbot_devices(
        hass,
        entry,
        api,
        devices,
        coordinators_by_id,
    )

    entry.runtime_data = SwitchbotCloudData(
        api=api,
        devices=switchbot_devices,
    )

    _store_coordinators(hass, entry, coordinators_by_id)
    _register_webhook(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: SwitchbotCloudConfigEntry,
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        _unregister_webhook(hass, entry)

        if DOMAIN in hass.data:
            hass.data[DOMAIN].pop(entry.entry_id, None)

            if not hass.data[DOMAIN]:
                hass.data.pop(DOMAIN)

    return unload_ok