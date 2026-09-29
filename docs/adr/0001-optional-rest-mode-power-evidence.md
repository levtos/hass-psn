# ADR 0001: Optional power evidence for PS5 Rest Mode

- Status: superseded by ADR 0002
- Date: 2026-09-28
- Corrected: 2026-09-28 for v0.9.1 cold-start handling
- Scope: [Issue #4](https://github.com/Levtos/hass-psn/issues/4)

## Decision

The existing PSN Status sensor remains the canonical activity state. PSN data
has precedence: an active title is `Playing`, an online console is `Online`, and
only a runtime transition from `Online` or `Playing` to an explicitly offline
console with valid power above the configured threshold opens `Rest Mode`. An
already derived `Rest Mode` continues only while that evidence remains valid.
Every other case is `Offline`.

The power entity is an optional Home Assistant config-entry option. Its state is
read directly by the dedicated Status sensor, stabilized with a five-second
cancel-and-reschedule debounce, and never added to the PSN coordinator payload.
The default threshold is 10.0 W and the comparison is strictly greater-than.
An `Offline` console remains `Offline` when power rises, which prevents a cold
start from being misclassified while PSN has not yet reported `online`.

## Consequences

Installations without a configured power entity keep their PSN-only behavior,
including existing entities and unique IDs. Invalid, missing, unknown, or
unavailable power is not evidence. Core Contracts, SourceBindings, MQTT, and
synthetic media-player states remain outside this change.

Runtime transition evidence is not persisted. Restoring or holding `Rest Mode`
across integration reloads, Home Assistant restarts, or temporary evidence loss
is explicitly outside this decision.
