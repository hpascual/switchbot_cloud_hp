"""SwitchBot Cloud webhook API helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import uuid
from time import time
from typing import Any

from aiohttp import ClientSession


SWITCHBOT_API_HOST = "https://api.switch-bot.com"


def _headers(token: str, secret: str) -> dict[str, str]:
    t = str(int(time() * 1000))
    nonce = str(uuid.uuid4())
    data = token + t + nonce

    sign = base64.b64encode(
        hmac.new(
            secret.encode(),
            msg=data.encode(),
            digestmod=hashlib.sha256,
        ).digest()
    ).decode().upper()

    return {
        "Authorization": token,
        "Content-Type": "application/json",
        "charset": "utf8",
        "t": t,
        "sign": sign,
        "nonce": nonce,
    }


async def async_query_webhook(
    session: ClientSession,
    token: str,
    secret: str,
) -> list[str]:
    """Query registered SwitchBot webhook URLs."""
    response = await session.post(
        f"{SWITCHBOT_API_HOST}/v1.1/webhook/queryWebhook",
        headers=_headers(token, secret),
        json={"action": "queryUrl"},
    )
    data: dict[str, Any] = await response.json()
    return data.get("body", {}).get("urls", []) or []


async def async_delete_webhook(
    session: ClientSession,
    token: str,
    secret: str,
    url: str,
) -> None:
    """Delete a SwitchBot webhook URL."""
    await session.post(
        f"{SWITCHBOT_API_HOST}/v1.1/webhook/deleteWebhook",
        headers=_headers(token, secret),
        json={
            "action": "deleteWebhook",
            "url": url,
        },
    )


async def async_setup_webhook(
    session: ClientSession,
    token: str,
    secret: str,
    url: str,
) -> None:
    """Register SwitchBot webhook URL."""
    await session.post(
        f"{SWITCHBOT_API_HOST}/v1.1/webhook/setupWebhook",
        headers=_headers(token, secret),
        json={
            "action": "setupWebhook",
            "url": url,
            "deviceList": "ALL",
        },
    )