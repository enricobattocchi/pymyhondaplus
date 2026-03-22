# pymyhondaplus

Unofficial Python client for the Honda Connect Europe (My Honda+) API.

Tested on Honda e. Should work with other Honda Connect Europe vehicles (e:Ny1, ZR-V, CR-V, Civic, HR-V, Jazz 2020+) but these are untested — contributions welcome!

## Installation

```bash
pip install pymyhondaplus

# Optional: enable OS keyring support (macOS Keychain, Windows Credential Vault, Linux Secret Service)
pip install pymyhondaplus[keyring]
```

## CLI usage

```bash
# Login (first time — triggers email verification; password prompted if omitted)
pymyhondaplus login --email user@example.com

# List vehicles on your account
pymyhondaplus list

# Get vehicle status (auto-selects if only one vehicle)
pymyhondaplus status

# Get fresh status from car (wakes TCU)
pymyhondaplus status --fresh

# Lock / unlock doors
pymyhondaplus lock
pymyhondaplus unlock

# Request fresh car location (wakes TCU)
pymyhondaplus location

# Climate control
pymyhondaplus climate-start
pymyhondaplus climate-stop
pymyhondaplus climate-settings --temp hotter --duration 30

# Set charge limits
pymyhondaplus charge-limit --home 80 --away 90

# Horn & lights
pymyhondaplus horn

# Trip history (current month)
pymyhondaplus trips
pymyhondaplus trips --all
```

### Vehicle selection

If you have only one vehicle on your account, it's selected automatically. With multiple vehicles, specify one using `--vin` (or `-v`) with a VIN, nickname, or plate number:

```bash
pymyhondaplus -v "Honda e" status
pymyhondaplus -v GE395KM status
pymyhondaplus -v JHMZC7840LXXXXXX status

# Or via environment variable
export HONDA_VIN="Honda e"
pymyhondaplus status
```

### Security

Tokens and device keys are encrypted at rest using Fernet (AES-128-CBC). The encryption key is:

- **With `pymyhondaplus[keyring]`**: stored in the OS keyring (macOS Keychain, Windows Credential Vault, Linux Secret Service/KDE Wallet)
- **Without keyring**: derived from a machine-specific fingerprint (username + hostname + random salt via PBKDF2)

Use `--storage plain` to disable encryption (original behavior). Existing plain-text token files are automatically migrated to encrypted format on first use.

## Library usage

```python
from pymyhondaplus.api import HondaAPI
from pymyhondaplus.auth import HondaAuth, DeviceKey

# Authenticate
auth = HondaAuth()
tokens = auth.full_login("user@example.com", "password")

# Use the API
api = HondaAPI()
api.set_tokens(**tokens)
status = api.get_dashboard("JHMZC7840LXXXXXX")
```

## Related projects

- [myhondaplus-desktop](https://github.com/enricobattocchi/myhondaplus-desktop) — Desktop GUI application
- [myhondaplus-homeassistant](https://github.com/enricobattocchi/myhondaplus-homeassistant) — Home Assistant integration

## Disclaimer

This project is **unofficial** and **not affiliated with, endorsed by, or connected to Honda Motor Co., Ltd.** in any way.

- Use at your own risk. The authors accept no responsibility for any damage to your vehicle, account, or warranty.
- Honda may change their API at any time, which could break this library without notice.
- Sending remote commands (lock, unlock, climate, charging) to your vehicle is your responsibility. Make sure you understand what each command does before using it.
- This project does not store or transmit your credentials to any third party. Authentication is performed directly with Honda's servers.
