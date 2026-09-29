"""PSN status derivation for the PlayStation Network integration."""

from __future__ import annotations


def derive_status(
    online_status: str | None,
    has_active_title: bool,
) -> str:
    """Derive the PSN-facing status without local console evidence."""
    if has_active_title:
        return "Playing"
    if online_status == "online":
        return "Online"
    return "Offline"
