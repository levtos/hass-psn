# ADR 0002: Separate PSN status from physical PS5 console status

- Status: accepted
- Date: 2026-09-29
- Scope: [Issue #7](https://github.com/Levtos/hass-psn/issues/7)
- Supersedes: ADR 0001

## Context

The existing Status sensor represents PlayStation Network presence. Using power consumption to add `Rest Mode` to that sensor mixed an account-level cloud view with the physical state of one console. It also could not distinguish a console from other account activity such as the PlayStation mobile app.

The `ps5-remoteplay` library can query a PS5 directly on the local network with `get_device(host)` and report `AWAKE` or `STANDBY`. This status query is asynchronous and does not require pairing credentials.

## Decision

The existing Status sensor remains PSN-only:

1. Active title -> `Playing`.
2. PSN online -> `Online`.
3. Otherwise -> `Offline`.

A separate Console Status sensor represents physical console evidence:

1. Local `STANDBY` -> `Rest Mode`.
2. Local `AWAKE` plus an active PSN title -> `Playing`.
3. Local `AWAKE` without an active title -> `Online`.
4. No local response plus finite numeric power less than or equal to the configured threshold -> `Offline`.
5. Otherwise the entity is unavailable.

The PS5 host is optional per config entry. Local polling uses its own coordinator and does not write data into the PSN coordinator. Local failures return no local evidence and cannot make PSN entities unavailable. Runtime PSN failures do not hide a local `AWAKE` or `STANDBY` result; PSN is used only to refine local `AWAKE` into `Playing`.

The existing optional power sensor and threshold remain configuration options, but power is only fallback evidence for `Offline`. It cannot prove `Rest Mode` or a positive console state.

## Consequences

- Existing Status unique IDs and PSN-only installations remain compatible.
- Console Status has a new unique ID and may be unavailable when physical evidence is inconclusive.
- A local host or IP must be configured for primary physical detection; automatic discovery and multi-console selection are intentionally deferred.
- MQTT, Core Contracts `held`/restore semantics, persistence, and media-player changes remain out of scope.
