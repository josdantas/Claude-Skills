"""Spike S1 — a cifra por registro inviabiliza a busca vetorial?

Critério (plano §13): 10k registros, p95 do recall completo.
    p95 > 1,5 s  → plano B (índice inteiro em volume SQLCipher).

Três braços:
  A  baseline   — corpo em claro no índice, sem cripto
  B  envelope   — vetor em claro no índice (ANN precisa dele), corpo cifrado
                  por registro; decifra apenas o top-k recuperado
  C  hardened   — vetores também cifrados em repouso: mede o custo de decifrar
                  o shard inteiro para a memória no início da sessão

Os vetores são sintéticos: S1 mede custo de sistema (I/O, ANN, AES-GCM), que
independe de os embeddings carregarem semântica real. A qualidade semântica é
a pergunta do S2, que exige pesos de modelo.
"""

from __future__ import annotations

import os
import shutil
import statistics
import sys
import time
from pathlib import Path

import lancedb
import numpy as np
import pyarrow as pa

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from arca.crypto.envelope import Envelope, open_, seal  # noqa: E402

N_RECORDS = 10_000
DIM = 768
TOP_K = 30
N_QUERIES = 200
BODY_BYTES = 600
DB = Path("/tmp/arca-s1")


def make_corpus(rng: np.random.Generator) -> tuple[np.ndarray, list[bytes], list[str]]:
    vectors = rng.standard_normal((N_RECORDS, DIM), dtype=np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    bodies = [os.urandom(BODY_BYTES // 2).hex().encode() for _ in range(N_RECORDS)]
    ids = [f"mem_{i:06d}" for i in range(N_RECORDS)]
    return vectors, bodies, ids


def pct(xs: list[float], p: float) -> float:
    return statistics.quantiles(xs, n=1000)[int(p * 1000) - 1]


def report(name: str, lat: list[float]) -> None:
    print(
        f"  {name:<28} mediana {statistics.median(lat)*1000:7.1f} ms   "
        f"p95 {pct(lat, 0.95)*1000:7.1f} ms   p99 {pct(lat, 0.99)*1000:7.1f} ms"
    )


def main() -> None:
    if DB.exists():
        shutil.rmtree(DB)
    rng = np.random.default_rng(42)
    kek = os.urandom(32)

    print(f"S1 — {N_RECORDS} registros, dim {DIM}, top-k {TOP_K}, {N_QUERIES} consultas\n")
    vectors, bodies, ids = make_corpus(rng)

    # ---- ingestão ----------------------------------------------------------
    t0 = time.perf_counter()
    sealed = [seal(kek, i, b).to_bytes() for i, b in zip(ids, bodies)]
    t_seal = time.perf_counter() - t0
    print(f"  cifra de {N_RECORDS} registros: {t_seal:.2f} s "
          f"({t_seal/N_RECORDS*1e6:.0f} µs/registro)\n")

    db = lancedb.connect(str(DB))
    schema_a = pa.schema([("vector", pa.list_(pa.float32(), DIM)),
                          ("id", pa.string()), ("body", pa.binary())])
    tbl_a = db.create_table("plain", schema=schema_a)
    tbl_a.add([{"vector": v, "id": i, "body": b}
               for v, i, b in zip(vectors, ids, bodies)])

    tbl_b = db.create_table("sealed", schema=schema_a)
    tbl_b.add([{"vector": v, "id": i, "body": s}
               for v, i, s in zip(vectors, ids, sealed)])

    queries = rng.standard_normal((N_QUERIES, DIM), dtype=np.float32)
    queries /= np.linalg.norm(queries, axis=1, keepdims=True)

    # ---- braço A: baseline -------------------------------------------------
    lat_a: list[float] = []
    for q in queries:
        t = time.perf_counter()
        rows = tbl_a.search(q).limit(TOP_K).to_list()
        _ = [r["body"] for r in rows]
        lat_a.append(time.perf_counter() - t)

    # ---- braço B: envelope por registro ------------------------------------
    lat_b: list[float] = []
    dec_only: list[float] = []
    for q in queries:
        t = time.perf_counter()
        rows = tbl_b.search(q).limit(TOP_K).to_list()
        td = time.perf_counter()
        for r in rows:
            open_(kek, r["id"], Envelope.from_bytes(r["body"]))
        dec_only.append(time.perf_counter() - td)
        lat_b.append(time.perf_counter() - t)

    print("Braços de recall:")
    report("A baseline (claro)", lat_a)
    report("B envelope por registro", lat_b)
    report("   └ só o decrypt do top-k", dec_only)

    # ---- braço C: shard cifrado inteiro ------------------------------------
    shard = vectors.tobytes()
    t = time.perf_counter()
    shard_env = seal(kek, "shard_2026_08", shard)
    t_seal_shard = time.perf_counter() - t

    t = time.perf_counter()
    raw = open_(kek, "shard_2026_08", shard_env)
    t_open_shard = time.perf_counter() - t
    restored = np.frombuffer(raw, dtype=np.float32).reshape(N_RECORDS, DIM)
    assert np.array_equal(restored, vectors)

    mb = len(shard) / 1e6
    print(f"\nBraço C (perfil hardened) — shard de vetores {mb:.1f} MB:")
    print(f"  cifrar shard  {t_seal_shard*1000:7.1f} ms")
    print(f"  decifrar shard {t_open_shard*1000:6.1f} ms  "
          f"({mb/t_open_shard:.0f} MB/s) — custo único por sessão")

    # ---- veredito ----------------------------------------------------------
    p95_b = pct(lat_b, 0.95)
    overhead = (statistics.median(lat_b) - statistics.median(lat_a)) * 1000
    print(f"\nVEREDITO S1: p95 do braço B = {p95_b*1000:.1f} ms "
          f"(limiar do spike: 1500 ms; meta do produto: 800 ms)")
    print(f"  sobrecarga mediana da cifra por registro: {overhead:+.1f} ms")
    print(f"  → {'PASSA' if p95_b < 1.5 else 'FALHA — acionar plano B'}")
    shutil.rmtree(DB, ignore_errors=True)


if __name__ == "__main__":
    main()
