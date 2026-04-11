# Changelog

All notable changes to this project will be documented in this file.

## 5.4.0 — 2026-04-11

- Add thread-safety to `HondaAPI` so a single instance can be shared across threads without external locking
- All `session.request()` calls and token refresh are serialized via an internal lock
- Concurrent `refresh_auth()` calls are deduplicated (only one thread refreshes, others reuse the result)

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
