# pymyhondaplus

Python client for the Honda Connect Europe (My Honda+) API.

Works with Honda e, e:Ny1, ZR-V, CR-V, Civic, HR-V, Jazz (2020+) in Europe.

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

# Lock doors
pymyhondaplus -v JHMZC7840LXXXXXX lock
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
