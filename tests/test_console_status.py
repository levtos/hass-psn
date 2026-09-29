"""Tests for physical PS5 console status derivation."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "playstation_network"
    / "console_status.py"
)
SPEC = spec_from_file_location("playstation_console_status", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

derive_console_status = MODULE.derive_console_status
parse_power_value = MODULE.parse_power_value
TRANSITION_GRACE = MODULE.CONSOLE_STATUS_TRANSITION_GRACE_SECONDS


def test_awake_with_psn_offline_and_no_title_is_online() -> None:
    assert derive_console_status("AWAKE", False, None, 10.0) == "Online"


def test_awake_with_psn_online_and_no_title_is_online() -> None:
    assert derive_console_status("AWAKE", False, 100, 10.0) == "Online"


def test_awake_with_active_title_is_playing() -> None:
    assert derive_console_status("AWAKE", True, None, 10.0) == "Playing"


def test_standby_is_rest_mode() -> None:
    assert derive_console_status("STANDBY", False, None, 10.0) == "Rest Mode"


def test_standby_overrides_stale_psn_title() -> None:
    assert derive_console_status("STANDBY", True, 100, 10.0) == "Rest Mode"


def test_failed_local_check_with_low_power_is_offline() -> None:
    assert derive_console_status(None, False, 1, 10.0) == "Offline"
    assert derive_console_status(None, False, 10, 10.0) == "Offline"


def test_failed_local_check_with_high_power_is_unavailable() -> None:
    assert derive_console_status(None, False, 10.1, 10.0) is None


def test_failed_local_check_without_power_is_unavailable() -> None:
    assert derive_console_status(None, False, None, 10.0) is None


def test_psn_account_online_cannot_create_physical_online_state() -> None:
    assert derive_console_status(None, False, None, 10.0) is None
    assert derive_console_status(None, True, 100, 10.0) is None


def test_psn_failure_does_not_hide_local_awake_state() -> None:
    assert derive_console_status("AWAKE", False, None, 10.0) == "Online"


def test_invalid_power_values_are_not_evidence() -> None:
    for power in (
        None,
        True,
        "unknown",
        "unavailable",
        "not-a-number",
        "nan",
        "inf",
        "-inf",
    ):
        assert parse_power_value(power) is None
        assert derive_console_status(None, False, power, 10.0) is None


def test_online_is_held_during_temporary_local_evidence_loss() -> None:
    assert derive_console_status(None, False, 1, 10.0, "Online", 30.0) == "Online"


def test_playing_is_held_during_temporary_local_evidence_loss() -> None:
    assert derive_console_status(None, False, 1, 10.0, "Playing", 30.0) == "Playing"


def test_rest_mode_is_held_during_temporary_local_evidence_loss() -> None:
    assert derive_console_status(None, False, 1, 10.0, "Rest Mode", 30.0) == "Rest Mode"


def test_standby_ends_online_grace_immediately() -> None:
    assert (
        derive_console_status("STANDBY", False, 1, 10.0, "Online", 5.0) == "Rest Mode"
    )


def test_awake_ends_rest_mode_grace_immediately() -> None:
    assert derive_console_status("AWAKE", False, 1, 10.0, "Rest Mode", 5.0) == "Online"
    assert derive_console_status("AWAKE", True, 1, 10.0, "Rest Mode", 5.0) == "Playing"


def test_expired_grace_with_low_power_is_offline() -> None:
    assert (
        derive_console_status(None, False, 1, 10.0, "Online", TRANSITION_GRACE)
        == "Offline"
    )


def test_expired_grace_with_high_power_is_unavailable() -> None:
    assert (
        derive_console_status(None, False, 100, 10.0, "Online", TRANSITION_GRACE)
        is None
    )


def test_expired_grace_without_power_is_unavailable() -> None:
    assert (
        derive_console_status(None, False, None, 10.0, "Rest Mode", TRANSITION_GRACE)
        is None
    )


def test_initial_missing_local_evidence_does_not_start_grace() -> None:
    assert derive_console_status(None, False, 1, 10.0) == "Offline"
    assert derive_console_status(None, False, None, 10.0) is None


def test_non_local_fallback_status_does_not_start_grace() -> None:
    assert derive_console_status(None, False, 1, 10.0, "Offline", 1.0) == "Offline"
