"""PSN failure regressions using the real HA coordinator and pinned PSNAWP."""

import asyncio
import json
import logging
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed
from psnawp_api.core.psnawp_exceptions import (
    PSNAWPAuthenticationError,
    PSNAWPBadRequestError,
    PSNAWPForbiddenError,
    PSNAWPInvalidTokenError,
    PSNAWPNotFoundError,
    PSNAWPServerError,
    PSNAWPTooManyRequestsError,
    PSNAWPUnauthorizedError,
)
from psnawp_api.core.request_builder import RequestBuilder, response_checker
from requests import Response, Session
from requests.exceptions import ChunkedEncodingError, ConnectionError, SSLError, Timeout

from custom_components import playstation_network as integration
from custom_components.playstation_network import coordinator as coordinator_module
from custom_components.playstation_network.coordinator import PsnCoordinator
from custom_components.playstation_network.media_player import MediaPlayer
from custom_components.playstation_network.sensor import (
    PSN_ADDITIONAL_SENSOR,
    PSN_SENSOR,
    PsnAttributeSensor,
    PsnSensor,
)

pytestmark = pytest.mark.asyncio


def presence(title_id="TEST00001"):
    """Return synthetic PSN data without private account or media information."""
    return {
        "basicPresence": {
            "availability": "availableToPlay" if title_id else "unavailable",
            "primaryPlatformInfo": {"onlineStatus": "online", "platform": "PS5"},
            "gameTitleInfoList": (
                [{"npTitleId": title_id, "format": "PS5", "titleName": title_id}]
                if title_id
                else []
            ),
        }
    }


@pytest_asyncio.fixture
async def psn(tmp_path, monkeypatch):
    hass = HomeAssistant(str(tmp_path))
    hass.config.country = "DE"
    hass.config.language = "de"
    user = SimpleNamespace(
        online_id="test-account",
        profile=Mock(return_value={"aboutMe": "test profile"}),
        get_presence=Mock(return_value=presence()),
    )
    title = SimpleNamespace(
        title_id="TEST00001", get_details=Mock(return_value=[{"name": "Test title"}])
    )
    client = SimpleNamespace(
        trophy_summary=Mock(return_value={"test": "summary"}),
        trophy_titles_for_title=Mock(return_value=[{"test": "trophies"}]),
        title_stats=Mock(return_value=[{"test": "stats"}]),
    )
    api = SimpleNamespace(game_title=Mock(return_value=title))
    backoff = AsyncMock()
    monkeypatch.setattr(coordinator_module, "asyncio", SimpleNamespace(sleep=backoff))
    coordinator = PsnCoordinator(hass, api, user, client)
    try:
        yield SimpleNamespace(
            hass=hass,
            coordinator=coordinator,
            user=user,
            client=client,
            api=api,
            title=title,
            backoff=backoff,
        )
    finally:
        await coordinator.async_shutdown()
        await hass.async_stop(force=True)


def errors(caplog):
    return [record for record in caplog.records if record.levelno >= logging.ERROR]


@pytest.mark.parametrize(
    "failure",
    [
        ConnectionResetError(104, "Connection reset by peer"),
        ConnectionError("wrapped connection reset"),
        Timeout("read timeout"),
        TimeoutError(),
        ChunkedEncodingError("interrupted body"),
        PSNAWPServerError("Internal Server error"),
    ],
)
async def test_transient_retry_recovers_without_error_log(psn, caplog, failure):
    psn.user.get_presence.side_effect = [failure, presence()]
    await psn.coordinator.async_refresh()

    assert psn.coordinator.last_update_success
    assert psn.user.get_presence.call_count == 2
    assert psn.user.profile.call_count == 1  # no whole-refresh retry
    assert psn.client.trophy_summary.call_count == 1
    psn.backoff.assert_awaited_once_with(2)
    assert psn.coordinator.data["title_metadata"]["npTitleId"] == "TEST00001"
    assert not errors(caplog)


@pytest.mark.parametrize("failure", [ConnectionResetError, PSNAWPServerError])
async def test_outage_is_atomic_deduplicated_and_recovers_on_poll(psn, caplog, failure):
    coordinator = psn.coordinator
    caplog.set_level(logging.INFO, logger=coordinator.logger.name)
    notifications = Mock()
    remove_listener = coordinator.async_add_listener(notifications)
    await coordinator.async_refresh()
    previous = coordinator.data
    previous_contents = deepcopy(previous)
    psn.user.profile.return_value = {"aboutMe": "updated"}
    psn.user.get_presence.return_value = presence("TEST00002")
    psn.client.title_stats.side_effect = failure("temporary failure")
    caplog.clear()

    for _ in range(5):
        coordinator._async_unsub_refresh()
        await coordinator._handle_refresh_interval()
        assert coordinator.data is previous
        assert coordinator.data == previous_contents
        assert not coordinator.last_update_success
        assert isinstance(coordinator.last_exception, UpdateFailed)
        assert "client.title_stats" in str(coordinator.last_exception)
        assert coordinator._unsub_refresh is not None  # normal polling still armed

    assert len(errors(caplog)) == 1
    assert psn.backoff.await_count == 5
    assert psn.client.title_stats.call_count == 11  # success, then two per poll

    psn.client.title_stats.side_effect = None
    coordinator._async_unsub_refresh()
    await coordinator._handle_refresh_interval()
    assert coordinator.last_update_success
    # HA retains last_exception as history; last_update_success defines freshness.
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert coordinator.data is not previous
    assert coordinator.data["profile"] == {"aboutMe": "updated"}
    assert coordinator.data["title_metadata"]["npTitleId"] == "TEST00002"
    assert previous == previous_contents
    assert len(errors(caplog)) == 1
    # HA notifies on success, the first failure and recovery, not repeated failures.
    assert notifications.call_count == 3
    assert sum("data recovered" in record.message for record in caplog.records) == 1
    remove_listener()


async def test_only_one_retry_budget_for_entire_poll(psn):
    psn.user.profile.side_effect = [PSNAWPServerError("temporary"), {}]
    psn.user.get_presence.side_effect = ConnectionResetError(104, "reset")
    await psn.coordinator.async_refresh()
    assert psn.user.profile.call_count == 2
    assert psn.user.get_presence.call_count == 1
    assert psn.client.trophy_summary.call_count == 0
    psn.backoff.assert_awaited_once_with(2)
    assert not psn.coordinator.last_update_success


@pytest.mark.parametrize("operation", ["trophy_titles_for_title", "title_stats"])
async def test_lazy_iterator_is_recreated_and_partial_result_discarded(psn, operation):
    def interrupted():
        yield {"partial": True}
        raise ConnectionResetError(104, "reset during iteration")

    method = getattr(psn.client, operation)
    method.side_effect = [interrupted(), iter([{"complete": True}])]
    await psn.coordinator.async_refresh()
    assert psn.coordinator.last_update_success
    assert method.call_count == 2
    key = (
        "title_trophies" if operation == "trophy_titles_for_title" else "recent_titles"
    )
    expected = {"complete": True} if key == "title_trophies" else [{"complete": True}]
    assert psn.coordinator.data[key] == expected


@pytest.mark.parametrize(
    "failure",
    [
        PSNAWPAuthenticationError("expired npsso"),
        PSNAWPInvalidTokenError("invalid token"),
        PSNAWPUnauthorizedError("unauthorized"),
    ],
)
async def test_authentication_starts_reauth_without_transient_retry(psn, failure):
    entry = Mock()
    psn.coordinator.config_entry = entry
    psn.user.get_presence.side_effect = failure
    await psn.coordinator.async_refresh()
    assert isinstance(psn.coordinator.last_exception, ConfigEntryAuthFailed)
    entry.async_start_reauth_if_available.assert_called_once_with(psn.hass)
    psn.backoff.assert_not_awaited()
    assert psn.user.get_presence.call_count == 1


@pytest.mark.parametrize(
    "failure, diagnostic",
    [
        (PSNAWPForbiddenError("private resource"), "HTTP 403"),
        (PSNAWPBadRequestError("bad request"), "PSNAWPBadRequestError"),
        (PSNAWPNotFoundError("missing"), "PSNAWPNotFoundError"),
        (SSLError("certificate invalid"), "SSLError"),
        (ValueError("malformed response"), "ValueError"),
    ],
)
async def test_permanent_errors_do_not_retry_or_reauth(psn, failure, diagnostic):
    entry = Mock()
    psn.coordinator.config_entry = entry
    psn.user.get_presence.side_effect = failure
    await psn.coordinator.async_refresh()
    assert isinstance(psn.coordinator.last_exception, UpdateFailed)
    assert diagnostic in str(psn.coordinator.last_exception)
    assert psn.user.get_presence.call_count == 1
    entry.async_start_reauth_if_available.assert_not_called()
    psn.backoff.assert_not_awaited()


async def test_rate_limit_defers_normal_polling_without_retry_or_reauth(psn):
    remove_listener = psn.coordinator.async_add_listener(Mock())
    psn.user.get_presence.side_effect = PSNAWPTooManyRequestsError("slow down")
    await psn.coordinator.async_refresh()
    assert isinstance(psn.coordinator.last_exception, UpdateFailed)
    assert psn.coordinator.last_exception.retry_after == 900
    assert psn.coordinator._unsub_refresh is not None
    timer = psn.coordinator._unsub_refresh.__self__
    assert 898 < timer.when() - psn.hass.loop.time() < 901
    assert psn.user.get_presence.call_count == 1
    psn.backoff.assert_not_awaited()
    psn.user.get_presence.side_effect = None
    psn.coordinator._async_unsub_refresh()
    await psn.coordinator._handle_refresh_interval()
    assert psn.coordinator.last_update_success
    assert psn.coordinator._retry_after is None
    remove_listener()


async def test_sensors_and_media_player_follow_snapshot_and_failure_state(psn):
    await psn.coordinator.async_refresh()
    sensor = PsnSensor(psn.coordinator, PSN_SENSOR[1])
    attribute = PsnAttributeSensor(psn.coordinator, PSN_ADDITIONAL_SENSOR[0])
    player = MediaPlayer(psn.coordinator)
    assert sensor.available and attribute.available and player.available
    assert player.media_title == "TEST00001"

    psn.user.get_presence.side_effect = PSNAWPServerError("Internal Server error")
    await psn.coordinator.async_refresh()
    assert not sensor.available and not attribute.available and not player.available
    assert player.media_title == "TEST00001"  # data retained, explicitly unavailable

    psn.user.get_presence.side_effect = None
    psn.user.get_presence.return_value = presence("TEST00002")
    await psn.coordinator.async_refresh()
    assert sensor.available and attribute.available and player.available
    assert player.media_title == "TEST00002"  # no reference to the old dictionary


async def test_recent_titles_replace_previous_snapshot_and_clear_without_game(psn):
    await psn.coordinator.async_refresh()
    await psn.coordinator.async_refresh()
    assert psn.coordinator.data["recent_titles"] == [{"test": "stats"}]
    psn.user.get_presence.return_value = presence(None)
    await psn.coordinator.async_refresh()
    assert psn.coordinator.data["recent_titles"] == []
    assert psn.coordinator.data["title_details"] == {}
    assert psn.coordinator.data["title_trophies"] == {}


async def test_localized_details_fallback_uses_same_retry_budget(psn):
    psn.title.get_details.side_effect = [
        [{"errorCode": "locale missing"}],
        PSNAWPServerError("Internal Server error"),
        [{"name": "Default locale"}],
    ]
    await psn.coordinator.async_refresh()
    assert psn.coordinator.last_update_success
    assert psn.coordinator.data["title_details"] == [{"name": "Default locale"}]
    assert psn.title.get_details.call_count == 3
    psn.backoff.assert_awaited_once_with(2)


async def test_cancellation_does_not_retry_or_publish_partial_data(psn):
    previous = psn.coordinator.data
    psn.user.get_presence.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await psn.coordinator._async_update_data()
    assert psn.coordinator.data is previous
    psn.backoff.assert_not_awaited()


async def test_error_diagnostic_names_operation_without_response_body(psn, caplog):
    psn.user.get_presence.side_effect = PSNAWPServerError("private-response-marker")
    await psn.coordinator.async_refresh()
    assert "user.get_presence" in str(psn.coordinator.last_exception)
    assert "PSNAWPServerError" in str(psn.coordinator.last_exception)
    assert "private-response-marker" not in str(psn.coordinator.last_exception)
    assert "private-response-marker" not in caplog.text


@pytest.mark.parametrize(
    "status, exception",
    [
        (401, PSNAWPUnauthorizedError),
        (403, PSNAWPForbiddenError),
        (429, PSNAWPTooManyRequestsError),
        (500, PSNAWPServerError),
        (502, PSNAWPServerError),
        (503, PSNAWPServerError),
        (504, PSNAWPServerError),
    ],
)
async def test_pinned_psnawp_response_error_mapping(status, exception):
    response = Response()
    response.status_code = status
    response._content = b"Internal Server error"
    with pytest.raises(exception):
        response_checker(response)


async def test_pinned_request_builder_has_one_attempt_and_accounts_for_it():
    # Bypass SQLite initialization: exercise the installed PSNAWP request method.
    builder = object.__new__(RequestBuilder)
    builder.limiter = Mock()
    builder.session = Mock()
    builder.session.request.side_effect = ConnectionResetError(104, "reset")
    with pytest.raises(ConnectionResetError):
        builder.get(url="https://example.invalid/test")
    builder.session.request.assert_called_once()
    builder.limiter.try_acquire.assert_called_once()
    with Session() as session:
        assert session.get_adapter("https://example.invalid").max_retries.total == 0


@pytest.mark.parametrize("status", [None, 500, 502, 503, 504])
async def test_request_builder_to_coordinator_recovery(psn, caplog, status):
    """Run both incident paths through PSNAWP's actual response checker."""
    builder = object.__new__(RequestBuilder)
    builder.limiter = Mock()
    builder.session = Mock()
    success = Response()
    success.status_code = 200
    success._content = json.dumps(presence()).encode()
    if status is None:
        failure = ConnectionResetError(104, "Connection reset by peer")
    else:
        failure = Response()
        failure.status_code = status
        failure._content = b"Internal Server error"
    builder.session.request.side_effect = [failure, success]
    psn.user.get_presence = lambda: builder.get(
        url="https://example.invalid/test"
    ).json()
    await psn.coordinator.async_refresh()
    assert psn.coordinator.last_update_success
    assert builder.session.request.call_count == 2
    assert builder.limiter.try_acquire.call_count == 2
    psn.backoff.assert_awaited_once_with(2)
    assert not errors(caplog)


@pytest.mark.parametrize("failure", [ConnectionResetError, PSNAWPServerError])
async def test_short_outage_keeps_entities_available_during_retry(psn, caplog, failure):
    await psn.coordinator.async_refresh()
    sensor = PsnSensor(psn.coordinator, PSN_SENSOR[1])
    previous = psn.coordinator.data

    async def check_backoff(delay):
        assert delay == 2
        assert sensor.available
        assert psn.coordinator.last_update_success
        assert psn.coordinator.data is previous

    psn.backoff.side_effect = check_backoff
    psn.user.get_presence.side_effect = [failure("temporary failure"), presence()]
    await psn.coordinator.async_refresh()
    assert sensor.available
    assert psn.coordinator.data is not previous
    assert not errors(caplog)


@pytest.mark.parametrize(
    "failure, expected",
    [
        (PSNAWPUnauthorizedError("unauthorized"), ConfigEntryAuthFailed),
        (PSNAWPForbiddenError("forbidden"), ConfigEntryNotReady),
        (PSNAWPServerError("server failure"), ConfigEntryNotReady),
        (ConnectionResetError(104, "reset"), ConfigEntryNotReady),
    ],
)
async def test_setup_keeps_auth_and_temporary_failures_separate(
    psn, monkeypatch, failure, expected
):
    api = Mock()
    api.user.side_effect = failure
    monkeypatch.setattr(integration, "PSNAWP", Mock(return_value=api))
    entry = SimpleNamespace(data={"npsso": "test-only"})
    with pytest.raises(expected):
        await integration.async_setup_entry(psn.hass, entry)
