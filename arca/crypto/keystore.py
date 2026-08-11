"""Material de chaves do cofre.

Modelo: existe uma **master key** (MK) aleatória de 32 bytes que embrulha as DEK
de todos os registros. A MK nunca é derivada de nada — ela é sorteada uma vez e
guardada apenas em forma embrulhada, por dois caminhos independentes:

    MK  ──cifrada por──>  KEK  (Argon2id sobre a passphrase)   → uso diário
        ──cifrada por──>  RK   (BIP39 → HKDF)                  → recuperação

Trocar a passphrase reembrulha a MK; não reescreve nenhum registro. Perder a
passphrase não perde o cofre, desde que exista a frase de recuperação.

**Invariante central:** o arquivo em disco contém apenas material embrulhado,
salt e verificador. Nenhuma chave em claro toca o disco, em nenhum caminho de
código. Há um teste de propriedade dedicado a isso (`tests/test_keystore.py`).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from arca.crypto.kdf import KdfParams, derive_kek

MK_LEN = 32
SALT_LEN = 16
NONCE_LEN = 12
VERIFIER_PLAINTEXT = b"arca-keystore-v1"


class UnlockError(Exception):
    """Passphrase ou frase de recuperação incorreta, ou arquivo adulterado."""


def _wrap(key: bytes, mk: bytes, aad: bytes) -> str:
    nonce = os.urandom(NONCE_LEN)
    return (nonce + AESGCM(key).encrypt(nonce, mk, aad)).hex()


def _unwrap(key: bytes, blob: str, aad: bytes) -> bytes:
    raw = bytes.fromhex(blob)
    try:
        return AESGCM(key).decrypt(raw[:NONCE_LEN], raw[NONCE_LEN:], aad)
    except Exception as exc:  # InvalidTag e afins
        raise UnlockError("não foi possível desembrulhar a master key") from exc


def recovery_key_from_entropy(entropy: bytes) -> bytes:
    """Deriva a RK a partir da entropia da frase de recuperação (32 bytes)."""
    return HKDF(
        algorithm=hashes.SHA256(), length=MK_LEN, salt=None, info=b"arca/recovery/v1"
    ).derive(entropy)


@dataclass(frozen=True, slots=True)
class Keystore:
    """Estado persistido do material de chaves. Só contém coisa embrulhada."""

    version: int
    salt: bytes
    kdf: KdfParams
    wrapped_by_passphrase: str
    wrapped_by_recovery: str
    verifier: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "version": self.version,
                "salt": self.salt.hex(),
                "kdf": {
                    "version": self.kdf.version,
                    "memory_kib": self.kdf.memory_kib,
                    "time_cost": self.kdf.time_cost,
                    "parallelism": self.kdf.parallelism,
                },
                "wrapped_by_passphrase": self.wrapped_by_passphrase,
                "wrapped_by_recovery": self.wrapped_by_recovery,
                "verifier": self.verifier,
            },
            indent=2,
        )

    @classmethod
    def from_json(cls, text: str) -> "Keystore":
        d = json.loads(text)
        k = d["kdf"]
        return cls(
            version=d["version"],
            salt=bytes.fromhex(d["salt"]),
            kdf=KdfParams(k["version"], k["memory_kib"], k["time_cost"], k["parallelism"]),
            wrapped_by_passphrase=d["wrapped_by_passphrase"],
            wrapped_by_recovery=d["wrapped_by_recovery"],
            verifier=d["verifier"],
        )

    def save(self, path: Path) -> None:
        _atomic_write(path, self.to_json().encode())

    @classmethod
    def load(cls, path: Path) -> "Keystore":
        return cls.from_json(path.read_text())


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    dir_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def create(
    passphrase: str, recovery_entropy: bytes, params: KdfParams | None = None
) -> tuple[Keystore, bytes]:
    """Cria um cofre novo. Devolve (keystore, master_key).

    `params` existe para os testes usarem um custo menor; em produção o default
    são os parâmetros de contrato. Os parâmetros usados ficam gravados no
    keystore, então um cofre criado com custo baixo não é destrancado com custo
    alto por engano — ele carrega sua própria configuração.
    """
    if len(recovery_entropy) != MK_LEN:
        raise ValueError("entropia de recuperação deve ter 32 bytes")
    mk = os.urandom(MK_LEN)
    salt = os.urandom(SALT_LEN)
    params = params or KdfParams()
    kek = derive_kek(passphrase, salt, params)
    rk = recovery_key_from_entropy(recovery_entropy)

    ks = Keystore(
        version=1,
        salt=salt,
        kdf=params,
        wrapped_by_passphrase=_wrap(kek, mk, b"passphrase"),
        wrapped_by_recovery=_wrap(rk, mk, b"recovery"),
        verifier=_wrap(mk, VERIFIER_PLAINTEXT, b"verifier"),
    )
    return ks, mk


def unlock(ks: Keystore, passphrase: str) -> bytes:
    kek = derive_kek(passphrase, ks.salt, ks.kdf)
    mk = _unwrap(kek, ks.wrapped_by_passphrase, b"passphrase")
    _check(ks, mk)
    return mk


def unlock_with_recovery(ks: Keystore, recovery_entropy: bytes) -> bytes:
    rk = recovery_key_from_entropy(recovery_entropy)
    mk = _unwrap(rk, ks.wrapped_by_recovery, b"recovery")
    _check(ks, mk)
    return mk


def change_passphrase(
    ks: Keystore, mk: bytes, new_passphrase: str, params: KdfParams | None = None
) -> Keystore:
    """Reembrulha a MK. Nenhum registro é reescrito."""
    salt = os.urandom(SALT_LEN)
    params = params or KdfParams()
    kek = derive_kek(new_passphrase, salt, params)
    return Keystore(
        version=ks.version,
        salt=salt,
        kdf=params,
        wrapped_by_passphrase=_wrap(kek, mk, b"passphrase"),
        wrapped_by_recovery=ks.wrapped_by_recovery,
        verifier=ks.verifier,
    )


def _check(ks: Keystore, mk: bytes) -> None:
    if _unwrap(mk, ks.verifier, b"verifier") != VERIFIER_PLAINTEXT:
        raise UnlockError("verificador não confere")


# --------------------------------------------------------------------------
# Onde a MK vive enquanto o cofre está aberto
# --------------------------------------------------------------------------

Backend = Literal["os_keychain", "session"]


class SessionKeyHolder:
    """Guarda a MK apenas em memória, pelo tempo da sessão.

    É o fallback quando não há keychain do SO — o caso deste container Linux
    headless. Secure Enclave (macOS) e TPM 2.0 (Linux/Windows) entram como
    backends adicionais e ainda **não estão implementados nem testados**; o
    plano os prevê para a Fase 0 em hardware real, não em CI.
    """

    __slots__ = ("_mk",)

    def __init__(self) -> None:
        self._mk: bytearray | None = None

    def set(self, mk: bytes) -> None:
        self._mk = bytearray(mk)

    def get(self) -> bytes:
        if self._mk is None:
            raise UnlockError("cofre trancado")
        return bytes(self._mk)

    def lock(self) -> None:
        """Zera o buffer antes de soltar a referência.

        Melhor esforço: o CPython pode ter feito cópias que não alcançamos.
        Um backend em enclave é a resposta correta; isto reduz a janela.
        """
        if self._mk is not None:
            for i in range(len(self._mk)):
                self._mk[i] = 0
            self._mk = None
