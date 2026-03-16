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

# Trip history
pymyhondaplus -v JHMZC7840LXXXXXX trips
pymyhondaplus -v JHMZC7840LXXXXXX trips --from 2026-03-14T00:00:00+00:00
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
