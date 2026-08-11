"""Derivação de chave. Parâmetros fixos e versionados — ver docs/arca-plano-de-implementacao.md §1."""

from __future__ import annotations

from dataclasses import dataclass

from argon2.low_level import Type, hash_secret_raw

KDF_VERSION = 1

# Argon2id m=256MiB, t=3, p=4 (parâmetro de contrato do projeto).
ARGON2_MEMORY_KIB = 256 * 1024
ARGON2_TIME_COST = 3
ARGON2_PARALLELISM = 4
KEY_LEN = 32  # AES-256


@dataclass(frozen=True)
class KdfParams:
    version: int = KDF_VERSION
    memory_kib: int = ARGON2_MEMORY_KIB
    time_cost: int = ARGON2_TIME_COST
    parallelism: int = ARGON2_PARALLELISM


def derive_kek(passphrase: str, salt: bytes, params: KdfParams | None = None) -> bytes:
    """Deriva a KEK a partir da passphrase. Nunca persiste o resultado."""
    p = params or KdfParams()
    if len(salt) < 16:
        raise ValueError("salt deve ter ao menos 16 bytes")
    return hash_secret_raw(
        secret=passphrase.encode("utf-8"),
        salt=salt,
        time_cost=p.time_cost,
        memory_cost=p.memory_kib,
        parallelism=p.parallelism,
        hash_len=KEY_LEN,
        type=Type.ID,
    )
