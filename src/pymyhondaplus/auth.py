"""
Honda Connect Europe authentication module.

Implements the full login flow including device registration and email verification.
Reverse-engineered from the My Honda+ Android app.
"""

import base64
import hashlib
import json
import logging
import os
import time
import urllib.parse
from pathlib import Path
from typing import Optional

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

logger = logging.getLogger(__name__)

API_BASE = "https://mobile-api.connected.honda-eu.com"

# Server RSA public key (hardcoded in the app)
SERVER_PUBLIC_KEY_B64 = (
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAyCLLwyLwpI1vsPcUNTgJ"
    "1dr2pJ53luEx/BuU4HVSVtz6HtkPpEDSiFDOOrpJJOTYUjzqV93bm7Q2t2g8pRqK"
    "0zjijLm4w1tdcZkxEwYVQJr8SOYza/zbeac2TMu4iu9SbbJM0fzUwX6IrBu/EE4G"
    "diIF3Dwm4tzNpqZeh1fXEy9A2MHzmZIdWdkowZlUUyLtXuGBcbTOBY7LFRLKK0bV"
    "UsC06w/dCD3Rhs48IXhAPyqSZYCIqofUvAq5NE0YzIPSSMKtrcPPL+Ae0F9/pz8q"
    "YisH8TWyZZ6ih0Y5HufjuDzNYfJLNt4CEiohs7+hZtfbshkKuw+vr3sS4g9zM0Ot"
    "SQIDAQAB"
)

AUTH_SERVER_PUBLIC_KEY_VERSION = "1bff05258b984f278f70ed8c9580ba79"

DEFAULT_HEADERS = {
    "user-agent": "okhttp/4.12.0",
    "accept-encoding": "gzip",
    "content-type": "application/json",
    "x-app-device-os": "android",
    "x-app-device-osversion": "26",
    "x-app-device-model": "HomeAssistant",
}

DEFAULT_DEVICE_KEY_FILE = Path.home() / ".honda_device_key.pem"


def _load_server_public_key():
    """Load Honda's server RSA public key."""
    from cryptography.hazmat.primitives.serialization import load_der_public_key
    key_bytes = base64.b64decode(SERVER_PUBLIC_KEY_B64)
    return load_der_public_key(key_bytes)


def _encrypt_with_aes(payload: str) -> dict:
    """AES-256-CBC encrypt a payload."""
    key = os.urandom(32)
    iv = os.urandom(16)

    payload_bytes = payload.encode("utf-8")
    pad_len = 16 - (len(payload_bytes) % 16)
    payload_bytes += bytes([pad_len] * pad_len)

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(payload_bytes) + encryptor.finalize()

    return {
        "cipherText": base64.b64encode(ciphertext).decode(),
        "iv": base64.b64encode(iv).decode(),
        "key": base64.b64encode(key).decode(),
    }


def _encrypt_with_server_public_key(payload: str) -> str:
    """RSA encrypt with Honda's server public key (RSA/PKCS1)."""
    server_key = _load_server_public_key()
    encrypted = server_key.encrypt(
        payload.encode("utf-8"),
        padding.PKCS1v15(),
    )
    return base64.b64encode(encrypted).decode()


def encrypt_request(data: dict) -> dict:
    """Encrypt a request payload using the app's encryption scheme."""
    payload_json = json.dumps(data)
    aes_result = _encrypt_with_aes(payload_json)

    encrypted_salt = _encrypt_with_server_public_key(aes_result["iv"])
    encrypted_key = _encrypt_with_server_public_key(aes_result["key"])

    return {
        "encryptedOneTimeKey": encrypted_key,
        "encryptedOneTimeSalt": encrypted_salt,
        "encryptedPayload": aes_result["cipherText"],
        "keyId": AUTH_SERVER_PUBLIC_KEY_VERSION,
    }


class DeviceKey:
    """Manages the device RSA keypair used for authentication.

    Can be created in three ways:
    - DeviceKey() — generates a new ephemeral key
    - DeviceKey(pem_data=b"...") — loads from PEM bytes
    - DeviceKey(key_file=Path(...)) — loads from file or generates and saves
    """

    def __init__(self, pem_data: Optional[bytes] = None,
                 key_file: Optional[Path] = None):
        self._key_file = key_file
        if pem_data:
            self._private_key = serialization.load_pem_private_key(pem_data, password=None)
        elif key_file is not None:
            self._load_or_generate(key_file)
        else:
            self._private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )

    def _load_or_generate(self, key_file: Path):
        if key_file.exists():
            pem_data = key_file.read_bytes()
            self._private_key = serialization.load_pem_private_key(pem_data, password=None)
            logger.info("Loaded existing device key from %s", key_file)
        else:
            self._private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
            key_file.write_bytes(self.pem_bytes)
            key_file.chmod(0o600)
            logger.info("Generated new device key at %s", key_file)

    @property
    def pem_bytes(self) -> bytes:
        """Get the private key as PEM-encoded bytes."""
        return self._private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

    @property
    def public_key_b64(self) -> str:
        """Get the public key in base64-encoded DER (X.509) format."""
        pub_bytes = self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return base64.b64encode(pub_bytes).decode()

    @property
    def key_identifier(self) -> str:
        """Get the key identifier (same as devicePublicKey)."""
        return self.public_key_b64

    def sign(self, data: str) -> str:
        """Sign data with the device private key (SHA256withRSA), return base64."""
        signature = self._private_key.sign(
            data.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode()


class HondaAuth:
    """Handles the full Honda Connect Europe authentication flow."""

    def __init__(self, device_key: Optional[DeviceKey] = None):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.device_key = device_key or DeviceKey()

    def _post(self, path: str, json_data: dict = None, **kwargs) -> requests.Response:
        return self.session.post(f"{API_BASE}{path}", json=json_data, **kwargs)

    def reset_device_authenticator(self, email: str, password: str,
                                    reset_type: str = "Replace") -> dict:
        """Register/replace device authenticator. Triggers email verification."""
        payload = encrypt_request({
            "emailAddress": email,
            "userPassword": password,
            "resetType": reset_type,
            "devicePublicKey": self.device_key.public_key_b64,
            "keyIdentifier": self.device_key.key_identifier,
        })
        resp = self._post("/auth/reset-device-authenticator", json_data=payload)
        logger.info("reset-device-authenticator: %s", resp.status_code)
        if resp.status_code not in (200, 202):
            raise RuntimeError(f"reset-device-authenticator failed: {resp.status_code} {resp.text}")
        return resp.json() if resp.text else {}

    def request_verify_link(self, email: str, request_type: str = "MfaSetup") -> dict:
        """Request a verification email link."""
        payload = encrypt_request({
            "emailAddress": email,
            "magicLinkRequestType": request_type,
        })
        resp = self._post("/auth/verify-link", json_data=payload)
        logger.info("verify-link: %s", resp.status_code)
        if resp.status_code not in (200, 202):
            raise RuntimeError(f"verify-link failed: {resp.status_code} {resp.text}")
        return resp.json() if resp.text else {}

    def check_verify_link_status(self, email: str) -> dict:
        """Check if the email verification link has been clicked."""
        payload = encrypt_request({"emailAddress": email})
        resp = self._post("/auth/verify-link/status", json_data=payload)
        return resp.json() if resp.text else {}

    def register_device(self, email: str, password: str) -> dict:
        """Register this device's public key with Honda."""
        payload = encrypt_request({
            "emailAddress": email,
            "userPassword": password,
            "devicePublicKey": self.device_key.public_key_b64,
            "devicePublicKeyIdentifier": self.device_key.key_identifier,
        })
        resp = self._post("/auth/register", json_data=payload)
        logger.info("register: %s", resp.status_code)
        if resp.status_code not in (200, 202):
            raise RuntimeError(f"register failed: {resp.status_code} {resp.text}")
        return resp.json() if resp.text else {}

    def initiate_login(self, email: str, password: str,
                       identity_provider: str = "isv-branded",
                       locale: str = "it") -> dict:
        """Step 1 of login: send encrypted credentials."""
        payload = encrypt_request({
            "emailAddress": email,
            "userPassword": password,
            "devicePublicKey": self.device_key.public_key_b64,
            "keyIdentifier": self.device_key.key_identifier,
            "locale": locale,
            "fingerprintSupport": False,
            "frontCameraSupport": False,
            "faceSupport": False,
            "pushToken": "",
            "deviceId": "homeassistant",
            "deviceName": "Home Assistant",
            "deviceType": "HomeAssistant",
            "platformType": "android",
            "osVersion": "26",
            "applicationId": "com.honda_eu.connected.app",
            "applicationVersion": "3.0.0",
        })
        resp = self._post("/auth/initiate-login", json_data=payload)
        logger.info("initiate-login: %s %s", resp.status_code, resp.text[:300] if resp.text else "")
        if resp.status_code not in (200, 202):
            raise RuntimeError(f"initiate-login failed: {resp.status_code} {resp.text}")
        return resp.json()

    def complete_login(self, email: str, password: str,
                       transaction_id: str, signature_challenge: str,
                       identity_provider: str = "isv-prod",
                       locale: str = "it") -> dict:
        """Step 2 of login: sign the challenge and send encrypted credentials."""
        signed_challenge = self.device_key.sign(signature_challenge)

        payload = encrypt_request({
            "emailAddress": email,
            "userPassword": password,
            "keyIdentifier": self.device_key.key_identifier,
            "identityProvider": identity_provider,
            "locale": locale,
            "transactionId": transaction_id,
            "signedChallengeResponse": signed_challenge,
        })
        resp = self._post("/auth/complete-login", json_data=payload)
        logger.info("complete-login: %s %s", resp.status_code, resp.text[:300] if resp.text else "")
        if resp.status_code not in (200, 202):
            raise RuntimeError(f"complete-login failed: {resp.status_code} {resp.text}")
        return resp.json()

    def login(self, email: str, password: str, locale: str = "it") -> dict:
        """Try initiate + complete login. Returns tokens dict or raises RuntimeError."""
        result = self.initiate_login(email, password, locale=locale)
        return self.complete_login(
            email, password,
            result["transactionId"], result["signatureChallenge"],
            locale=locale,
        )

    def verify_magic_link(self, key: str, link_type: str = "mfa") -> dict:
        """Verify a magic link with dontRedirect=true."""
        encoded_key = urllib.parse.quote(key, safe="+/=")
        url = f"{API_BASE}/auth/verify-link?type={link_type}&key={encoded_key}&dontRedirect=true"
        resp = self.session.get(url)
        logger.info("verify-link GET: %s %s", resp.status_code, resp.text[:200] if resp.text else "")
        return {"status_code": resp.status_code, "body": resp.text}

    def full_login(self, email: str, password: str, locale: str = "it") -> dict:
        """
        Complete login flow. If device is not registered, handles registration
        and email verification interactively (CLI only).
        """
        logger.info("Starting login for %s", email)

        try:
            result = self.initiate_login(email, password, locale=locale)
        except RuntimeError as e:
            error_text = str(e)
            if "device-authenticator-not-registered" in error_text:
                logger.info("Device not registered, starting registration flow")
                return self._handle_device_registration(email, password, locale)
            raise

        transaction_id = result["transactionId"]
        signature_challenge = result["signatureChallenge"]

        return self.complete_login(
            email, password, transaction_id, signature_challenge, locale=locale,
        )

    def _handle_device_registration(self, email: str, password: str,
                                     locale: str) -> dict:
        """Handle device registration + email verification + login."""
        print("\nRequesting device verification...")
        try:
            reset_result = self.reset_device_authenticator(
                email, password, reset_type="Replace")
            logger.info("reset-device-authenticator response: %s", reset_result)
            print("Verification email sent!")
        except RuntimeError as e:
            if "currently blocked" in str(e):
                logger.info("Reset already requested, proceeding")
                print("Reset already requested. If you got an email, click it now.")
            else:
                raise

        print("\n" + "=" * 60)
        print("  CHECK YOUR EMAIL!")
        print("  You'll receive a verification link from Honda.")
        print("  DO NOT click it — instead, copy the link URL and paste it here.")
        print("=" * 60)

        link = input("\nPaste the verification link here: ").strip()

        key, link_type = self.parse_verify_link_key(link)
        if not key:
            raise RuntimeError(f"Could not extract key from link: {link}")

        result = self.verify_magic_link(key, link_type)
        logger.info("Magic link verification result: %s", result)

        result = self.initiate_login(email, password, locale=locale)
        transaction_id = result["transactionId"]
        signature_challenge = result["signatureChallenge"]

        return self.complete_login(
            email, password, transaction_id, signature_challenge,
            locale=locale,
        )

    @staticmethod
    def extract_user_id(access_token: str) -> str:
        """Extract user_id (sub) from a JWT access token."""
        token_parts = access_token.split(".")
        if len(token_parts) >= 2:
            payload = token_parts[1] + "=" * (4 - len(token_parts[1]) % 4)
            return json.loads(base64.urlsafe_b64decode(payload)).get("sub", "")
        return ""

    @staticmethod
    def parse_verify_link_key(link: str) -> tuple[str, str]:
        """Extract key and type from a verification link URL."""
        parsed = urllib.parse.urlparse(link)
        params = {}
        for part in parsed.query.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k] = urllib.parse.unquote(v)
        return params.get("key", ""), params.get("type", "mfa")
