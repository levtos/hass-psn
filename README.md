![GitHub Release](https://img.shields.io/github/v/release/Levtos/hass-psn)
![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/Levtos/hass-psn/total)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://brands.home-assistant.io/playstation_network/dark_logo.png">
  <img alt="PlayStation Network logo" src="https://brands.home-assistant.io/playstation_network/logo.png">
</picture>

## HA-PSN – [PlayStation Network](https://www.psn.com/) for Home Assistant

This is the standalone `Levtos/hass-psn` distribution of the PlayStation Network integration for Home Assistant.

The internal Home Assistant domain remains `playstation_network`. This preserves the existing integration identity while the project is developed and released independently as **HA-PSN**.

This project builds on the original work by [JackJPowell](https://github.com/JackJPowell/hass-psn). It is not affiliated with Sony or Home Assistant.

## Installation

There are two main ways to install this custom component within your Home Assistant instance:

1. Using HACS (see https://hacs.xyz/ for installation instructions if you do not already have it installed):

   [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Levtos&repository=hass-psn&category=Integration)

   Or

   1. From within Home Assistant, click on the link to **HACS**
   2. Click on **Integrations**
   3. Click on the vertical ellipsis in the top right and select **Custom repositories**
   4. Enter `https://github.com/Levtos/hass-psn` and select **Integration**
   5. Click the **ADD** button and install **HA-PSN**
   6. Restart Home Assistant and then proceed with the configuration.

2. Manual installation:
   1. Download or clone this repository.
   2. Copy `custom_components/playstation_network` into the same path on your Home Assistant instance.
   3. Restart Home Assistant and then proceed with the configuration.

## Configuration

After installing the custom component and restarting:

1. Go to **Settings** -> **Devices & Services** -> **Integrations**.
2. Click **+ ADD INTEGRATION**.
3. Search for **Playstation Network** and select it.
4. Supply the NPSSO token from your PlayStation account.

To obtain an NPSSO token:

1. Log in to [PlayStation](https://playstation.com).
2. Open [the Sony SSO cookie endpoint](https://ca.account.sony.com/api/v1/ssocookie).
3. Copy only the alphanumeric value after `npsso`.

## Usage

After the device is configured, the integration exposes:

- A PSN-oriented **Status** sensor (`Playing`, `Online`, or `Offline`).
- A separate physical **Console Status** sensor.
- PlayStation Network trophy sensors.
- A media player with the current game title and cover art.
- Optional top-level sensors for title metadata such as platform, genre, content rating, play count, play duration, and trophy progress.

Enable **Expose attributes as entities** in the integration options to create the additional metadata sensors, including **Genres**.

### Physical Console Status

Set an optional **PS5 host or IP address** in the integration options to query the console directly on the local network. A fixed or DHCP-reserved address is recommended. The status query uses `ps5-remoteplay` and does not require Remote Play pairing or credentials.

The physical status follows these rules:

- Local `STANDBY` -> `Rest Mode`.
- Local `AWAKE` with an active PSN title -> `Playing`.
- Local `AWAKE` without an active title -> `Online`.
- No local response plus valid power at or below the configured threshold -> `Offline`.
- No local response plus high, missing, or invalid power -> entity unavailable.

After previously valid local evidence, a temporary discovery gap keeps the last Console Status for up to 45 seconds. New local `AWAKE` or `STANDBY` evidence is applied immediately; after the grace expires, the normal power fallback and availability rules resume. This grace is runtime-only and is not persisted across Home Assistant restarts.

The optional power sensor is fallback evidence for `Offline`; it does not detect `Rest Mode`. PSN alone never creates a positive physical console state, so using the PlayStation mobile app cannot make an unreachable console appear online. Without a configured PS5 host, the existing PSN entities continue to work unchanged; the Console Status entity requires conclusive local or low-power evidence to become available.

## Messages

The existing `notify.playstation_network` action can send PlayStation Network messages to a user or group. Notifications are retained for compatibility but are not part of the initial HA-PSN feature focus.

## Development focus

The initial standalone line focuses on reliable Home Assistant compatibility, useful game metadata for media logic, and selected features that are valuable for this installation. Core changes will be reviewed and adopted selectively rather than copied wholesale.

## About this project

HA-PSN is an independent community project based on the original PlayStation Network integration. It is not associated with Sony, Sony Interactive Entertainment, or Home Assistant.
