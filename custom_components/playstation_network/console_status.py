"""Physical PS5 console status derivation."""

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


def derive_console_status(
    local_status: str | None,
    has_active_title: bool,
    power_value: Any,
    threshold: float,
) -> str | None:
    """Derive physical console status from local and fallback power evidence."""
    if local_status == "STANDBY":
        return "Rest Mode"
    if local_status == "AWAKE":
        return "Playing" if has_active_title else "Online"

    numeric_power = parse_power_value(power_value)
    if numeric_power is not None and numeric_power <= threshold:
        return "Offline"
    return None
