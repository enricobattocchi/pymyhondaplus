# pymyhondaplus

[![PyPI](https://img.shields.io/pypi/v/pymyhondaplus)](https://pypi.org/project/pymyhondaplus/)
[![Python](https://img.shields.io/pypi/pyversions/pymyhondaplus)](https://pypi.org/project/pymyhondaplus/)
[![Downloads](https://img.shields.io/pypi/dm/pymyhondaplus)](https://pypi.org/project/pymyhondaplus/)
[![License](https://img.shields.io/pypi/l/pymyhondaplus)](https://pypi.org/project/pymyhondaplus/)

Unofficial Python client for the Honda Connect Europe (My Honda+) API.

Tested on Honda e. Should work with other Honda Connect Europe vehicles (e:Ny1, ZR-V, CR-V, Civic, HR-V, Jazz 2020+) but these are untested — contributions welcome!

## Installation

```bash
pip install pymyhondaplus

# Optional: enable OS keyring support (macOS Keychain, Windows Credential Vault, Linux Secret Service)
pip install pymyhondaplus[keyring]
```

## Quick start

```bash
# Login (first time — triggers email verification)
pymyhondaplus login --email user@example.com

# Vehicle status
pymyhondaplus status
pymyhondaplus status --fresh            # wake TCU for fresh data
pymyhondaplus status --watch 5m         # poll and print changes

# Remote commands
pymyhondaplus lock
pymyhondaplus unlock
pymyhondaplus horn
pymyhondaplus climate-start
pymyhondaplus charge-limit --home 80 --away 90

# Trip history and statistics
pymyhondaplus trips --all --locations
pymyhondaplus trip-stats --period week
```

See [USAGE.md](USAGE.md) for the full command reference, including vehicle selection, trip details, library usage, and security options.

## Related projects

- [myhondaplus-desktop](https://github.com/enricobattocchi/myhondaplus-desktop) — Desktop GUI application
- [myhondaplus-homeassistant](https://github.com/enricobattocchi/myhondaplus-homeassistant) — Home Assistant integration

## Disclaimer

This project is **unofficial** and **not affiliated with, endorsed by, or connected to Honda Motor Co., Ltd.** in any way.

- Use at your own risk. The authors accept no responsibility for any damage to your vehicle, account, or warranty.
- Honda may change their API at any time, which could break this library without notice.
- Sending remote commands (lock, unlock, climate, charging) to your vehicle is your responsibility. Make sure you understand what each command does before using it.
- This project does not store or transmit your credentials to any third party. Authentication is performed directly with Honda's servers.
