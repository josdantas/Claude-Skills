"""Frase de recuperação BIP39 (24 palavras) e divisão 2-de-3 entre guardiões.

A entropia de 32 bytes é o objeto canônico: a frase é a forma legível dela, e
as partes de Shamir são a forma distribuível. Reconstruir 2 das 3 partes
devolve a mesma entropia e, portanto, as mesmas 24 palavras.
"""

from __future__ import annotations

from dataclasses import dataclass

from mnemonic import Mnemonic

from arca.crypto import shamir

ENTROPY_BYTES = 32  # 256 bits → 24 palavras
_MNEMO = Mnemonic("english")


def generate() -> tuple[str, bytes]:
    """Sorteia entropia nova. Devolve (frase de 24 palavras, entropia)."""
    import os

    entropy = os.urandom(ENTROPY_BYTES)
    return _MNEMO.to_mnemonic(entropy), entropy


def to_entropy(phrase: str) -> bytes:
    """Valida o checksum BIP39 e devolve a entropia."""
    words = phrase.strip().split()
    if len(words) != 24:
        raise ValueError(f"esperadas 24 palavras, recebidas {len(words)}")
    normalized = " ".join(words).lower()
    if not _MNEMO.check(normalized):
        raise ValueError("frase de recuperação inválida (checksum BIP39)")
    return bytes(_MNEMO.to_entropy(normalized))


def to_phrase(entropy: bytes) -> str:
    if len(entropy) != ENTROPY_BYTES:
        raise ValueError("entropia deve ter 32 bytes")
    return _MNEMO.to_mnemonic(entropy)


@dataclass(frozen=True, slots=True)
class Guardian:
    """Uma parte entregue a um guardião. `index` distingue as partes."""

    index: int
    share: bytes

    def encode(self) -> str:
        """Forma transportável: `arca1-<idx>-<hex>`."""
        return f"arca1-{self.index}-{self.share.hex()}"

    @classmethod
    def decode(cls, text: str) -> "Guardian":
        prefix, idx, payload = text.strip().split("-", 2)
        if prefix != "arca1":
            raise ValueError("prefixo desconhecido na parte de recuperação")
        return cls(int(idx), bytes.fromhex(payload))


def split_guardians(entropy: bytes, threshold: int = 2, count: int = 3) -> list[Guardian]:
    if len(entropy) != ENTROPY_BYTES:
        raise ValueError("entropia deve ter 32 bytes")
    return [Guardian(i, s) for i, s in shamir.split(entropy, threshold, count)]


def combine_guardians(guardians: list[Guardian]) -> bytes:
    return shamir.combine([(g.index, g.share) for g in guardians])
