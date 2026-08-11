"""Critério de aceite da Fase 0: nenhuma chave em claro toca o disco."""

from __future__ import annotations

import json
import os

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from arca.crypto import keystore, recovery
from arca.crypto.kdf import KdfParams

# Custo reduzido: estes testes exercitam lógica, não o endurecimento do KDF.
# O custo real dos parâmetros de contrato é medido em bench/ (468 ms).
FAST = KdfParams(version=1, memory_kib=8 * 1024, time_cost=1, parallelism=1)


def test_roundtrip_passphrase_and_recovery():
    phrase, entropy = recovery.generate()
    ks, mk = keystore.create("senha-correta", entropy, FAST)

    assert keystore.unlock(ks, "senha-correta") == mk
    assert keystore.unlock_with_recovery(ks, recovery.to_entropy(phrase)) == mk


def test_wrong_passphrase_fails_closed():
    _, entropy = recovery.generate()
    ks, _ = keystore.create("certa", entropy, FAST)
    with pytest.raises(keystore.UnlockError):
        keystore.unlock(ks, "errada")


def test_change_passphrase_preserves_master_key_and_recovery():
    phrase, entropy = recovery.generate()
    ks, mk = keystore.create("antiga", entropy, FAST)

    ks2 = keystore.change_passphrase(ks, mk, "nova", FAST)

    assert keystore.unlock(ks2, "nova") == mk
    assert keystore.unlock_with_recovery(ks2, recovery.to_entropy(phrase)) == mk
    with pytest.raises(keystore.UnlockError):
        keystore.unlock(ks2, "antiga")


def test_tampered_keystore_is_rejected():
    _, entropy = recovery.generate()
    ks, _ = keystore.create("senha", entropy, FAST)

    raw = json.loads(ks.to_json())
    blob = bytearray(bytes.fromhex(raw["wrapped_by_passphrase"]))
    blob[-1] ^= 0x01  # um bit no ciphertext
    raw["wrapped_by_passphrase"] = blob.hex()

    with pytest.raises(keystore.UnlockError):
        keystore.unlock(keystore.Keystore.from_json(json.dumps(raw)), "senha")


# --------------------------------------------------------------------------
# CRITÉRIO DE ACEITE: nenhuma chave em claro no disco
# --------------------------------------------------------------------------


@settings(max_examples=25, deadline=None)
@given(passphrase=st.text(min_size=1, max_size=40))
def test_no_plaintext_key_material_on_disk(passphrase, tmp_path_factory):
    """Nenhum byte da MK, da KEK ou da RK aparece em nada que foi gravado."""
    tmp = tmp_path_factory.mktemp("ks")
    phrase, entropy = recovery.generate()
    ks, mk = keystore.create(passphrase, entropy, FAST)

    path = tmp / "keystore.json"
    ks.save(path)

    written = b"".join(p.read_bytes() for p in tmp.rglob("*") if p.is_file())
    rk = keystore.recovery_key_from_entropy(entropy)

    for name, secret in (("master key", mk), ("recovery key", rk), ("entropia", entropy)):
        assert secret not in written, f"{name} apareceu em claro no disco"
        assert secret.hex().encode() not in written, f"{name} apareceu em hex no disco"

    # a frase de recuperação também nunca é persistida pelo keystore
    assert phrase.encode() not in written
    # e o arquivo continua destrancável
    assert keystore.unlock(keystore.Keystore.load(path), passphrase) == mk


def test_no_temp_files_left_behind(tmp_path):
    _, entropy = recovery.generate()
    ks, _ = keystore.create("s", entropy, FAST)
    ks.save(tmp_path / "keystore.json")
    assert list(tmp_path.glob("*.tmp")) == []


def test_session_holder_zeroes_on_lock():
    holder = keystore.SessionKeyHolder()
    mk = os.urandom(32)
    holder.set(mk)
    assert holder.get() == mk
    holder.lock()
    with pytest.raises(keystore.UnlockError):
        holder.get()
