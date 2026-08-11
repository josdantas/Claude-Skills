"""Envelope AES-256-GCM com DEK por registro.

O AAD amarra cada ciphertext ao seu record_id e à versão do esquema: um blob
movido para outro registro falha na autenticação em vez de decifrar em silêncio.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SCHEMA_VERSION = 1
NONCE_LEN = 12
DEK_LEN = 32


@dataclass(frozen=True, slots=True)
class Envelope:
    """Registro cifrado. Serializável direto para disco ou coluna de índice."""

    version: int
    wrapped_dek: bytes  # nonce ‖ ciphertext(DEK) sob a KEK
    payload: bytes  # nonce ‖ ciphertext(plaintext) sob a DEK

    def to_bytes(self) -> bytes:
        return (
            self.version.to_bytes(2, "big")
            + len(self.wrapped_dek).to_bytes(2, "big")
            + self.wrapped_dek
            + self.payload
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> "Envelope":
        version = int.from_bytes(raw[:2], "big")
        wlen = int.from_bytes(raw[2:4], "big")
        return cls(version, raw[4 : 4 + wlen], raw[4 + wlen :])


def _aad(record_id: str, version: int = SCHEMA_VERSION) -> bytes:
    return f"{record_id}\x1f{version}".encode("utf-8")


def seal(kek: bytes, record_id: str, plaintext: bytes) -> Envelope:
    dek = os.urandom(DEK_LEN)
    aad = _aad(record_id)

    n_payload = os.urandom(NONCE_LEN)
    payload = n_payload + AESGCM(dek).encrypt(n_payload, plaintext, aad)

    n_dek = os.urandom(NONCE_LEN)
    wrapped = n_dek + AESGCM(kek).encrypt(n_dek, dek, aad)

    return Envelope(SCHEMA_VERSION, wrapped, payload)


def open_(kek: bytes, record_id: str, env: Envelope) -> bytes:
    aad = _aad(record_id, env.version)
    dek = AESGCM(kek).decrypt(env.wrapped_dek[:NONCE_LEN], env.wrapped_dek[NONCE_LEN:], aad)
    return AESGCM(dek).decrypt(env.payload[:NONCE_LEN], env.payload[NONCE_LEN:], aad)
