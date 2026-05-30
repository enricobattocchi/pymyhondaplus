# Changelog

All notable changes to this project will be documented in this file.

## 5.10.1 (2026-05-30)

### Fixed

- `CarLocation.from_command_result` canonicalizes `velocity.unit` through `_normalize_speed_unit`. Previously only `"kph"` was rewritten to `"km/h"`, so UK accounts (Honda returns `"mile/h"`) surfaced the raw alias through `pymyhondaplus find-car` and the Home Assistant `car_finder_location` service, while the rest of the stack had already settled on `"miles/h"`.
- `_normalize_speed_unit` learns the slash-less aliases `kph` / `kmh` / `kmph` / `mph` that the car-location endpoint can return.

## 5.10.0 (2026-05-30)

### Added

- `consumption_unit_for(fuel_type, distance_unit)`: canonical mapping shared by the library and the CLI.

### Fixed

- `parse_ev_status` canonicalizes the distance and speed unit strings Honda returns for non-metric accounts. UK accounts come back with `rangeUnit="mile"` (singular) and `velocity.unit="mile/h"`; the library was passing those through unchanged, breaking consumers that expect `"miles"` / `"miles/h"` (most visibly: the Home Assistant integration mislabelled odometer, range, and speed as km).
- `compute_trip_stats` derives `consumption_unit` from `(fuel_type, distance_unit)` instead of `fuel_type` alone. UK ICE accounts now get `mpg`, UK EV accounts get `mi/kWh`. Metric accounts are unchanged.
- `compute_trip_stats` aggregates `AveFuelEconomy` correctly for imperial units. `mpg` and `mi/kWh` are distance-per-fuel: the right rollup is `total_distance / sum(distance / efficiency)`, not the distance-weighted average used for `L/100km` / `kWh/100km`. Two trips of 10mi at 10mpg and 20mi at 20mpg now report 15.0 mpg instead of 16.7.
- `pymyhondaplus trips` and `pymyhondaplus trip-stats` label output by the vehicle's locale: distance unit is read from the cached dashboard and the consumption label follows.

## 5.9.1 (2026-05-24)

### Fixed

- Encrypted storage no longer deletes token / device-key files it cannot decrypt (for example after the encryption key changes). The file is renamed aside as `<name>.broken-<timestamp>`, so the ciphertext is preserved and the next login can recover instead of starting from a silent data loss.
- Authentication no longer logs the account email or Honda response payloads at INFO level, so credentials and personal data no longer leak into logs.

### Changed

- Log levels tidied up: anomalies are raised from DEBUG to WARNING, and storage backend selection plus the plaintext-to-encrypted migration are surfaced at INFO.

## 5.9.0 (2026-05-22)

### Breaking

- `request_dashboard_refresh(vin)` is renamed to `refresh_dashboard(vin)`. Same return type (`command_id: str`) and semantics; only the name changed.
- `refresh_dashboard(vin, timeout, poll_interval) -> CommandResult` (the high-level convenience that fired the command and waited) is **removed**. Callers should pair the new low-level `refresh_dashboard(vin)` with `wait_for_command(command_id, ...)` to get the previous behavior.
- `request_car_location(vin)` is renamed to `refresh_location(vin)`.

### Added

- `CarLocation` dataclass plus `CarLocation.from_command_result(result)` for extracting GPS data from a `refresh_location` command result. Honda's `/tsp/car-location` endpoint returns the location inside the async-command-status response (in `output.Content` as a JSON-encoded payload with coordinates in milliarcseconds and the *actual* GPS fix time), not by updating `/tsp/dashboard-latest`. This parser handles the unwrapping, MAS to decimal conversion, and the `kph` to `km/h` unit normalization. The fix time it reports is truthful (when the TCU actually acquired the GPS), whereas the dashboard's `gpsData.dtTime` is stamped with the server's response time on every refresh and doesn't represent when the car was actually located.
- New CLI command `find-car`: the dedicated Car Finder query. Calls `/tsp/car-location` and prints the TCU's last GPS fix with its truthful fix-time, course heading, and ignition state. The reported coordinates may differ from `location` (which is dashboard-derived): TCU-side GPS may be drifted at parking, while dashboard refresh tends to surface a more spatially accurate position. The two are different concepts and we expose them as different commands.
- `location --fresh` now refreshes the dashboard (consistent with `status --fresh`); previously it routed to `/tsp/car-location`. For Car Finder behaviour, use `find-car`.
- Global flag `--local-tz` renders timestamps in human-readable CLI output (`status`, `location`, `trips`, `trip-detail`, `find-car`) in the system's local timezone instead of UTC. Default behavior is unchanged (UTC with `+00:00` suffix), so existing scripts and consumers are not affected. JSON and CSV output are also unchanged (raw API passthrough).
- `trip-detail` now accepts either UTC or local-tz ISO 8601 strings for its `start_time` / `end_time` arguments and normalizes them to UTC before calling Honda's endpoint, so timestamps copied from `trips --local-tz` round-trip cleanly.

Migration:

```python
# Before
result = api.refresh_dashboard(vin, timeout=90)
# After
command_id = api.refresh_dashboard(vin)
result = api.wait_for_command(command_id, timeout=90)

# Before
command_id = api.request_car_location(vin)
# After
command_id = api.refresh_location(vin)
```

The single-tier API matches how every other action method (`remote_lock`, `set_climate_settings`, etc.) already behaves: send the command, get a `command_id`, optionally wait via `wait_for_command`.

## 5.8.2 (2026-04-25)

### Added

- Add 7 new translation keys (`geofence_state_active`, `geofence_state_inactive`, `geofence_state_activating`, `geofence_state_deactivating`, `geofence_activate_error`, `geofence_deactivate_error`, `geofence_timeout_error`) sourced verbatim from the Honda app, across all 13 locales. Honda's app ships sk/sv error strings swapped; fixed here so each locale gets its own language. Italian active/inactive labels capitalized for consistency with the other 12 locales.

### Fixed

- `wait_for_geofence` now polls on `isWaitingForActivate` / `isWaitingForDeactivate` (matching Honda's own app) instead of `isCommandProcessing`. The previous logic exited as soon as the server's state machine went idle, which is well before the async command to the car has actually completed. When the TCU was unreachable (energy-saving mode), the wait reported a result based on stale `activateAsyncCommandStatus` from the *previous* command, often as immediate failure or timeout. The fix tracks the actual in-flight flag, ignoring stale status until the new command resolves.

### Changed

- CLI `geofence-set` / `geofence-clear` default `--timeout` raised from 90s to 420s (matches Honda's own server-side wait policy of "up to 7 minutes"). Explicit `--timeout N` still wins. Other remote commands keep their 90s default.
- CLI `geofence` query now distinguishes four states (Active / Not Active / Activating / De-Activating) using Honda's own status labels, and surfaces a separate error line for the most recent terminal failure (timeout / activate / deactivate). The error line is suppressed while a new command is in flight so it doesn't leak the previous attempt's outcome onto the live status.

## 5.8.1 (2026-04-24)

### Added

- Public API: expose `get_translator` and `TRANSLATIONS` at the top level so consumers can share the library's non-capability translations.
- Add `no_active_capabilities` translation key in all 13 locales (header fallback message when a vehicle reports no actives).

### Changed

- CLI `capabilities` command now lists every active capability the API reports, rendered by their raw Honda API key (e.g. `telematicsRemoteLockUnlock`, `useSpecificTemperatureControl`, `smartCharge`). Previously only 12 hardcoded capabilities were shown with translated labels; that list silently omitted the 17 fields added in 5.8.0 and the translations themselves were partly invented rather than sourced from Honda. Raw API keys are honest, identical in every locale, and forward-compatible with flags Honda adds that this library version doesn't yet know about.
- CLI `capabilities` no longer prints inactive capabilities. Use `vehicle.capabilities.<field>` programmatically to check whether a specific flag is supported.
- Remove the 12 `cap_*` translation keys (`cap_lock_unlock`, `cap_climate`, `cap_charging`, `cap_horn`, `cap_digital_key`, `cap_charge_schedule`, `cap_climate_schedule`, `cap_max_charge`, `cap_car_finder`, `cap_journeys`, `cap_send_nav`, `cap_geo_fence`) across all 13 locales. Downstream consumers (e.g. `myhondaplus-desktop`) that referenced these keys must render capabilities as raw API keys too.

## 5.8.0 (2026-04-24)

### Added

- Add 17 newly discovered vehicle capabilities to `VehicleCapabilities`.

### Changed

- Convert DMS-with-commas GPS coordinates to decimal degrees in `parse_ev_status` (`EVStatus.latitude` and `EVStatus.longitude` changed from `str` to `float`).
- Refactor the CLI `location` command to use `EVStatus` instead of raw API data.
- Normalize `EVStatus.home_away` to `home` / `away` / `unknown` (fixes "home is unregistered").
- Normalize `EVStatus.climate_temp`: map known labels, pass through numeric values from specific-temperature vehicles, fall back to `"unknown"`.
- Normalize `EVStatus.charge_status` to a canonical enum (`charging`, `stopped`, `unknown`). The raw API returns values like `running` / `unavailable` which previously leaked through and broke downstream consumers declaring strict enum sensors (e.g. the Home Assistant integration). Mapping: `running` to `charging`, `stopped` to `stopped`, `unavailable` / missing / unexpected values to `unknown` (with a DEBUG log for unexpected values).
- CLI `CHARGE_STATUS_MAP` (in `translations.py`) is now keyed by the normalized values rather than raw API values.

Migration notes for library consumers:

- `EVStatus.latitude` / `EVStatus.longitude` are now `float`. Consumers doing string comparisons or concatenation must update.
- `EVStatus.charge_status` will no longer emit `"running"` or `"unavailable"`. Consumers that branched on these raw values should switch to `"charging"` / `"unknown"`.

## 5.7.1b1 (2026-04-14)

### Added

- Missing vehicle capabilities.

### Changed

- Normalize EVStatus fields.

## 5.7.0 (2026-04-13)

### Added

- Add `activate_status` and `deactivate_status` fields to `Geofence` dataclass (maps `activateAsyncCommandStatus` / `deactivateAsyncCommandStatus` from the API).
- Translate all CLI command labels and result messages (done / failed / timed out) across 13 languages.

### Changed

- `wait_for_geofence()` exits early when the server reports the vehicle is unreachable (`"failure"` or `"timeout"` status) instead of polling until deadline.
- Increase default polling timeouts: `wait_for_command` 60 to 90s, `get_dashboard` 90 to 120s, `wait_for_geofence` 120 to 420s (based on observed server-side timeouts).
- CLI geofence set/clear now show a spinner during polling.
- Downgrade token refresh log messages from INFO to DEBUG.

Migration notes for library consumers:

- `wait_for_geofence()` can now return a `Geofence` with `processing=True` when the server reports failure. Check `gf.activate_status` or `gf.deactivate_status` for `"failure"` / `"timeout"` to detect vehicle-unreachable conditions.
- Default timeouts are longer; pass explicit `timeout=` if you need the old behavior.

## 5.6.3 (2026-04-12)

### Changed

- Increase default HTTP timeout for auth endpoints from 10s to 30s (`DEFAULT_AUTH_TIMEOUT`); configurable via `HONDA_AUTH_TIMEOUT` env var.
- `--http-timeout` CLI flag now only applies to API calls, not auth operations.

## 5.6.2 (2026-04-12)

### Fixed

- Fix crash when running CLI with no subcommand (`'Namespace' object has no attribute 'http_timeout'`).

## 5.6.1 (2026-04-12)

### Fixed

- Fix token refresh raising `HondaAuthError` on 5xx server errors (502/503); now correctly raises `HondaAPIError` so callers treat it as a transient failure instead of triggering re-authentication.

## 5.6.0 (2026-04-12)

### Added

- Add geofence management: `get_geofence`, `set_geofence` (with polling), `clear_geofence` API methods with `Geofence` dataclass.
- New CLI commands: `geofence`, `geofence-set`, `geofence-clear`.
- Add `Vehicle` fields: registration/production dates, doors, transmission, weight, country.
- Add `UIConfiguration` with Honda's UI display hints (hide window/door/temperature status).
- Add `Subscription` fields: `package_type`, `term`, `trial_term`, `services` list.
- Add `UserProfile` dataclass and `get_user_profile()` API method.
- New CLI commands: `profile`, and `subscription` now shows services list.
- Translated fuel types (EV/PHEV/Petrol) and transmission (Automatic/Manual) in CLI output.
- Translated confirmation prompt, abort message, and capability error across 13 languages.
- Add configurable HTTP request timeout (`--http-timeout`, `HONDA_REQUEST_TIMEOUT` env var, `request_timeout` constructor parameter).

### Fixed

- Fix Polish `charge_speed_normal` translation.

### Changed

- Coordinates are accepted/returned in degrees; MAS conversion handled internally.
- Capability checks at library level: all command methods raise `ValueError` if the feature is not supported.
- Default 10-second timeout on all HTTP requests to prevent indefinite hangs.
- Retry only on 5xx status responses; transport errors (timeouts, connection failures) fail fast.

## 5.5.0 (2026-04-11)

### Added

- Add typed dataclasses: `Vehicle`, `VehicleCapabilities`, `Subscription`, `EVStatus`.
- New CLI commands: `capabilities`, `subscription`, `list --verbose`.
- Add translations for all new CLI strings across 13 languages.

### Changed

- `get_vehicles()` now returns `list[Vehicle]` with model name, grade, year, images, capabilities, and subscription info.
- `parse_ev_status()` now returns an `EVStatus` dataclass instead of a plain dict.
- All new types support dict-style access (`v["vin"]`, `v.get("fuel_type")`) for backward compatibility.
- `AuthTokens` serialization handles both old 5-field and new Vehicle format.

## 5.4.0 (2026-04-11)

### Added

- Add thread-safety to `HondaAPI` so a single instance can be shared across threads without external locking.
- Add GitHub issue and PR templates.
- Add CHANGELOG.md and CONTRIBUTING.md.

### Changed

- All `session.request()` calls and token refresh are serialized via an internal lock.
- Concurrent `refresh_auth()` calls are deduplicated (only one thread refreshes, others reuse the result).
- Remove redundant `range` field, use `range_climate_on` / `range_climate_off`.
- Bump development status from Alpha to Beta.

## 5.3.1 (2026-04-11)

### Fixed

- Fix lint errors.

## 5.3.0 (2026-04-11)

### Added

- Add i18n support for CLI status output (13 languages).
- Add climate range fields (`range_climate_on`, `range_climate_off`).

### Fixed

- Fix Italian and Norwegian translation issues.

## 5.2.2 (2026-04-09)

### Changed

- Improve handling when car does not respond to refresh.

## 5.2.1 (2026-04-08)

### Changed

- Refactor CLI command handling to consistently use return codes.

## 5.2.0 (2026-04-06)

### Added

- Add confirmation prompts, spinner, exit codes, CSV output, and shell completion.
- Add CLI behavioral tests.

## 5.1.0 (2026-04-04)

### Added

- Add multi-month trip aggregation in `trip-stats`.

### Fixed

- Handle malformed numeric fields gracefully.

## 5.0.0 (2026-04-04)

### Breaking

- `poll_command()` now returns a `CommandResult` object instead of a raw dict. Update code that used `{"status_code": ..., "data": ...}` to use `CommandResult` fields instead.

### Added

- Add structured `CommandResult` for async command polling.
- Add `HondaAuthError` for auth-specific failures.

### Changed

- Raise `HondaAuthError` for all authentication failures.

## 4.2.0 (2026-03-29)

### Added

- Add tests for DeviceKey, storage backends, and auth flow.
- Add ruff and mypy to CI.

## 4.1.0 (2026-03-29)

### Changed

- Route PUT methods through `_request` for automatic token refresh.
- Standardize error handling.

## 4.0.0 (2026-03-28)

### Breaking

- `remote_climate_on` renamed to `set_climate_settings`.

### Changed

- Remove unused token import feature.

## 3.0.0 (2026-03-25)

### Breaking

- Status output now uses dynamic units from the API instead of hardcoded km/°C.

### Added

- Add CI workflow to run tests on push and PR.
- Add test suite for parsing and computation helpers.

### Changed

- Validate charge limit values (80, 85, 90, 95, 100).

## 2.0.0 (2026-03-25)

### Added

- Add charge prohibition and climate schedule commands.
- Add climate-settings read and defrost toggle.
- Add `--version` flag to CLI.

### Fixed

- Handle schedule and climate errors for secondary users.

## 1.3.0 (2026-03-23)

### Changed

- Improve library API for Home Assistant integration.
- Extract trip helpers into API layer for library reuse.
- Show kWh/100km for electric vehicles instead of L/100km.

## 1.2.0 (2026-03-21)

### Added

- Add trip-stats, trip-detail commands and trip locations.
- Add `--watch` mode to status command.
- Encrypt tokens and device key at rest.
- Add PyPI badges to README.

## 1.1.0 (2026-03-21)

### Added

- Add vehicle list, auto-selection, and identification by name or plate.

## 1.0.1 (2026-03-18)

### Fixed

- Fix remote horn & lights endpoint.
- Fix lock/unlock command body.

## 1.0.0 (2026-03-16)

Initial release.

### Added

- Login with email verification.
- Vehicle status (battery, range, charge, location, doors, lights).
- Remote commands (lock, unlock, horn, climate, charge).
- Trip history.
- Encrypted token storage.
