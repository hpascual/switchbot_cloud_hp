"""Tests for robust command delivery in SwitchBot Cloud Push."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
import pytest
from homeassistant.exceptions import HomeAssistantError
from switchbot_api import CommonCommands

from custom_components.switchbot_cloud_hp.button import (
    ART_FRAME_NEXT_BUTTON_DESCRIPTION,
    SwitchBotCloudBot,
)
from custom_components.switchbot_cloud_hp.entity import SwitchBotCloudEntity


class FakeAPI:
    """Minimal SwitchBot API double that records commands."""

    def __init__(self, responses: list[Any]) -> None:
        """Initialize with a queue of responses or exceptions."""
        self._responses = list(responses)
        self.calls: list[tuple[Any, ...]] = []

    async def send_command(
        self,
        device_id: str,
        command: Any,
        command_type: str,
        parameters: Any,
    ) -> Any:
        """Record the command and return or raise the next programmed response."""
        self.calls.append((device_id, command, command_type, parameters))
        response = self._responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def rate_limit_error(headers: dict[str, str] | None = None) -> Exception:
    """Reproduce the ContentTypeError raised by switchbot-api on a 429 response."""
    return aiohttp.ContentTypeError(
        request_info=None,
        history=(),
        status=429,
        message="Attempt to decode JSON with unexpected mimetype: ",
        headers=headers or {},
    )


def make_entity(api: FakeAPI, device_id: str = "DEV0001") -> SwitchBotCloudEntity:
    """Build a bare entity without the Home Assistant coordinator harness."""
    entity = object.__new__(SwitchBotCloudEntity)
    entity._api = api
    entity._device_id = device_id
    entity._attr_unique_id = device_id
    return entity


@pytest.fixture
def sleep_spy(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Capture backoff delays instead of waiting for real."""
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    return delays


async def test_success_sends_single_command(sleep_spy: list[float]) -> None:
    """A healthy API receives exactly one command and no backoff wait."""
    api = FakeAPI([None])
    entity = make_entity(api)

    await entity.send_api_command(CommonCommands.ON)

    assert len(api.calls) == 1
    assert api.calls[0][0] == "DEV0001"
    assert sleep_spy == []


async def test_retries_rate_limit_then_succeeds(sleep_spy: list[float]) -> None:
    """A 429 is retried with exponential backoff until the command succeeds."""
    api = FakeAPI([rate_limit_error(), rate_limit_error(), None])
    entity = make_entity(api)

    await entity.send_api_command(CommonCommands.ON)

    assert len(api.calls) == 3
    assert sleep_spy == [1.0, 2.0]


async def test_rate_limit_exhaustion_raises_readable_error(sleep_spy: list[float]) -> None:
    """Exhausted retries raise HomeAssistantError after the configured attempts."""
    api = FakeAPI(
        [rate_limit_error(), rate_limit_error(), rate_limit_error()]
    )
    entity = make_entity(api)

    with pytest.raises(HomeAssistantError, match="rate limit"):
        await entity.send_api_command(CommonCommands.ON)

    assert len(api.calls) == 3
    assert sleep_spy == [1.0, 2.0]


async def test_non_idempotent_command_is_not_retried(sleep_spy: list[float]) -> None:
    """Commands marked as non-idempotent fail on the first 429 without retrying."""
    api = FakeAPI([rate_limit_error()])
    entity = make_entity(api)

    with pytest.raises(HomeAssistantError, match="rate limit"):
        await entity.send_api_command(CommonCommands.PRESS, retry_on_rate_limit=False)

    assert len(api.calls) == 1
    assert sleep_spy == []


async def test_retry_after_header_is_respected(sleep_spy: list[float]) -> None:
    """A Retry-After header dictates the wait before the next attempt."""
    api = FakeAPI([rate_limit_error({"Retry-After": "2"}), None])
    entity = make_entity(api)

    await entity.send_api_command(CommonCommands.ON)

    assert len(api.calls) == 2
    assert sleep_spy == [2.0]


async def test_retry_after_beyond_max_aborts(sleep_spy: list[float]) -> None:
    """A Retry-After longer than the allowed maximum aborts without waiting."""
    api = FakeAPI([rate_limit_error({"Retry-After": "60"})])
    entity = make_entity(api)

    with pytest.raises(HomeAssistantError, match="longer than"):
        await entity.send_api_command(CommonCommands.ON)

    assert len(api.calls) == 1
    assert sleep_spy == []


async def test_client_error_is_translated(sleep_spy: list[float]) -> None:
    """Transport errors become a readable HomeAssistantError."""
    api = FakeAPI([aiohttp.ClientConnectionError("boom")])
    entity = make_entity(api)

    with pytest.raises(HomeAssistantError, match="Could not reach"):
        await entity.send_api_command(CommonCommands.ON)

    assert len(api.calls) == 1


async def test_timeout_is_translated(sleep_spy: list[float]) -> None:
    """Timeouts become a readable HomeAssistantError without retrying."""
    api = FakeAPI([TimeoutError()])
    entity = make_entity(api)

    with pytest.raises(HomeAssistantError, match="Timed out"):
        await entity.send_api_command(CommonCommands.ON)

    assert len(api.calls) == 1
    assert sleep_spy == []


def make_button(
    api: FakeAPI,
    device_id: str,
    unique_id: str,
) -> SwitchBotCloudBot:
    """Build a bare AI Art Frame button without the entity registry harness."""
    button = object.__new__(SwitchBotCloudBot)
    button._api = api
    button._device_id = device_id
    button._attr_unique_id = unique_id
    button.entity_description = ART_FRAME_NEXT_BUTTON_DESCRIPTION
    return button


async def test_art_frame_button_sends_device_id_without_suffix(
    sleep_spy: list[float],
) -> None:
    """AI Art Frame buttons send the device MAC, not the suffixed unique ID."""
    api = FakeAPI([None])
    button = make_button(api, "FE70648E46FB", "FE70648E46FB-next")

    await button.async_press()

    assert len(api.calls) == 1
    assert api.calls[0][0] == "FE70648E46FB"
    assert api.calls[0][1] == ART_FRAME_NEXT_BUTTON_DESCRIPTION.command
    assert sleep_spy == []
