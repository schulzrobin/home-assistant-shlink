# Shlink for Home Assistant

A custom Home Assistant integration for [Shlink](https://shlink.io/), the self-hosted URL shortener.

The integration connects directly to the Shlink REST API and exposes your Shlink instance and every short URL as Home Assistant devices and sensors.

> This is a community integration and is not an official Shlink integration.

## Features

### Shlink device

The main **Shlink** device provides:

| Entity | Description |
|---|---|
| Kurzlinks | Number of short URLs |
| Total | Total non-orphan visits |
| NonBots | Visits identified as non-bot traffic |
| Bots | Visits identified as bot traffic |
| Orphan Views | Visits not associated with an existing short URL |

### One device per short URL

Every Shlink short URL is automatically represented as its own Home Assistant device.

Each device provides:

| Entity | Description |
|---|---|
| Besuche | Total visits |
| Besuche heute | Visits today |
| Besuche gestern | Visits yesterday |
| Besuche letzte 7 Tage | Visits in the current 7-day window |
| Besuche letzte 30 Tage | Visits in the current 30-day window |
| Short URL | Complete short URL |
| Long URL | Destination URL |

The total visit sensor also exposes useful attributes such as the short code, domain, title, tags, creation date, validity limits, maximum visits and crawlable state.

New short URLs are discovered automatically.

## Requirements

- Home Assistant 2026.3.0 or newer
- A reachable Shlink instance
- A Shlink API key with permission to read short URLs and visit statistics

## Installation with HACS

### Custom repository

Until this repository is included in the default HACS repository list:

1. Open **HACS** in Home Assistant.
2. Open the menu in the top-right corner.
3. Select **Custom repositories**.
4. Add this repository:
   `https://github.com/schulzrobin/home-assistant-shlink`
5. Select **Integration** as the category.
6. Install **Shlink**.
7. Restart Home Assistant.

After the restart go to:

**Settings → Devices & services → Add integration → Shlink**

## Manual installation

Copy:

```text
custom_components/shlink
```

to:

```text
/config/custom_components/shlink
```

Restart Home Assistant and add **Shlink** from **Settings → Devices & services**.

## Configuration

The integration is configured completely through the Home Assistant UI.

You need:

- **Shlink URL** — the base URL of your Shlink server, for example `https://s.example.com`
- **API key** — your Shlink API key
- **Verify SSL certificate** — disable only when required for an internal/self-signed setup

No YAML configuration is required.

## Update interval

Shlink is polled every **5 minutes**.

Period statistics use the timezone configured in Home Assistant.

## Devices and entities

Example:

```text
Shlink
├── Kurzlinks
├── Total
├── NonBots
├── Bots
└── Orphan Views

Shlink – Home Assistant
├── Besuche
├── Besuche heute
├── Besuche gestern
├── Besuche letzte 7 Tage
├── Besuche letzte 30 Tage
├── Short URL
└── Long URL
```

## API compatibility

The integration prefers the Shlink REST API v3 and has a v2 fallback for basic API detection.

Visit statistics are read from Shlink's REST API. The integration uses the visit summaries returned by current Shlink versions and retains compatibility with older per-link visit counters where possible.

## Troubleshooting

Enable debug logging from Home Assistant's integration troubleshooting controls, then reproduce the problem and inspect the Home Assistant log.

When reporting an issue, never include your Shlink API key.

## Updating

When installed through HACS, future releases can be installed from HACS.

For manual installations, replace `custom_components/shlink` with the files from the new release and restart Home Assistant.

## License

This Home Assistant integration is released under the MIT License.

Shlink is a separate project. Shlink names and branding belong to their respective owners.

## Credits

- [Shlink](https://shlink.io/) for the self-hosted URL shortener and REST API.
- [Home Assistant](https://www.home-assistant.io/) for the home automation platform.
- [HACS](https://www.hacs.xyz/) for custom integration distribution.
