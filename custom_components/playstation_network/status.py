"""Status derivation for the PlayStation Network integration."""

from __future__ import annotations

import math
from typing import Any


def parse_power_value(power_value: Any) -> float | None:
    """Return a finite numeric power value, or None when it is invalid."""
    if power_value is None or isinstance(power_value, bool):
        return None

    try:
        value = float(power_value)
    except (TypeError, ValueError):
        return None

    return value if math.isfinite(value) else None


def derive_status(
    online_status: str | None,
    has_active_title: bool,
    power_value: Any,
    threshold: float,
) -> str:
    """Derive the canonical PSN status using PSN-first precedence."""
    if has_active_title:
        return "Playing"
    if online_status == "online":
        return "Online"
    if (
        online_status == "offline"
        and (numeric_power := parse_power_value(power_value)) is not None
        and numeric_power > threshold
    ):
        return "Rest Mode"
    return "Offline"
