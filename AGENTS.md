# AGENTS.md

Fast orientation for AI agents working on this repo. Humans should start with [`CONTRIBUTING.md`](CONTRIBUTING.md), which documents the architecture, conventions, test layout, and release process in full. This file complements that with quick-navigation pointers for agents starting cold; defer to CONTRIBUTING.md when in doubt.

This repo is the canonical source for sections 2, 3, and 5 below. The same sections appear in `myhondaplus-homeassistant/AGENTS.md` and `myhondaplus-desktop/AGENTS.md` and are kept in sync manually — update them here first, then propagate.

## 1. What this repo is

`pymyhondaplus` is the Python client library for the My Honda+ / Honda Connect Europe API. It is consumed by the [Home Assistant integration](https://github.com/enricobattocchi/myhondaplus-homeassistant) and the [desktop app](https://github.com/enricobattocchi/myhondaplus-desktop), and ships its own CLI (`pymyhondaplus`).

## 2. Naming

Refer to the upstream service as "the My Honda+ API" or "the Honda Connect Europe API" in code, comments, commit messages, PR descriptions, log strings, and test names — matching the framing used in the public READMEs. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full style guide.

## 3. The three-repo ecosystem

`pymyhondaplus` (Python library + CLI) is consumed by:

- [`myhondaplus-homeassistant`](https://github.com/enricobattocchi/myhondaplus-homeassistant) — Home Assistant integration, pinned `==X.Y.Z` (HA convention).
- [`myhondaplus-desktop`](https://github.com/enricobattocchi/myhondaplus-desktop) — PyQt6 desktop app, pinned `>=X.Y.Z`.

**Ownership boundaries** — each concern lives in exactly one repo:

- **Library owns**: API request/response shapes, auth flow, `EVStatus` parsing, enum normalization (`charge_status`, `home_away`, `climate_temp`, geofence states), `VehicleCapabilities` resolution, capability raw-API-key labels, geofence state labels, geofence error messages, library-side translations (CLI strings + the `t_lib()` keys consumers bridge to).
- **HA integration owns**: entity descriptors, coordinators, config flow, services, `strings.json` + `translations/*.json`, error-handling conventions for HA.
- **Desktop owns**: view layer (MainWindow / widgets), controller, workers, dashboard / trip / geofence / vehicle UI, desktop `translations/*.json`, PyInstaller bundling.

If a task feels like it crosses boundaries, default to "the library owns the API/parsing/canonical enums; consumers are presentation" and confirm with the maintainer before editing across repos.

**Triage rule.** When investigating an issue or fix in a consumer repo (HA or desktop), use the ownership boundaries above. If the symptom is in library-owned territory (API request/response shape, parsing, enum normalization, capability resolution, library-owned translation strings), the issue or PR should be opened in `pymyhondaplus` — even if it was first surfaced through a consumer. When in doubt, a short Python repro against the library is the fastest way to confirm.

## 4. Where to touch code

| Task | Files |
|---|---|
| Add a remote command | new `remote_*` method on `HondaAPI` in `src/pymyhondaplus/api.py`; CLI wiring in `src/pymyhondaplus/cli.py`; translation strings in `src/pymyhondaplus/translations.py` (all 13 locales); tests in `tests/test_api_client.py` and the relevant `tests/test_cli_*.py` |
| Add an `EVStatus` field | `EVStatus` dataclass + `parse_ev_status()` in `src/pymyhondaplus/api.py` (defensive parsing — numerics may arrive as strings); CLI rendering in `cli.py` + translation entries; tests in `tests/test_parse_ev_status.py` |
| Add / expose a capability flag | `_CAPABILITY_FIELD_TO_API_KEY` mapping in `src/pymyhondaplus/api.py`; tests in `tests/test_capability_check.py` and `tests/test_vehicle.py`. Consumers don't need to bump for new flags — `__getattr__` resolves them via `caps.raw`. |
| Normalize a new enum value | helper in `api.py` (`_normalize_*`); flag a follow-up to update consumers' enum sensor `options` lists if the value will be exposed |
| Add a new endpoint | new method on `HondaAPI` in `api.py`; fixture in `tests/`; test in `tests/test_api_client.py` |
| Auth-flow change | `src/pymyhondaplus/auth.py` (`HondaAuth`) and/or `HondaAPI.refresh_auth` in `api.py`; tests in `tests/test_auth.py`, `tests/test_thread_safety.py` (refresh is behind `self._lock`) |
| New CLI command | argparse + handler in `src/pymyhondaplus/cli.py`; translation strings in `translations.py`; tests in `tests/test_cli_*.py` |
| New translated string | `TRANSLATIONS` dict in `src/pymyhondaplus/translations.py` (all 13 locales); `tests/test_translations.py` enforces coverage |

## 5. Cross-repo workflows

- **Release order is library first, then consumers.** Bump `pymyhondaplus`, tag, GitHub-release; then update HA `manifest.json` `requirements` (`==X.Y.Z`) and/or desktop `pyproject.toml` + `README.md` (`>=X.Y.Z`), then release each consumer.
- **Pin update rule**: HA pins exact (Home Assistant convention); desktop pins minimum.
- **Translation-drift PRs** may span library + HA. When a string converges in wording, move the pair from `_KNOWN_DRIFT` to `ENFORCED_OVERLAPS` in the same PR (HA test: `tests/test_translation_drift.py`).

## 6. Common pitfalls

- Parsing is defensive by design — numeric fields can arrive as strings, GPS coordinates can be DMS or decimal. Use the existing `_safe_int` / `_safe_float` / coord helpers; don't `int()` directly.
- Enum normalization is canonical. Don't add raw upstream values like `"running"` or `"unavailable"` to public exports — consumers depend on the canonical set.
- Token refresh is thread-safe via `HondaAPI._lock`; don't add code paths that bypass it.

## 7. Gates

`pytest` (Python 3.11/3.12/3.13 matrix), `ruff check`, `mypy`. Tag is the bare version (e.g. `5.8.2`, not `v5.8.2`). `CHANGELOG.md` is updated in the same PR as the version bump.

## 8. Full reference

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the complete architecture, test layout, vehicle-testing notes, capability/EVStatus/CLI field-addition recipes, code style, and release process. The same guidance that applies to human contributors applies to agents.
