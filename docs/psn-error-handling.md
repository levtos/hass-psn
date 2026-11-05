# PSN fetch failure handling

This hotfix implements [hass-psn#11](https://github.com/Levtos/hass-psn/issues/11).
The reported connection reset and server error are reproduced with synthetic
responses in `tests/test_coordinator.py`; the historical reset's exact API
operation is still unknown. The reported PSN outage is incident context, not a
proven cause extracted from those historical logs.

## Dependency inspection

Pinned PSNAWP 3.0.3 `RequestBuilder.request` calls its existing rate limiter,
then a default Requests `Session`, then `response_checker`. Neither it nor the
default Requests adapters retries transport or server failures. The
`pre_request_processing` authenticator decorator checks token expiration and
obtains/refreshes credentials; it is not a transient-error retry mechanism.
`response_checker` maps 5xx to `PSNAWPServerError`, and 401, 403 and 429 to
distinct client exceptions. These exceptions are siblings of
`PSNAWPAuthenticationError`, not subclasses of it. HTTP response status and
`Retry-After` headers are not retained in the PSNAWP exceptions.

## Hotfix policy

- The coordinator owns a single retry budget per refresh: at most one failed
  read operation is repeated after an asynchronous two-second delay. Only
  connection failures (including bare/wrapped resets), timeouts, interrupted
  bodies and PSNAWP server errors qualify. TLS/certificate errors do not.
- Already successful operations are not repeated. Lazy iterators are recreated
  and fully consumed inside the executor on each attempt. No adapter retry or
  second refresh retry loop is installed. All HTTP attempts remain subject to
  the existing PSNAWP limiter (300 requests per 15 minutes).
- A new dictionary is assembled without mutating published containers. Recent
  titles replace the previous list; game-specific data is cleared when there
  is no active game. DataUpdateCoordinator publishes the snapshot only when
  every required operation succeeds. The media player reads the current
  dictionary rather than keeping the original reference.
- During the short retry, the previously successful entities remain available.
  After exhaustion, `UpdateFailed` retains the last snapshot, sets
  `last_update_success=False`, and makes PSN entities unavailable. Returning
  cached data as a successful update would falsely advertise freshness.
- HA's existing coordinator suppresses consecutive fetch errors, emits one
   INFO recovery message, and keeps automatic polling armed. No custom
  logging filter, availability grace period or freshness state machine is
  needed. A new outage after a genuine successful refresh can log again.
- HTTP 401, explicit authentication failure and invalid-token errors trigger
  HA reauthentication. HTTP 403 is a resource/permission denial, without
  automatic reauthentication. HTTP 429 bypasses the short retry and uses HA's
  `UpdateFailed(retry_after=900)` scheduling, a conservative fallback matching
  the configured rate window. Other client, certificate and data errors fail
  the refresh without immediate retry. Cancellation propagates.
- Error messages and retry DEBUG lines name the operation and exception
  class, without interpolating response bodies, URLs, account IDs or tokens.
  HA may include the chained exception traceback at DEBUG level; do not enable
  broad PSNAWP HTTP DEBUG logging to diagnose these failures because upstream
  logs request/response details.
- Setup preserves HA's normal `ConfigEntryNotReady` retry for temporary
  initialization failures; actual authentication/401 errors are separate.
  The coordinator receives its config entry explicitly for HA lifecycle and
  reauthentication handling.

Local PS5 discovery and Console Status rules are unchanged. Tests run against
the real Home Assistant 2026.10.4 coordinator and PSNAWP 3.0.3, without live
Sony requests or credentials. Historical incident reproduction and automated
recovery tests do not replace Benni's Live verification.

## Test command

```powershell
uv run --no-project --python 3.14 --with homeassistant==2026.10.4 --with pytest --with pytest-asyncio --with PSNAWP==3.0.3 --with pyrate-limiter==4.1.0 --with ps5-remoteplay==0.1.8 python -m pytest tests -q -o asyncio_default_fixture_loop_scope=function
```
