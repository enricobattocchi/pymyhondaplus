# Changelog

All notable changes to this project will be documented in this file.

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
