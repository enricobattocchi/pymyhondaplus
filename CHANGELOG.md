# Changelog

All notable changes to this project will be documented in this file.

## 5.8.2 — 2026-04-25

- `wait_for_geofence` now polls on `isWaitingForActivate` / `isWaitingForDeactivate` (matching Honda's own app) instead of `isCommandProcessing`. The previous logic exited as soon as the server's state machine went idle, which is well before the async command to the car has actually completed — when the TCU was unreachable (energy-saving mode), the wait reported a result based on stale `activateAsyncCommandStatus` from the *previous* command, often as immediate "failure" or "timeout". The fix tracks the actual in-flight flag, ignoring stale status until the new command resolves.
- CLI `geofence-set` / `geofence-clear` default `--timeout` raised from 90s to 420s (matches Honda's own server-side wait policy of "up to 7 minutes"). Explicit `--timeout N` still wins. Other remote commands keep their 90s default.
- CLI `geofence` query now distinguishes four states (Active / Not Active / Activating / De-Activating) using Honda's own status labels, and surfaces a separate error line for the most recent terminal failure (timeout / activate / deactivate). The error line is suppressed while a new command is in flight so it doesn't leak the previous attempt's outcome onto the live status.
- Add 7 new translation keys (`geofence_state_active`, `geofence_state_inactive`, `geofence_state_activating`, `geofence_state_deactivating`, `geofence_activate_error`, `geofence_deactivate_error`, `geofence_timeout_error`) sourced verbatim from the Honda app, across all 13 locales. Honda's app ships sk/sv error strings swapped — fixed here so each locale gets its own language. Italian active/inactive labels capitalized for consistency with the other 12 locales.

## 5.8.1 — 2026-04-24

- CLI `capabilities` command now lists every active capability the API reports, rendered by their raw Honda API key (e.g. `telematicsRemoteLockUnlock`, `useSpecificTemperatureControl`, `smartCharge`). Previously only 12 hardcoded capabilities were shown with translated labels; that list silently omitted the 17 fields added in 5.8.0 and the translations themselves were partly invented rather than sourced from Honda. Raw API keys are honest, identical in every locale, and forward-compatible with flags Honda adds that this library version doesn't yet know about.
- CLI `capabilities` no longer prints inactive capabilities. Use `vehicle.capabilities.<field>` programmatically to check whether a specific flag is supported.
- Remove the 12 `cap_*` translation keys (`cap_lock_unlock`, `cap_climate`, `cap_charging`, `cap_horn`, `cap_digital_key`, `cap_charge_schedule`, `cap_climate_schedule`, `cap_max_charge`, `cap_car_finder`, `cap_journeys`, `cap_send_nav`, `cap_geo_fence`) across all 13 locales. Downstream consumers (e.g. `myhondaplus-desktop`) that referenced these keys must render capabilities as raw API keys too.
- Public API: expose `get_translator` and `TRANSLATIONS` at the top level so consumers can share the library's non-capability translations.
- Add `no_active_capabilities` translation key in all 13 locales (header fallback message when a vehicle reports no actives).

## 5.8.0 — 2026-04-24

- Convert DMS-with-commas GPS coordinates to decimal degrees in `parse_ev_status` (`EVStatus.latitude` and `EVStatus.longitude` changed from `str` to `float`).
- Refactor the CLI `location` command to use `EVStatus` instead of raw API data.
- Normalize `EVStatus.home_away` to `home` / `away` / `unknown` (fixes "home is unregistered").
- Normalize `EVStatus.climate_temp`: map known labels, pass through numeric values from specific-temperature vehicles, fall back to `"unknown"`.
- Add 17 newly discovered vehicle capabilities to `VehicleCapabilities`.
- Normalize `EVStatus.charge_status` to a canonical enum (`charging`, `stopped`, `unknown`). The raw API returns values like `running` / `unavailable` which previously leaked through and broke downstream consumers declaring strict enum sensors (e.g. the Home Assistant integration).
- Mapping: `running` → `charging`, `stopped` → `stopped`, `unavailable` / missing / unexpected values → `unknown` (with a DEBUG log for unexpected values).
- CLI `CHARGE_STATUS_MAP` (in `translations.py`) is now keyed by the normalized values rather than raw API values.

### Migration notes for library consumers

- `EVStatus.latitude` / `EVStatus.longitude` are now `float`. Consumers doing string comparisons or concatenation must update.
- `EVStatus.charge_status` will no longer emit `"running"` or `"unavailable"`. Consumers that branched on these raw values should switch to `"charging"` / `"unknown"`.

## 5.7.1b1 — 2026-04-14

- Normalize EVStatus fields and add missing vehicle capabilities

## 5.7.0 — 2026-04-13

- Add `activate_status` and `deactivate_status` fields to `Geofence` dataclass (maps `activateAsyncCommandStatus` / `deactivateAsyncCommandStatus` from the API)
- `wait_for_geofence()` exits early when the server reports the vehicle is unreachable (`"failure"` or `"timeout"` status) instead of polling until deadline
- Increase default polling timeouts: `wait_for_command` 60→90s, `get_dashboard` 90→120s, `wait_for_geofence` 120→420s (based on observed server-side timeouts)
- CLI geofence set/clear now show a spinner during polling
- Translate all CLI command labels and result messages (done/failed/timed out) across 13 languages
- Downgrade token refresh log messages from INFO to DEBUG

### Migration notes for library consumers

- `wait_for_geofence()` can now return a `Geofence` with `processing=True` when the server reports failure. Check `gf.activate_status` or `gf.deactivate_status` for `"failure"` / `"timeout"` to detect vehicle-unreachable conditions.
- Default timeouts are longer; pass explicit `timeout=` if you need the old behavior.

## 5.6.3 — 2026-04-12

- Increase default HTTP timeout for auth endpoints from 10s to 30s (`DEFAULT_AUTH_TIMEOUT`); configurable via `HONDA_AUTH_TIMEOUT` env var
- `--http-timeout` CLI flag now only applies to API calls, not auth operations

## 5.6.2 — 2026-04-12

- Fix crash when running CLI with no subcommand (`'Namespace' object has no attribute 'http_timeout'`)

## 5.6.1 — 2026-04-12

- Fix token refresh raising `HondaAuthError` on 5xx server errors (502/503); now correctly raises `HondaAPIError` so callers treat it as a transient failure instead of triggering re-authentication

## 5.6.0 — 2026-04-12

- Add geofence management: `get_geofence`, `set_geofence` (with polling), `clear_geofence` API methods with `Geofence` dataclass
- New CLI commands: `geofence`, `geofence-set`, `geofence-clear`
- Coordinates are accepted/returned in degrees; MAS conversion handled internally
- Add `Vehicle` fields: registration/production dates, doors, transmission, weight, country
- Add `UIConfiguration` with Honda's UI display hints (hide window/door/temperature status)
- Add `Subscription` fields: `package_type`, `term`, `trial_term`, `services` list
- Add `UserProfile` dataclass and `get_user_profile()` API method
- New CLI commands: `profile`, `subscription` now shows services list
- Translated fuel types (EV/PHEV/Petrol) and transmission (Automatic/Manual) in CLI output
- Capability checks at library level: all command methods raise `ValueError` if the feature is not supported
- Translated confirmation prompt, abort message, and capability error across 13 languages
- Add configurable HTTP request timeout (`--http-timeout`, `HONDA_REQUEST_TIMEOUT` env var, `request_timeout` constructor parameter)
- Default 10-second timeout on all HTTP requests to prevent indefinite hangs
- Retry only on 5xx status responses; transport errors (timeouts, connection failures) fail fast
- Fix Polish `charge_speed_normal` translation

## 5.5.0 — 2026-04-11

- Add typed dataclasses: `Vehicle`, `VehicleCapabilities`, `Subscription`, `EVStatus`
- `get_vehicles()` now returns `list[Vehicle]` with model name, grade, year, images, capabilities, and subscription info
- `parse_ev_status()` now returns an `EVStatus` dataclass instead of a plain dict
- All new types support dict-style access (`v["vin"]`, `v.get("fuel_type")`) for backward compatibility
- New CLI commands: `capabilities`, `subscription`, `list --verbose`
- Add translations for all new CLI strings across 13 languages
- `AuthTokens` serialization handles both old 5-field and new Vehicle format

## 5.4.0 — 2026-04-11

- Add thread-safety to `HondaAPI` so a single instance can be shared across threads without external locking
- All `session.request()` calls and token refresh are serialized via an internal lock
- Concurrent `refresh_auth()` calls are deduplicated (only one thread refreshes, others reuse the result)
- Remove redundant `range` field, use `range_climate_on`/`range_climate_off`
- Add GitHub issue and PR templates
- Bump development status from Alpha to Beta
- Add CHANGELOG.md and CONTRIBUTING.md

## 5.3.1 — 2026-04-11

- Fix lint errors

## 5.3.0 — 2026-04-11

- Add i18n support for CLI status output (13 languages)
- Add climate range fields (`range_climate_on`, `range_climate_off`)
- Fix Italian and Norwegian translation issues

## 5.2.2 — 2026-04-09

- Improve handling when car does not respond to refresh

## 5.2.1 — 2026-04-08

- Refactor CLI command handling to consistently use return codes

## 5.2.0 — 2026-04-06

- Add confirmation prompts, spinner, exit codes, CSV output, and shell completion
- Add CLI behavioral tests

## 5.1.0 — 2026-04-04

- Handle malformed numeric fields gracefully
- Add multi-month trip aggregation in `trip-stats`

## 5.0.0 — 2026-04-04

**Breaking:** `poll_command()` now returns a `CommandResult` object instead of a raw dict. Update code that used `{"status_code": ..., "data": ...}` to use `CommandResult` fields instead.

- Add structured `CommandResult` for async command polling
- Add `HondaAuthError` for auth-specific failures
- Raise `HondaAuthError` for all authentication failures

## 4.2.0 — 2026-03-29

- Add tests for DeviceKey, storage backends, and auth flow
- Add ruff and mypy to CI

## 4.1.0 — 2026-03-29

- Route PUT methods through `_request` for automatic token refresh
- Standardize error handling

## 4.0.0 — 2026-03-28

**Breaking:** `remote_climate_on` renamed to `set_climate_settings`.

- Remove unused token import feature

## 3.0.0 — 2026-03-25

**Breaking:** Status output now uses dynamic units from the API instead of hardcoded km/°C.

- Validate charge limit values (80, 85, 90, 95, 100)
- Add CI workflow to run tests on push and PR
- Add test suite for parsing and computation helpers

## 2.0.0 — 2026-03-25

- Add charge prohibition and climate schedule commands
- Add climate-settings read and defrost toggle
- Add `--version` flag to CLI
- Handle schedule and climate errors for secondary users

## 1.3.0 — 2026-03-23

- Improve library API for Home Assistant integration
- Extract trip helpers into API layer for library reuse
- Show kWh/100km for electric vehicles instead of L/100km

## 1.2.0 — 2026-03-21

- Add trip-stats, trip-detail commands and trip locations
- Add `--watch` mode to status command
- Encrypt tokens and device key at rest
- Add PyPI badges to README

## 1.1.0 — 2026-03-21

- Add vehicle list, auto-selection, and identification by name or plate

## 1.0.1 — 2026-03-18

- Fix remote horn & lights endpoint
- Fix lock/unlock command body

## 1.0.0 — 2026-03-16

Initial release.

- Login with email verification
- Vehicle status (battery, range, charge, location, doors, lights)
- Remote commands (lock, unlock, horn, climate, charge)
- Trip history
- Encrypted token storage
