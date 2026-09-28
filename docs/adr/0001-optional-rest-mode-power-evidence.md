# ADR 0001: Optional power evidence for PS5 Rest Mode

- Status: accepted
- Date: 2026-09-28
- Scope: [Issue #4](https://github.com/Levtos/hass-psn/issues/4)

## Decision

The existing PSN Status sensor remains the canonical activity state. PSN data
has precedence: an active title is `Playing`, an online console is `Online`, and
only an explicitly offline console with valid power above the configured
threshold is `Rest Mode`. Every other case is `Offline`.

The power entity is an optional Home Assistant config-entry option. Its state is
read directly by the dedicated Status sensor, stabilized with a five-second
cancel-and-reschedule debounce, and never added to the PSN coordinator payload.
The default threshold is 10.0 W and the comparison is strictly greater-than.

## Consequences

Installations without a configured power entity keep their PSN-only behavior,
including existing entities and unique IDs. Invalid, missing, unknown, or
unavailable power is not evidence. Core Contracts, SourceBindings, MQTT, and
synthetic media-player states remain outside this change.
