"""Coordinator for local PS5 device status."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from ps5_remoteplay import DeviceNotFound, DeviceStatus, PS5Error, get_device

from .const import DEVICE_SCAN_INTERVAL, PS5_QUERY_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class Ps5ConsoleCoordinator(DataUpdateCoordinator[DeviceStatus | None]):
    """Poll local PS5 status independently from PSN cloud data."""

    def __init__(self, hass: HomeAssistant, host: str) -> None:
        """Initialize the local console coordinator."""
        self.host = host
        super().__init__(
            hass,
            _LOGGER,
            name="PS5 local status",
            update_interval=DEVICE_SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> DeviceStatus | None:
        """Return local device status, or no evidence when the query fails."""
        try:
            return (await get_device(self.host, timeout=PS5_QUERY_TIMEOUT)).status
        except DeviceNotFound:
            _LOGGER.debug("No local PS5 response from %s", self.host)
        except (PS5Error, OSError) as error:
            _LOGGER.warning("Local PS5 query for %s failed: %s", self.host, error)
        except Exception:
            _LOGGER.exception("Unexpected local PS5 query failure for %s", self.host)
        return None
