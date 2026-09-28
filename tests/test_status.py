"""Tests for PlayStation status derivation."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

STATUS_MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "playstation_network"
    / "status.py"
)
SPEC = spec_from_file_location("playstation_network_status", STATUS_MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
STATUS_MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(STATUS_MODULE)

derive_status = STATUS_MODULE.derive_status


def next_status(
    previous_status: str | None,
    online_status: str | None,
    has_active_title: bool,
    power_value,
    threshold: float = 10.0,
) -> str:
    """Derive one transition for concise transition tests."""
    return derive_status(
        online_status,
        has_active_title,
        power_value,
        threshold,
        previous_status,
    )


def test_playing_takes_precedence_over_high_power() -> None:
    assert next_status("Offline", "online", True, 180) == "Playing"


def test_online_takes_precedence_over_high_power() -> None:
    assert next_status("Offline", "online", False, 120) == "Online"


def test_cold_start_power_rise_remains_offline() -> None:
    status = next_status(None, "offline", False, 1)
    assert status == "Offline"
    assert next_status(status, "offline", False, 100) == "Offline"


def test_online_to_offline_with_high_power_is_rest_mode() -> None:
    assert next_status("Online", "offline", False, 15) == "Rest Mode"


def test_playing_to_offline_with_high_power_is_rest_mode() -> None:
    assert next_status("Playing", "offline", False, 15) == "Rest Mode"


def test_active_to_offline_at_or_below_threshold_is_offline() -> None:
    for previous_status in ("Online", "Playing"):
        assert next_status(previous_status, "offline", False, 10) == "Offline"
        assert next_status(previous_status, "offline", False, 2) == "Offline"


def test_rest_mode_continues_while_offline_power_remains_high() -> None:
    assert next_status("Rest Mode", "offline", False, 15) == "Rest Mode"


def test_rest_mode_to_offline_when_power_drops() -> None:
    assert next_status("Rest Mode", "offline", False, 2) == "Offline"


def test_rest_mode_to_online() -> None:
    assert next_status("Rest Mode", "online", False, 15) == "Online"


def test_rest_mode_to_playing() -> None:
    assert next_status("Rest Mode", "online", True, 15) == "Playing"


def test_invalid_power_does_not_open_rest_mode() -> None:
    for power in (
        None,
        "unknown",
        "unavailable",
        "not-a-number",
        "nan",
        "inf",
        "-inf",
    ):
        assert next_status("Online", "offline", False, power) == "Offline"


def test_missing_power_sensor_preserves_legacy_offline() -> None:
    assert next_status("Online", "offline", False, None) == "Offline"


def test_unknown_psn_with_high_power_is_offline() -> None:
    assert next_status("Online", "unknown", False, 15) == "Offline"
