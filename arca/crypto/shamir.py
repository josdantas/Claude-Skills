"""Shamir Secret Sharing sobre GF(2^8), para a recuperação 2-de-3.

Implementação byte a byte com o polinômio irredutível do AES (0x11b). Segredos
de tamanho fixo; nenhum padding, nenhum comprimento variável — o único uso é
dividir 32 bytes de entropia de recuperação entre guardiões.

As tabelas de log/antilog tornam a multiplicação uma soma de índices. Isso é
rápido, mas *não* é tempo constante. Aceitável aqui: a operação roda uma vez,
na criação ou na recuperação do cofre, com o usuário presente — não é um
oráculo que um atacante possa consultar repetidamente.
"""

from __future__ import annotations

import os

_EXP = [0] * 512
_LOG = [0] * 256


def _init_tables() -> None:
    x = 1
    for i in range(255):
        _EXP[i] = x
        _LOG[x] = i
        x ^= (x << 1) ^ (0x11B if x & 0x80 else 0)
        x &= 0xFF
    for i in range(255, 512):
        _EXP[i] = _EXP[i - 255]


_init_tables()


def _mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def _div(a: int, b: int) -> int:
    if b == 0:
        raise ZeroDivisionError("divisão por zero em GF(256)")
    if a == 0:
        return 0
    return _EXP[(_LOG[a] - _LOG[b]) % 255]


def split(secret: bytes, threshold: int, shares: int) -> list[tuple[int, bytes]]:
    """Divide `secret` em `shares` partes, das quais `threshold` reconstroem."""
    if not 2 <= threshold <= shares <= 255:
        raise ValueError("exige 2 <= threshold <= shares <= 255")
    if not secret:
        raise ValueError("segredo vazio")

    out: list[bytearray] = [bytearray() for _ in range(shares)]
    for byte in secret:
        # coeficientes aleatórios; a_0 = byte do segredo
        coeffs = [byte] + list(os.urandom(threshold - 1))
        for idx in range(shares):
            x = idx + 1  # x=0 é o segredo, nunca distribuído
            y = 0
            for power, coeff in enumerate(coeffs):
                term = coeff
                for _ in range(power):
                    term = _mul(term, x)
                y ^= term
            out[idx].append(y)
    return [(i + 1, bytes(s)) for i, s in enumerate(out)]


def combine(parts: list[tuple[int, bytes]]) -> bytes:
    """Reconstrói o segredo por interpolação de Lagrange em x=0."""
    if len(parts) < 2:
        raise ValueError("são necessárias ao menos 2 partes")
    lengths = {len(p) for _, p in parts}
    if len(lengths) != 1:
        raise ValueError("partes de tamanhos diferentes")
    xs = [x for x, _ in parts]
    if len(set(xs)) != len(xs):
        raise ValueError("partes com índices repetidos")

    length = lengths.pop()
    secret = bytearray(length)
    for pos in range(length):
        acc = 0
        for i, (xi, yi) in enumerate(parts):
            num, den = 1, 1
            for j, (xj, _) in enumerate(parts):
                if i == j:
                    continue
                num = _mul(num, xj)
                den = _mul(den, xi ^ xj)
            acc ^= _mul(yi[pos], _div(num, den))
        secret[pos] = acc
    return bytes(secret)
