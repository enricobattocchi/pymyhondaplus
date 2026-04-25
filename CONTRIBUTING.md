# Contributing

Thanks for your interest in contributing to pymyhondaplus!

## Reporting issues

If something isn't working, please [open an issue](https://github.com/enricobattocchi/pymyhondaplus/issues) with:

- Your vehicle model (e.g. Honda e, ZR-V, e:Ny1)
- Python version
- The command you ran and the output you got (redact any personal data)

## Development setup

```bash
git clone https://github.com/enricobattocchi/pymyhondaplus.git
cd pymyhondaplus
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running tests and linting

```bash
pytest
ruff check src/ tests/
mypy src/
```

All three must pass before a PR can be merged. CI runs these automatically on Python 3.11, 3.12, and 3.13.

## Submitting changes

1. Fork the repo and create a branch from `main`.
2. Make your changes. Add tests for new functionality.
3. Run `pytest`, `ruff check`, and `mypy` locally.
4. Open a pull request with a clear description of what you changed and why.

## Vehicle testing

This library is only fully tested on the Honda e. If you own a different Honda Connect Europe vehicle and can confirm that a feature works (or doesn't), that's one of the most valuable contributions you can make — just open an issue with your findings.

## Architecture

```
src/pymyhondaplus/
  api.py          — Dataclasses, HondaAPI client, parse_* functions
  cli.py          — CLI: argparse, command handlers, i18n output
  auth.py         — Login flow: device keys, RSA/AES encryption, magic links
  storage.py      — Token/key persistence: plain, encrypted, keyring backends
  http.py         — Shared TimeoutAdapter for requests
  translations.py — CLI string translations (13 locales) + maps
```

### Key patterns

- **Dataclasses as API models** (`EVStatus`, `Vehicle`, `Geofence`, `AuthTokens`, `CommandResult`, `Subscription`, `UIConfiguration`, `UserProfile`). Each has `from_api()`, `to_dict()`, and `from_dict()`.
- **`VehicleCapabilities` is raw-backed**: a single `raw: dict` holds the capability map. Known attribute names like `caps.remote_lock` are resolved through `__getattr__` against the `_CAPABILITY_FIELD_TO_API_KEY` registry. Unknown future flags are reachable via `caps.raw` without a library update. Use `caps.active_api_keys()` / `caps.not_supported_api_keys()` to enumerate.
- **`parse_ev_status(dashboard) → EVStatus`** is the main interface downstream consumers (HA integration, desktop) rely on. Numeric fields use `_safe_int()` / `_safe_float()`; enum-like fields are normalized to a canonical set.
- **CLI command handlers** each return an int exit code. Destructive commands require `_confirm()` unless `--yes` is passed.
- **Translations** live in `translations.py`. `TRANSLATIONS` and `get_translator()` are exported at package root for downstream consumers that share strings.

### API conventions

- GPS coordinates arrive in different formats from different endpoints. Helpers in `api.py` normalize to floats.
- Many "numeric" fields can arrive as strings or with bad data. Always use `_safe_int()` / `_safe_float()`.
- Enum-like fields can contain unexpected values across vehicle models. Normalize with a whitelist or mapping; never pass raw strings to downstream consumers.
- Different field shapes per vehicle model (Honda e vs ZR-V vs e:Ny1). Defensive parsing is essential.
- Geofence operations have two state machines: `isCommandProcessing` (server bookkeeping) and `isWaitingForActivate` / `isWaitingForDeactivate` (real "command in flight"). `wait_for_geofence` polls on the latter.

### Test layout

Tests live in `tests/` with shared fixtures in `conftest.py`. The `dashboard_ev` fixture is a realistic Honda e dashboard response.

| File | Coverage |
|---|---|
| `test_parse_ev_status.py` | EVStatus parsing and normalization |
| `test_cli_behavior.py`, `test_cli_capabilities.py`, `test_cli_trip_stats.py` | CLI flows with `_FakeAPI` |
| `test_api_client.py` | HondaAPI methods |
| `test_auth.py`, `test_device_key.py` | Authentication |
| `test_schedules.py` | Charge/climate schedules |
| `test_geofence.py` | Geofence parsing + `wait_for_geofence` polling |
| `test_storage.py` | Token persistence backends |
| `test_trip_stats.py` | Trip aggregation |
| `test_capability_check.py` | Vehicle capability gating |
| `test_thread_safety.py` | Concurrent token refresh |
| `test_translations.py` | i18n string coverage |
| `test_vehicle.py` | Vehicle dataclass + `VehicleCapabilities` |

### Adding a new EVStatus field

1. Add the field to the dataclass with a safe default.
2. Parse it with `_safe_int()` / `_safe_float()` (numerics) or whitelist/mapping (enums).
3. Update `to_dict()` if present.
4. Add tests including malformed-input cases.
5. If the CLI displays it, add translated strings to all 13 locales in `translations.py`.

### Adding a new CLI command

1. Subparser in `build_parser()`.
2. `_handle_*_command()` returning an int.
3. Wire into `_run_main()`.
4. Destructive → `_confirm_command()`.
5. Translated strings in `translations.py`.
6. Test in `test_cli_behavior.py` with `_FakeAPI`.

### Adding a known capability flag

Add the Python attribute name → API key entry to `_CAPABILITY_FIELD_TO_API_KEY` in `api.py`. That single addition gives `caps.<name>` attribute access AND fallback support when token caches lack `raw`. No dataclass field needed.

## Code style

- Follow existing patterns in the codebase.
- Type hints are expected for public functions.
- Keep dependencies minimal — don't add new ones without a strong reason.
- Tags use bare version numbers (`5.8.2`), not `v5.8.2`.

## Translations

Translation values that map to user-visible strings should be coherent and accurate per locale. If you're unsure about wording for a language, prefer leaving the field unset (English is the fallback) over guessing.

## Release process

1. Bump `version` in `pyproject.toml`.
2. Add a `## X.Y.Z — YYYY-MM-DD` section to `CHANGELOG.md`.
3. Verify `pytest` / `ruff` / `mypy` are clean.
4. PR → merge to `main` (merge commit, not squash).
5. Tag `X.Y.Z` (no `v` prefix) on the merge commit. Push the tag.
6. `gh release create X.Y.Z` triggers the GitHub Actions workflow that uploads to PyPI.
