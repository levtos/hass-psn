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


def test_playing_takes_precedence_over_high_power() -> None:
    assert derive_status("online", True, 180, 10.0) == "Playing"


def test_online_takes_precedence_over_high_power() -> None:
    assert derive_status("online", False, 120, 10.0) == "Online"


def test_offline_above_threshold_is_rest_mode() -> None:
    assert derive_status("offline", False, 15, 10.0) == "Rest Mode"


def test_offline_at_threshold_is_offline() -> None:
    assert derive_status("offline", False, 10, 10.0) == "Offline"


def test_offline_below_threshold_is_offline() -> None:
    assert derive_status("offline", False, 2, 10.0) == "Offline"


def test_offline_unknown_power_is_offline() -> None:
    assert derive_status("offline", False, "unknown", 10.0) == "Offline"


def test_offline_unavailable_power_is_offline() -> None:
    assert derive_status("offline", False, "unavailable", 10.0) == "Offline"


def test_missing_power_sensor_preserves_legacy_offline() -> None:
    assert derive_status("offline", False, None, 10.0) == "Offline"


def test_unknown_psn_with_high_power_is_offline() -> None:
    assert derive_status("unknown", False, 15, 10.0) == "Offline"


def test_offline_to_rest_mode_transition() -> None:
    states = [
        derive_status("offline", False, 2, 10.0),
        derive_status("offline", False, 15, 10.0),
    ]
    assert states == ["Offline", "Rest Mode"]


def test_rest_mode_to_offline_transition() -> None:
    states = [
        derive_status("offline", False, 15, 10.0),
        derive_status("offline", False, 2, 10.0),
    ]
    assert states == ["Rest Mode", "Offline"]


def test_malformed_and_non_finite_power_are_offline() -> None:
    for power in ("not-a-number", "nan", "inf", "-inf"):
        assert derive_status("offline", False, power, 10.0) == "Offline"
