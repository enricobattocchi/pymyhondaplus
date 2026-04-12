"""Shared HTTP transport utilities for pymyhondaplus."""

import os

from requests.adapters import HTTPAdapter

DEFAULT_REQUEST_TIMEOUT = float(os.environ.get("HONDA_REQUEST_TIMEOUT", "10"))
DEFAULT_AUTH_TIMEOUT = float(os.environ.get("HONDA_AUTH_TIMEOUT", "30"))


class TimeoutAdapter(HTTPAdapter):
    """HTTPAdapter with a default timeout for all requests."""

    def __init__(self, *args, timeout=DEFAULT_REQUEST_TIMEOUT, **kwargs):
        self._timeout = timeout
        super().__init__(*args, **kwargs)

    def send(self, *args, **kwargs):
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = self._timeout
        return super().send(*args, **kwargs)
