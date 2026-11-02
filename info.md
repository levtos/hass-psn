HA-PSN exposes PlayStation Network account data and, optionally, a distinct physical PS5 Console Status.

Version 0.10.0 separates the existing PSN-oriented Status sensor from the new Console Status sensor. Configure an optional PS5 host or IP address for local `AWAKE`/`STANDBY` detection. An optional Home Assistant power sensor can provide fallback evidence that an unreachable console is offline.

Version 0.10.1 adds a 45-second runtime transition grace so temporary local discovery gaps during real PS5 power-state changes do not visibly flap through unavailable or Offline. Live verification of the corrected transitions remains open.

Version 0.10.2 adds bounded recovery for temporary PSN network and server errors.
One failed read per poll may be retried after two seconds, without an ERROR log
if it succeeds. Failed refreshes retain the last complete snapshot, mark PSN
entities unavailable, and recover through normal polling. Repeated failures are
deduplicated by Home Assistant. Authentication, permission errors and rate
limits are handled separately; HTTP 429 delays polling for 15 minutes.
