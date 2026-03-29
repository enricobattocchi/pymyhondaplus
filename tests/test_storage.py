"""Tests for storage backends — PlainFileStorage and EncryptedFileStorage."""

import json
from unittest.mock import MagicMock, patch

import pytest

from pymyhondaplus.storage import (
    PlainFileStorage,
    EncryptedFileStorage,
    KeyringStorage,
    get_storage,
)


@pytest.fixture
def plain_storage(tmp_path):
    return PlainFileStorage(tmp_path / "tokens.json", tmp_path / "key.pem")


@pytest.fixture
def encrypted_storage(tmp_path):
    return EncryptedFileStorage(tmp_path / "tokens.json", tmp_path / "key.pem")


SAMPLE_TOKENS = {
    "access_token": "tok123",
    "refresh_token": "ref456",
    "expires_at": 9999999999.0,
    "personal_id": "pid",
    "user_id": "uid",
}


class TestPlainFileStorage:

    def test_tokens_roundtrip(self, plain_storage):
        plain_storage.save_tokens(SAMPLE_TOKENS)
        loaded = plain_storage.load_tokens()
        assert loaded == SAMPLE_TOKENS

    def test_device_key_roundtrip(self, plain_storage):
        pem = b"-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----\n"
        plain_storage.save_device_key(pem)
        assert plain_storage.load_device_key() == pem

    def test_load_tokens_missing_file(self, plain_storage):
        assert plain_storage.load_tokens() is None

    def test_load_device_key_missing_file(self, plain_storage):
        assert plain_storage.load_device_key() is None

    def test_file_permissions(self, plain_storage):
        plain_storage.save_tokens(SAMPLE_TOKENS)
        assert oct(plain_storage.token_file.stat().st_mode & 0o777) == "0o600"

    def test_clear_removes_files(self, plain_storage):
        plain_storage.save_tokens(SAMPLE_TOKENS)
        plain_storage.save_device_key(b"key")
        plain_storage.clear()
        assert not plain_storage.token_file.exists()
        assert not plain_storage.key_file.exists()

    def test_clear_no_files_ok(self, plain_storage):
        plain_storage.clear()  # Should not raise

    def test_raises_on_encrypted_format(self, plain_storage):
        plain_storage.token_file.write_text(json.dumps({
            "v": 2, "enc": "fernet", "data": "abc"
        }))
        with pytest.raises(RuntimeError, match="encrypted"):
            plain_storage.load_tokens()


class TestEncryptedFileStorage:

    def test_tokens_roundtrip(self, encrypted_storage):
        encrypted_storage.save_tokens(SAMPLE_TOKENS)
        loaded = encrypted_storage.load_tokens()
        assert loaded == SAMPLE_TOKENS

    def test_device_key_roundtrip(self, encrypted_storage):
        pem = b"-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----\n"
        encrypted_storage.save_device_key(pem)
        assert encrypted_storage.load_device_key() == pem

    def test_file_is_encrypted(self, encrypted_storage):
        encrypted_storage.save_tokens(SAMPLE_TOKENS)
        raw = json.loads(encrypted_storage.token_file.read_text())
        assert raw["v"] == 2
        assert raw["enc"] == "fernet"
        assert "access_token" not in raw

    def test_load_tokens_missing_file(self, encrypted_storage):
        assert encrypted_storage.load_tokens() is None

    def test_salt_generated_on_first_use(self, encrypted_storage):
        encrypted_storage.save_tokens(SAMPLE_TOKENS)
        salt_file = encrypted_storage._salt_file
        assert salt_file.exists()
        assert len(salt_file.read_bytes()) == 32

    def test_salt_reused(self, encrypted_storage):
        encrypted_storage.save_tokens(SAMPLE_TOKENS)
        salt1 = encrypted_storage._salt_file.read_bytes()
        encrypted_storage.save_tokens(SAMPLE_TOKENS)
        salt2 = encrypted_storage._salt_file.read_bytes()
        assert salt1 == salt2

    def test_clear_removes_salt(self, encrypted_storage):
        encrypted_storage.save_tokens(SAMPLE_TOKENS)
        encrypted_storage.clear()
        assert not encrypted_storage._salt_file.exists()

    def test_migrates_plain_tokens(self, encrypted_storage):
        """Plain-text token file should be auto-migrated to encrypted."""
        encrypted_storage.token_file.write_text(json.dumps(SAMPLE_TOKENS))
        loaded = encrypted_storage.load_tokens()
        assert loaded == SAMPLE_TOKENS
        # File should now be in encrypted format
        raw = json.loads(encrypted_storage.token_file.read_text())
        assert raw["v"] == 2

    def test_wrong_key_removes_file(self, tmp_path):
        """If encryption key changes, stale file is removed."""
        s1 = EncryptedFileStorage(tmp_path / "tokens.json", tmp_path / "key.pem")
        s1.save_tokens(SAMPLE_TOKENS)

        # Change the salt to simulate a different machine
        s1._salt_file.write_bytes(b"x" * 32)

        loaded = s1.load_tokens()
        assert loaded is None
        assert not s1.token_file.exists()


class TestGetStorage:

    def test_plain_backend(self, tmp_path):
        s = get_storage(tmp_path / "t", tmp_path / "k", backend="plain")
        assert isinstance(s, PlainFileStorage)

    def test_encrypted_backend(self, tmp_path):
        s = get_storage(tmp_path / "t", tmp_path / "k", backend="encrypted")
        assert isinstance(s, EncryptedFileStorage)

    def test_keyring_backend_raises_without_keyring(self, tmp_path):
        with patch("pymyhondaplus.storage._find_keyring_backend", return_value=None):
            with pytest.raises(RuntimeError, match="No working keyring"):
                get_storage(tmp_path / "t", tmp_path / "k", backend="keyring")

    def test_keyring_backend_with_backend(self, tmp_path):
        mock_backend = MagicMock()
        with patch("pymyhondaplus.storage._find_keyring_backend", return_value=mock_backend):
            s = get_storage(tmp_path / "t", tmp_path / "k", backend="keyring")
            assert isinstance(s, KeyringStorage)

    def test_auto_falls_back_to_encrypted(self, tmp_path):
        with patch("pymyhondaplus.storage._find_keyring_backend", return_value=None):
            s = get_storage(tmp_path / "t", tmp_path / "k", backend="auto")
            assert isinstance(s, EncryptedFileStorage)

    def test_auto_prefers_keyring(self, tmp_path):
        mock_backend = MagicMock()
        with patch("pymyhondaplus.storage._find_keyring_backend", return_value=mock_backend):
            s = get_storage(tmp_path / "t", tmp_path / "k", backend="auto")
            assert isinstance(s, KeyringStorage)
