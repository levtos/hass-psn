# Home Assistant 2026.11 compatibility (0.10.3)

Scope: [issue #13](https://github.com/Levtos/hass-psn/issues/13), following PR #12.

The deprecated ConfigFlow CONNECTION_CLASS is removed. The manifest already
declares `iot_class: cloud_polling`, HA's integration classification mechanism.
The flow also consumes the coordinator's returned atomic snapshot, preserving
the account name during validation. No live configuration changes are needed.

## Dependency audit

| Component | Before | Selected | Evidence |
| --- | --- | --- | --- |
| PSNAWP | 3.0.3 | 3.1.0 | Inspected installed wheel source and metadata; public method signatures in PSNAWP, User, Client, GameTitle, Authenticator and RequestBuilder unchanged. |
| pyrate-limiter | 4.1.0 | 4.5.1 | Same constructor/Rate/Duration/SQLiteBucket/try_acquire use; real SQLite capacity enforcement tested. |
| Development HA | 2026.6.3 | 2026.11.0 | Real coordinator/config-flow regression suite, Python 3.14. |
| pytest / pytest-asyncio | unpinned | 9.2.0 / 1.4.1.post1 | Current resolved releases, full suite passes. |

PSNAWP raises its Python floor from 3.10 to 3.11; both versions support Python
3.14 at runtime in the tested environment. New dependency bounds are pycountry
>=26.2.16,<27 (previously >=24.6.1,<25), requests >=2.33.1,<3 (previously
>=2.32.5,<3), pyrate-limiter >=4.1,<5 (previously >=4.0.2,<5), and unchanged
typing-extensions >=4.15,<5. Limiter's new optional backend extras are not
installed. Existing PSNAWP exception inheritance/HTTP mapping is preserved;
3.1 adds PSNAWPMediaTypeError, which is not used here. RequestBuilder changes
only its NotRequired import, introduces no retry and still drops Retry-After
from exceptions. The authenticator's token processing is not a retry loop.

The existing 300 requests/15-minute rate policy remains. Limiter.try_acquire
uses blocking acquisition by default, in HA's executor, in both versions.
The upgrade does not impose a new hard HTTP timeout; long hung requests remain
an upstream limitation rather than a claimed fix for these server responses.

requirements.txt now delegates transitive Core pins to HA's package metadata
instead of maintaining a stale second copy. requirements-dev.txt is the pinned
supported integration test environment, also used by the devcontainer and
new GitHub test workflow. requirements_all.txt remains a historical full-Core
integration snapshot (PSNAWP reference updated), not the development install
path; refreshing thousands of unrelated integration dependencies is excluded.

## Server failures and targeted relief

Read-only HA system-log evidence on 2026-11-05 shows count 14, first 01:23:36
and last 02:04:44 CET, naming client.trophy_summary,
client.trophy_titles_for_title and api.game_title with PSNAWPServerError.
This confirms server-error classification at multiple API operations; the
deduplicated record does not preserve each HTTP status or full success/failure
sequence, and does not prove Sony's underlying cause. The user's stated
window ends 02:08; no extra event at that time is established by this record.

After exhausted consecutive server-error refreshes, HA schedules the next poll
after 30, 60, 120, 240 and at most 300 seconds. A complete success immediately
resets the counter and restores the normal 30-second interval; a different
error category breaks the server-failure streak. HTTP 429 retains its separate
900-second cooldown. Network errors keep ordinary polling. The one shared
two-second immediate retry budget, atomic snapshots, explicit unavailable
state after failure, authentication classification and recovery remain intact.
This reduces requests during sustained 5xx outages without hiding new episodes
after genuine successful refreshes. Upgrades are not claimed to cure Sony 5xx.

## Validation and risks

The full 76-test suite passes on HA 2026.11.0/Python 3.14 with both dependency
pairs (3.0.3/4.1.0 and 3.1.0/4.5.1). Tests cover all three incident operations,
bounded backoff/reset, real SQLite limiter enforcement, config-flow import and
snapshot consumption, plus all PR #12 regressions. Dependency resolution and
pip check pass. One upstream HA/aiohttp inheritance deprecation warning remains.
Existing broad exception catches in config_flow's entity cleanup remain
pre-existing Ruff findings. No checks were weakened to hide them.

No productive HA writes, install, reload, restart or PS5 status logic changes.
Live verification remains Benni's gate. Source/API compatibility plus mocked
Sony responses cannot prove successful real Sony authentication or availability.

Reproduce: `python -m pip install -r requirements-dev.txt`, then
`python -m pytest tests -q -o asyncio_default_fixture_loop_scope=function`.
