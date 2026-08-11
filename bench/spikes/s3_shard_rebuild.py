"""Spike S3 — o rebuild de shard é rápido o bastante para ser o padrão da deleção?

Critério (plano §13): shard de 5k registros.
    rebuild > 10 s  → reduzir o tamanho do shard.

O caminho medido é o real: o vault em disco é a fonte da verdade, o índice é
descartado por completo e refeito a partir dos arquivos. Nada de tombstone,
nada de soft-delete — é isso que fecha a lacuna dos *Ghost Vectors*.

Decisão de arquitetura que este spike testa: guardar o embedding **dentro do
envelope do registro**. Sem isso, todo rebuild exigiria re-embedar o shard
inteiro, e a deleção deixaria de ser barata.
"""

from __future__ import annotations

import base64
import os
import shutil
import sys
import time
from pathlib import Path

import lancedb
import numpy as np
import pyarrow as pa

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from arca.crypto.envelope import Envelope, open_, seal  # noqa: E402

N_SHARD = 5_000
DIM = 768
VAULT = Path("/tmp/arca-s3/vault")
INDEX = Path("/tmp/arca-s3/index")

FRONTMATTER = """---
id: {id}
created_at: 2026-08-10T12:00:00Z
valid_from: 2026-08-10
scope: user
source_class: user_direct
source_ref: "spike://s3"
confidence: 0.95
sensitivity: normal
status: trusted
---
"""


def build_vault(rng: np.random.Generator, kek: bytes) -> float:
    if VAULT.exists():
        shutil.rmtree(VAULT)
    VAULT.mkdir(parents=True)
    vectors = rng.standard_normal((N_SHARD, DIM), dtype=np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)

    t = time.perf_counter()
    for i in range(N_SHARD):
        rid = f"mem_{i:06d}"
        body = f"Memória de teste {i}. " + os.urandom(280).hex()
        # payload = corpo + embedding, ambos dentro do mesmo envelope
        blob = body.encode() + b"\x00EMB\x00" + vectors[i].tobytes()
        env = seal(kek, rid, blob)
        (VAULT / f"{rid}.md").write_bytes(
            FRONTMATTER.format(id=rid).encode()
            + base64.b64encode(env.to_bytes())
        )
    return time.perf_counter() - t


def rebuild(kek: bytes) -> tuple[float, float, float, int]:
    """Descarta o índice e o refaz lendo o vault. Retorna (leitura, insert, total, n)."""
    if INDEX.exists():
        shutil.rmtree(INDEX)

    t_total = time.perf_counter()

    t = time.perf_counter()
    rows = []
    for path in sorted(VAULT.glob("*.md")):
        raw = path.read_bytes()
        rid = path.stem
        env = Envelope.from_bytes(base64.b64decode(raw.split(b"---\n", 2)[2]))
        blob = open_(kek, rid, env)
        body, emb = blob.split(b"\x00EMB\x00", 1)
        rows.append({
            "vector": np.frombuffer(emb, dtype=np.float32),
            "id": rid,
            "body": body,
        })
    t_read = time.perf_counter() - t

    t = time.perf_counter()
    db = lancedb.connect(str(INDEX))
    schema = pa.schema([("vector", pa.list_(pa.float32(), DIM)),
                        ("id", pa.string()), ("body", pa.binary())])
    tbl = db.create_table("shard", schema=schema)
    tbl.add(rows)
    t_insert = time.perf_counter() - t

    return t_read, t_insert, time.perf_counter() - t_total, len(rows)


def main() -> None:
    rng = np.random.default_rng(7)
    kek = os.urandom(32)

    print(f"S3 — shard de {N_SHARD} registros, dim {DIM}\n")
    t_build = build_vault(rng, kek)
    size_mb = sum(p.stat().st_size for p in VAULT.glob("*.md")) / 1e6
    print(f"  vault criado: {t_build:.2f} s, {size_mb:.1f} MB em {N_SHARD} arquivos\n")

    # rebuild completo, três repetições
    times = []
    for run in range(3):
        t_read, t_insert, t_total, n = rebuild(kek)
        times.append(t_total)
        print(f"  rebuild #{run+1}: leitura+decrypt {t_read:.2f} s   "
              f"insert+índice {t_insert:.2f} s   total {t_total:.2f} s   ({n} registros)")

    # cenário real de deleção: apaga 100 registros e refaz o shard
    victims = sorted(VAULT.glob("*.md"))[:100]
    t = time.perf_counter()
    for p in victims:
        p.unlink()
    _, _, t_after, n_after = rebuild(kek)
    t_forget = time.perf_counter() - t
    print(f"\n  forget de 100 registros + rebuild: {t_forget:.2f} s "
          f"({n_after} registros restantes)")

    best = min(times)
    print(f"\nVEREDITO S3: rebuild de {N_SHARD} registros = {best:.2f} s "
          f"(limiar do spike: 10 s)")
    print(f"  → {'PASSA' if best < 10 else 'FALHA — reduzir tamanho do shard'}")
    print(f"  extrapolação: shard viável até ~{int(N_SHARD * 10 / best):,} registros "
          f"antes de estourar 10 s".replace(",", "."))
    shutil.rmtree("/tmp/arca-s3", ignore_errors=True)


if __name__ == "__main__":
    main()
