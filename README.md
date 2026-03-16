# pymyhondaplus

Python client for the Honda Connect Europe (My Honda+) API.

Tested on Honda e. Should work with other Honda Connect Europe vehicles (e:Ny1, ZR-V, CR-V, Civic, HR-V, Jazz 2020+) but these are untested — contributions welcome!

## Installation

```bash
pip install pymyhondaplus
```

## CLI usage

```bash
# Login (first time — triggers email verification)
pymyhondaplus login --email user@example.com --password secret

# Get vehicle status
pymyhondaplus -v JHMZC7840LXXXXXX status

# Get fresh status from car (wakes TCU)
pymyhondaplus -v JHMZC7840LXXXXXX status --fresh

# Lock / unlock doors
pymyhondaplus -v JHMZC7840LXXXXXX lock
pymyhondaplus -v JHMZC7840LXXXXXX unlock

# Request fresh car location (wakes TCU)
pymyhondaplus -v JHMZC7840LXXXXXX location

# Climate control
pymyhondaplus -v JHMZC7840LXXXXXX climate-start
pymyhondaplus -v JHMZC7840LXXXXXX climate-stop
pymyhondaplus -v JHMZC7840LXXXXXX climate-settings --temp hotter --duration 30

# Set charge limits
pymyhondaplus -v JHMZC7840LXXXXXX charge-limit --home 80 --away 90

# Horn & lights
pymyhondaplus -v JHMZC7840LXXXXXX horn

# Trip history (current month)
pymyhondaplus -v JHMZC7840LXXXXXX trips
pymyhondaplus -v JHMZC7840LXXXXXX trips --all
```

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

## Disclaimer

This project is **unofficial** and **not affiliated with, endorsed by, or connected to Honda Motor Co., Ltd.** in any way.

- Use at your own risk. The authors accept no responsibility for any damage to your vehicle, account, or warranty.
- Honda may change their API at any time, which could break this library without notice.
- Sending remote commands (lock, unlock, climate, charging) to your vehicle is your responsibility. Make sure you understand what each command does before using it.
- This project does not store or transmit your credentials to any third party. Authentication is performed directly with Honda's servers.
