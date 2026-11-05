"""Fetch complete PSN snapshots and recover from temporary service failures."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from psnawp_api.core.psnawp_exceptions import (
    PSNAWPAuthenticationError,
    PSNAWPForbiddenError,
    PSNAWPInvalidTokenError,
    PSNAWPServerError,
    PSNAWPTooManyRequestsError,
    PSNAWPUnauthorizedError,
)
from requests.exceptions import ChunkedEncodingError, SSLError, Timeout
from requests.exceptions import ConnectionError as RequestsConnectionError

from .const import DEVICE_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)
RETRY_DELAY_SECONDS = 2
# PSNAWP 3.0.3 discards Retry-After; use the configured 15-minute rate window.
RATE_LIMIT_DELAY_SECONDS = 15 * 60
TRANSIENT_ERRORS = (
    ConnectionError,
    TimeoutError,
    RequestsConnectionError,
    Timeout,
    ChunkedEncodingError,
    PSNAWPServerError,
)


class PsnCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Data update coordinator for PSN."""

    def __init__(
        self,
        hass: HomeAssistant,
        api,
        user,
        client,
        *,
        config_entry: ConfigEntry | None = None,
    ) -> None:
        """Initialize the Coordinator."""
        super().__init__(
            hass,
            config_entry=config_entry,
            name=DOMAIN,
            logger=_LOGGER,
            update_interval=DEVICE_SCAN_INTERVAL,
        )

        self.hass = hass
        self.entities = []
        self.api = api
        self.user = user
        self.client = client
        self._server_failures = 0
        self.data = {
            "presence": {},
            "available": False,
            "online_status": False,
            "profile": {},
            "platform": {},
            "title_metadata": {},
            "friends": [],
            "trophy_summary": [],
            "title_details": {},
            "title_trophies": {},
            "title_stats": {},
            "username": "",
            "recent_titles": [],
            "country": "",
            "language": "",
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Publish only a complete snapshot; HA owns failure state and log deduplication."""
        self._retry_available = True
        self._operation = "user.online_id"
        data = self.data.copy()
        try:
            data["username"] = await self._async_request(
                "user.online_id", lambda: self.user.online_id
            )
            data["profile"] = await self._async_request(
                "user.profile", self.user.profile
            )
            data["presence"] = await self._async_request(
                "user.get_presence", self.user.get_presence
            )
            presence = data["presence"]["basicPresence"]
            data["available"] = presence.get("availability") == "availableToPlay"
            data["platform"] = presence.get("primaryPlatformInfo") or {}
            title_info = presence.get("gameTitleInfoList") or []
            data["title_metadata"] = title_info[0] if title_info else {}

            data["trophy_summary"] = await self._async_request(
                "client.trophy_summary", self.client.trophy_summary
            )
            data["country"] = self.hass.config.country
            data["language"] = self.hass.config.language
            data["title_details"] = {}
            data["title_trophies"] = {}
            data["recent_titles"] = []

            if (
                data["available"] is True
                and data["title_metadata"].get("npTitleId") is not None
            ):
                title_id = data["title_metadata"]["npTitleId"]
                title = await self._async_request(
                    "api.game_title",
                    lambda: self.api.game_title(
                        title_id=title_id,
                        platform=data["title_metadata"]["format"],
                        account_id="me",
                    ),
                )
                data["title_details"] = await self._async_request(
                    "title.get_details (localized)",
                    lambda: title.get_details(
                        self.hass.config.country, self.hass.config.language
                    ),
                )
                if data["title_details"][0].get("errorCode") is not None:
                    data["title_details"] = await self._async_request(
                        "title.get_details (default locale)", title.get_details
                    )

                # Iterators issue requests during consumption. Recreate and consume
                # them in the executor so a failed iterator is never resumed.
                trophy_titles = await self._async_request(
                    "client.trophy_titles_for_title",
                    lambda: list(
                        self.client.trophy_titles_for_title(title_ids=[title.title_id])
                    ),
                )
                data["title_trophies"] = trophy_titles[-1] if trophy_titles else {}

                data["recent_titles"] = await self._async_request(
                    "client.title_stats",
                    lambda: list(self.client.title_stats(limit=3, page_size=3)),
                )

            self._server_failures = 0
            return data
        except (
            PSNAWPAuthenticationError,
            PSNAWPInvalidTokenError,
            PSNAWPUnauthorizedError,
        ) as error:
            self._server_failures = 0
            raise ConfigEntryAuthFailed(
                f"{self._operation}: PSN authentication failed ({type(error).__name__})"
            ) from error
        except PSNAWPForbiddenError as error:
            self._server_failures = 0
            # A resource/privacy denial is not evidence of expired credentials.
            raise UpdateFailed(
                f"{self._operation}: PSN access forbidden (HTTP 403)"
            ) from error
        except PSNAWPTooManyRequestsError as error:
            self._server_failures = 0
            raise UpdateFailed(
                f"{self._operation}: PSN rate limited (HTTP 429)",
                retry_after=RATE_LIMIT_DELAY_SECONDS,
            ) from error
        except PSNAWPServerError as error:
            self._server_failures = min(self._server_failures + 1, 5)
            raise UpdateFailed(
                f"{self._operation}: PSN request failed (PSNAWPServerError)",
                retry_after=min(30 * 2 ** (self._server_failures - 1), 300),
            ) from error
        except Exception as error:
            self._server_failures = 0
            # Do not log response bodies, account identifiers or request headers.
            raise UpdateFailed(
                f"{self._operation}: PSN request failed ({type(error).__name__})"
            ) from error

    async def _async_request[T](self, operation: str, request: Callable[[], T]) -> T:
        """Allow one extra read attempt per poll, without retrying the whole refresh.

        PSNAWP 3.0.3 and its default Requests adapters have no transport/server
        retries. All attempts still pass through PSNAWP's existing rate limiter.
        """
        self._operation = operation
        try:
            return await self.hass.async_add_executor_job(request)
        except TRANSIENT_ERRORS as error:
            if isinstance(error, SSLError) or not self._retry_available:
                raise
            self._retry_available = False
            _LOGGER.debug(
                "%s failed (%s); retrying once in %s seconds",
                operation,
                type(error).__name__,
                RETRY_DELAY_SECONDS,
            )
            await asyncio.sleep(RETRY_DELAY_SECONDS)
            return await self.hass.async_add_executor_job(request)
