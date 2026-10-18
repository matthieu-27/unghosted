"""Envelope encryption (ADR 0001): a random AES-256-GCM data key encrypts
the file content, the master key wraps the data key. Identical for the
local and S3 storage backends — encrypted bytes only reach storage."""

from __future__ import annotations

import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ALGORITHM_VERSION = "aes-256-gcm-envelope-v1"
"""Stored in documents.key_algorithm_version so future rotations can
migrate rows explicitly."""

_NONCE_BYTES = 12


class DecryptionError(RuntimeError):
    """Ciphertext or wrapped key failed authentication (tampered or the
    master key changed). Download must fail closed, never serve garbage."""


class EnvelopeEncryptor:
    def __init__(self, master_key: bytes) -> None:
        if len(master_key) != 32:
            raise ValueError(f"master key must be 32 bytes, got {len(master_key)}")
        self._master = AESGCM(master_key)

    def encrypt(self, plaintext: bytes) -> tuple[bytes, bytes]:
        """Return (encrypted_content, encrypted_data_key), both prefixed
        with their own random nonce. The data key exists only inside this
        call."""
        data_key = AESGCM.generate_key(bit_length=256)
        nonce = os.urandom(_NONCE_BYTES)
        encrypted_content = nonce + AESGCM(data_key).encrypt(nonce, plaintext, None)
        key_nonce = os.urandom(_NONCE_BYTES)
        encrypted_data_key = key_nonce + self._master.encrypt(key_nonce, data_key, None)
        return encrypted_content, encrypted_data_key

    def decrypt(self, encrypted_content: bytes, encrypted_data_key: bytes) -> bytes:
        try:
            data_key = self._master.decrypt(
                encrypted_data_key[:_NONCE_BYTES],
                encrypted_data_key[_NONCE_BYTES:],
                None,
            )
            return AESGCM(data_key).decrypt(
                encrypted_content[:_NONCE_BYTES],
                encrypted_content[_NONCE_BYTES:],
                None,
            )
        except InvalidTag as exc:
            raise DecryptionError("document decryption failed") from exc
