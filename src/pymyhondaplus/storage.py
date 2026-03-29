"""Secure storage backends for tokens and device keys."""

import base64
import getpass
import json
import logging
import os
import platform
from abc import ABC, abstractmethod
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

logger = logging.getLogger(__name__)

KEYRING_SERVICE = "pymyhondaplus"
KEYRING_KEY_NAME = "fernet-key"
ENCRYPTED_FORMAT_VERSION = 2


def _write_secure(path: Path, data: bytes | str):
    """Write data to a file with 0600 permissions."""
    if isinstance(data, str):
        data = data.encode()
    path.write_bytes(data)
    path.chmod(0o600)


def _is_encrypted_format(data: dict) -> bool:
    return data.get("v") == ENCRYPTED_FORMAT_VERSION and "enc" in data


class SecretStorage(ABC):
    """Abstract base for secret storage backends."""

    def __init__(self, token_file: Path, key_file: Path):
        self.token_file = token_file
        self.key_file = key_file

    @abstractmethod
    def save_tokens(self, tokens_dict: dict) -> None: ...

    @abstractmethod
    def load_tokens(self) -> dict | None: ...

    @abstractmethod
    def save_device_key(self, pem_bytes: bytes) -> None: ...

    @abstractmethod
    def load_device_key(self) -> bytes | None: ...

    @abstractmethod
    def clear(self) -> None: ...


class PlainFileStorage(SecretStorage):
    """Store secrets as plain-text files with 0600 permissions (original behavior)."""

    def save_tokens(self, tokens_dict: dict) -> None:
        _write_secure(self.token_file, json.dumps(tokens_dict))

    def load_tokens(self) -> dict | None:
        if not self.token_file.exists():
            return None
        data = json.loads(self.token_file.read_text())
        # If file is in encrypted format, we can't read it
        if _is_encrypted_format(data):
            raise RuntimeError(
                f"Token file {self.token_file} is encrypted. "
                "Use --storage auto or --storage encrypted to read it."
            )
        return data

    def save_device_key(self, pem_bytes: bytes) -> None:
        _write_secure(self.key_file, pem_bytes)

    def load_device_key(self) -> bytes | None:
        if not self.key_file.exists():
            return None
        return self.key_file.read_bytes()

    def clear(self) -> None:
        for f in [self.token_file, self.key_file]:
            if f.exists():
                f.unlink()


class _FernetStorage(SecretStorage):
    """Base for Fernet-encrypted storage backends."""

    def _get_fernet_key(self) -> bytes:
        raise NotImplementedError

    def _clear_fernet_key(self) -> None:
        pass

    def _fernet(self) -> Fernet:
        return Fernet(self._get_fernet_key())

    def _encrypt(self, data: bytes) -> bytes:
        return self._fernet().encrypt(data)

    def _decrypt(self, data: bytes) -> bytes:
        return self._fernet().decrypt(data)

    def _save_encrypted_file(self, path: Path, plaintext: bytes) -> None:
        envelope = {
            "v": ENCRYPTED_FORMAT_VERSION,
            "enc": "fernet",
            "data": self._encrypt(plaintext).decode(),
        }
        _write_secure(path, json.dumps(envelope))

    def _load_encrypted_file(self, path: Path) -> bytes | None:
        if not path.exists():
            return None
        raw = path.read_text()

        # Try to parse as JSON
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Not JSON — might be a plain PEM key
            return raw.encode()

        # Encrypted format
        if _is_encrypted_format(data):
            try:
                return self._decrypt(data["data"].encode())
            except InvalidToken:
                logger.warning(
                    "Cannot decrypt %s (encryption key changed). "
                    "Removing stale file — please login again.", path
                )
                path.unlink()
                return None

        # Plain-text token format — migrate
        if "access_token" in data:
            logger.debug("Migrating %s to encrypted storage", path)
            plaintext = json.dumps(data).encode()
            self._save_encrypted_file(path, plaintext)
            return plaintext

        return raw.encode()

    def save_tokens(self, tokens_dict: dict) -> None:
        self._save_encrypted_file(self.token_file, json.dumps(tokens_dict).encode())

    def load_tokens(self) -> dict | None:
        data = self._load_encrypted_file(self.token_file)
        if data is None:
            return None
        return json.loads(data)

    def save_device_key(self, pem_bytes: bytes) -> None:
        self._save_encrypted_file(self.key_file, pem_bytes)

    def load_device_key(self) -> bytes | None:
        return self._load_encrypted_file(self.key_file)

    def clear(self) -> None:
        for f in [self.token_file, self.key_file]:
            if f.exists():
                f.unlink()
        self._clear_fernet_key()


class EncryptedFileStorage(_FernetStorage):
    """Fernet encryption with a machine-derived key (no OS keyring needed).

    The Fernet key is derived from username + hostname + a random salt via PBKDF2.
    The salt is stored in a file next to the token file.
    """

    def __init__(self, token_file: Path, key_file: Path):
        super().__init__(token_file, key_file)
        self._salt_file = token_file.parent / ".honda_storage_salt"

    def _get_salt(self) -> bytes:
        if self._salt_file.exists():
            return self._salt_file.read_bytes()
        salt = os.urandom(32)
        _write_secure(self._salt_file, salt)
        return salt

    def _get_fernet_key(self) -> bytes:
        salt = self._get_salt()
        identity = f"{getpass.getuser()}@{platform.node()}".encode()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=600_000,
        )
        key = kdf.derive(identity)
        return base64.urlsafe_b64encode(key)

    def clear(self) -> None:
        super().clear()
        if self._salt_file.exists():
            self._salt_file.unlink()


class KeyringStorage(_FernetStorage):
    """Fernet encryption with the key stored in the OS keyring.

    Uses a specific keyring backend directly (not the chainer) to avoid
    triggering popups from multiple backends simultaneously.
    """

    def __init__(self, token_file: Path, key_file: Path, keyring_backend=None):
        super().__init__(token_file, key_file)
        self._backend = keyring_backend

    def _get_fernet_key(self) -> bytes:
        key = self._backend.get_password(KEYRING_SERVICE, KEYRING_KEY_NAME)
        if key is None:
            key = Fernet.generate_key().decode()
            self._backend.set_password(KEYRING_SERVICE, KEYRING_KEY_NAME, key)
            logger.debug("Generated new Fernet key in OS keyring")
        return key.encode()

    def _clear_fernet_key(self) -> None:
        try:
            self._backend.delete_password(KEYRING_SERVICE, KEYRING_KEY_NAME)
        except Exception:
            pass


def _find_keyring_backend():
    """Find the best working keyring backend, trying each one directly."""
    try:
        import keyring  # noqa: F401
    except ImportError:
        return None

    # Preferred backends in order (most common/reliable first)
    backend_classes = []
    for mod_name, cls_name in [
        ("keyring.backends.SecretService", "Keyring"),       # Linux (gnome-keyring, KDE with secret service)
        ("keyring.backends.libsecret", "Keyring"),           # Linux (libsecret)
        ("keyring.backends.kwallet", "DBusKeyring"),         # Linux (KDE Wallet)
        ("keyring.backends.macOS", "Keyring"),               # macOS Keychain
        ("keyring.backends.Windows", "WinVaultKeyring"),     # Windows
    ]:
        try:
            mod = __import__(mod_name, fromlist=[cls_name])
            cls = getattr(mod, cls_name)
            if cls.viable:
                backend_classes.append(cls)
        except (ImportError, AttributeError, Exception):
            continue

    # Try each viable backend with a real operation
    for cls in backend_classes:
        try:
            backend = cls()
            backend.get_password(KEYRING_SERVICE, "__probe__")
            logger.debug("Using keyring backend: %s", type(backend).__name__)
            return backend
        except Exception:
            continue

    return None


def get_storage(token_file: Path, key_file: Path,
                backend: str = "auto") -> SecretStorage:
    """Create a storage backend.

    Args:
        token_file: Path for token storage
        key_file: Path for device key storage
        backend: "auto", "keyring", "encrypted", or "plain"
    """
    if backend == "plain":
        return PlainFileStorage(token_file, key_file)
    if backend == "keyring":
        kb = _find_keyring_backend()
        if kb is None:
            raise RuntimeError("No working keyring backend found. Install keyring and a backend.")
        return KeyringStorage(token_file, key_file, keyring_backend=kb)
    if backend == "encrypted":
        return EncryptedFileStorage(token_file, key_file)

    # auto: try keyring, fall back to encrypted file
    kb = _find_keyring_backend()
    if kb is not None:
        return KeyringStorage(token_file, key_file, keyring_backend=kb)

    logger.debug("Using encrypted file storage (no keyring available)")
    return EncryptedFileStorage(token_file, key_file)
