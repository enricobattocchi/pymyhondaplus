"""Tests for DeviceKey — RSA key generation, serialization, and signing."""

import base64

from pymyhondaplus.auth import DeviceKey


class TestDeviceKeyGeneration:

    def test_generates_key_on_init(self):
        dk = DeviceKey()
        assert dk.pem_bytes.startswith(b"-----BEGIN PRIVATE KEY-----")

    def test_pem_roundtrip(self):
        dk1 = DeviceKey()
        dk2 = DeviceKey(pem_data=dk1.pem_bytes)
        assert dk1.public_key_b64 == dk2.public_key_b64

    def test_public_key_is_valid_base64(self):
        dk = DeviceKey()
        decoded = base64.b64decode(dk.public_key_b64)
        assert len(decoded) > 0

    def test_key_identifier_equals_public_key(self):
        dk = DeviceKey()
        assert dk.key_identifier == dk.public_key_b64

    def test_different_keys_have_different_public_keys(self):
        dk1 = DeviceKey()
        dk2 = DeviceKey()
        assert dk1.public_key_b64 != dk2.public_key_b64


class TestDeviceKeySign:

    def test_sign_returns_base64(self):
        dk = DeviceKey()
        sig = dk.sign("hello world")
        decoded = base64.b64decode(sig)
        assert len(decoded) > 0

    def test_sign_is_deterministic(self):
        dk = DeviceKey()
        sig1 = dk.sign("test data")
        sig2 = dk.sign("test data")
        assert sig1 == sig2

    def test_sign_different_data_different_signature(self):
        dk = DeviceKey()
        sig1 = dk.sign("data1")
        sig2 = dk.sign("data2")
        assert sig1 != sig2

    def test_sign_verifiable_with_public_key(self):
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        dk = DeviceKey()
        data = "verify me"
        sig = base64.b64decode(dk.sign(data))

        pub_key = serialization.load_der_public_key(
            base64.b64decode(dk.public_key_b64)
        )
        # Should not raise
        pub_key.verify(sig, data.encode(), padding.PKCS1v15(), hashes.SHA256())


class TestDeviceKeyFileIO:

    def test_load_from_file(self, tmp_path):
        key_file = tmp_path / "test.pem"
        dk1 = DeviceKey(key_file=key_file)
        assert key_file.exists()

        dk2 = DeviceKey(key_file=key_file)
        assert dk1.public_key_b64 == dk2.public_key_b64

    def test_generates_when_file_missing(self, tmp_path):
        key_file = tmp_path / "new.pem"
        dk = DeviceKey(key_file=key_file)
        assert key_file.exists()
        assert dk.pem_bytes.startswith(b"-----BEGIN PRIVATE KEY-----")

    def test_file_permissions(self, tmp_path):
        key_file = tmp_path / "test.pem"
        DeviceKey(key_file=key_file)
        assert oct(key_file.stat().st_mode & 0o777) == "0o600"

    def test_load_via_storage(self):
        from unittest.mock import MagicMock

        dk1 = DeviceKey()
        storage = MagicMock()
        storage.load_device_key.return_value = dk1.pem_bytes

        dk2 = DeviceKey(storage=storage)
        assert dk2.public_key_b64 == dk1.public_key_b64
        storage.load_device_key.assert_called_once()

    def test_generates_and_saves_via_storage(self):
        from unittest.mock import MagicMock

        storage = MagicMock()
        storage.load_device_key.return_value = None

        dk = DeviceKey(storage=storage)
        assert dk.pem_bytes.startswith(b"-----BEGIN PRIVATE KEY-----")
        storage.save_device_key.assert_called_once()
