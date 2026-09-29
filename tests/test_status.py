"""Tests for PlayStation Network status derivation."""

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


def test_playing_takes_precedence() -> None:
    assert derive_status("online", True) == "Playing"


def test_online_without_active_title() -> None:
    assert derive_status("online", False) == "Online"


def test_offline() -> None:
    assert derive_status("offline", False) == "Offline"


def test_direct_offline_to_playing_transition_remains_valid() -> None:
    assert derive_status("offline", False) == "Offline"
    assert derive_status("online", True) == "Playing"


def test_psn_status_never_reports_rest_mode() -> None:
    for online_status in ("online", "offline", "unknown", None):
        for has_active_title in (True, False):
            assert derive_status(online_status, has_active_title) != "Rest Mode"


def test_psn_only_behavior_needs_no_local_console_configuration() -> None:
    assert derive_status("online", False) == "Online"
    assert derive_status("offline", False) == "Offline"
