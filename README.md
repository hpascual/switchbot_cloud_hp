# SwitchBot Cloud Push

Real-time SwitchBot Cloud integration for Home Assistant using webhook push updates.

This custom integration is based on the native Home Assistant SwitchBot Cloud integration, but extends it with support for SwitchBot Cloud webhooks so devices can update Home Assistant almost instantly without aggressive API polling.

---

## Main Features

- Real-time updates using SwitchBot Cloud webhooks
- Automatic webhook registration in SwitchBot Cloud
- Slow fallback polling for reliability
- Reduced SwitchBot Cloud API usage
- Compatible with Nabu Casa, DuckDNS, reverse proxies and Cloudflare Tunnel
- Preserves compatibility with existing SwitchBot Cloud entities
- Supports both local BLE and cloud workflows

---

## Why this integration exists

The native SwitchBot Cloud integration relies primarily on polling the SwitchBot Cloud API.

Polling every few seconds is not practical because SwitchBot Cloud has a daily API request limit.

This integration solves the problem by using:

1. **Webhook push updates** for real-time changes
2. **Slow periodic polling** as a fallback mechanism

The result is:

- Faster updates
- Lower API usage
- Better responsiveness
- Lower risk of hitting SwitchBot Cloud limits

---

## How it works

When a device changes state:

```text
SwitchBot Device
        ↓
SwitchBot Cloud
        ↓
Webhook HTTPS Request
        ↓
Home Assistant Webhook Endpoint
        ↓
SwitchBot Cloud Push Integration
        ↓
Coordinator Update
        ↓
Entity State Update
```

The integration automatically:

- Creates a Home Assistant webhook endpoint
- Registers the webhook URL in SwitchBot Cloud
- Receives push events
- Updates entities immediately

---

## Tested Device Types

Currently tested with:

- Contact Sensor
- Water Detector
- Curtain 3

Observed webhook payload attributes include:

- `openState`
- `detectionState`
- `battery`
- `brightness`
- `slidePosition`
- `calibrate`

Additional SwitchBot devices may also work depending on the payloads exposed by SwitchBot Cloud.

---

## Requirements

You need:

- Home Assistant
- Internet access
- A public HTTPS URL reachable from the internet
- SwitchBot Cloud API Token
- SwitchBot Cloud API Secret

---

## Supported Public URL Examples

### Nabu Casa

```text
https://xxxx.ui.nabu.casa
```

### DuckDNS

```text
https://your-domain.duckdns.org
```

### Reverse Proxy

```text
https://ha.yourdomain.com
```

### Cloudflare Tunnel

```text
https://ha.yourdomain.com
```

Do NOT include:

```text
/api/webhook/...
```

The integration generates the webhook path automatically.

---

## Installation via HACS

### Step 1 — Add Custom Repository

1. Open HACS
2. Go to Integrations
3. Click the three-dot menu
4. Select Custom repositories
5. Add this repository:

```text
https://github.com/hpascual/switchbot_cloud_hp
```

6. Category:

```text
Integration
```

### Step 2 — Install

1. Search for:

```text
SwitchBot Cloud Push
```

2. Install the integration
3. Restart Home Assistant

---

## Configuration

Go to:

```text
Settings → Devices & Services → Add Integration
```

Search for:

```text
SwitchBot Cloud Push
```

You will be asked for:

### SwitchBot API Token

Generate it from the SwitchBot mobile app.

### SwitchBot API Secret

Generate it from the SwitchBot mobile app.

### Public Home Assistant URL

Examples:

```text
https://xxxx.ui.nabu.casa
https://your-domain.duckdns.org
https://ha.yourdomain.com
```

### Automatically register webhook

Recommended:

```text
Enabled
```

When enabled, the integration automatically:

- Creates the webhook endpoint in Home Assistant
- Registers the webhook in SwitchBot Cloud
- Replaces previous SwitchBot webhook URLs if necessary

---

## Automatic Webhook Registration

SwitchBot Cloud appears to support only one webhook URL per API account.

When the integration starts:

1. It queries existing webhook URLs
2. Removes old webhook URLs if needed
3. Registers the current Home Assistant webhook URL

The generated webhook URL looks like:

```text
https://your-domain/api/webhook/switchbot_cloud_hp_ENTRY_ID
```

---

## Recommended Architecture

### Best Performance

Recommended setup:

- Native SwitchBot BLE integration for local Bluetooth devices
- SwitchBot Cloud Push for remote/cloud webhook updates

This gives:

- Fast local BLE updates
- Real-time cloud events
- Reliable fallback polling

---

## Troubleshooting

### Webhook not updating entities

Verify:

- Public URL is reachable from the internet
- HTTPS certificate is valid
- SwitchBot webhook is correctly registered
- Home Assistant webhook endpoint exists

### Home Assistant logs

Enable debug logs:

```yaml
logger:
  logs:
    custom_components.switchbot_cloud_hp: debug
```

---

## Polling Strategy

This integration intentionally uses slow polling.

Default fallback polling interval:

```text
10 minutes
```

Real-time updates are expected to arrive through webhooks.

---

## Security Notes

- Your Home Assistant instance becomes reachable through a public HTTPS URL
- Use HTTPS only
- Use strong Home Assistant credentials
- Prefer Nabu Casa, Cloudflare Tunnel or properly secured reverse proxies

---

## Credits

Based on the native Home Assistant SwitchBot Cloud integration.

Extended with webhook push support by Hugo Pascual.