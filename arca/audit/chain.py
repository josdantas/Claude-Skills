"""Log de auditoria append-only com cadeia de hash.

Cada entrada carrega o hash da anterior e um HMAC sob uma chave derivada da MK.
Adulterar uma entrada quebra a verificação dela e de todas as seguintes.

**O log nunca contém corpo de memória** — só metadados, IDs e decisões. Um log
que vaza conteúdo é um segundo banco de dados sensível, e essa regra tem teste
próprio (`tests/test_audit.py::test_no_body_leaks_into_log`).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

GENESIS = "sha256:" + "0" * 64
_FORBIDDEN_FIELDS = {"body", "plaintext", "content", "text"}


def audit_key(mk: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None, info=b"arca/audit/v1"
    ).derive(mk)


@dataclass(frozen=True, slots=True)
class Entry:
    seq: int
    ts: str
    op: str
    actor: str
    prev: str
    record_id: str | None = None
    source_class: str | None = None
    decision: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def canonical(self) -> bytes:
        """Serialização determinística — é sobre isto que o HMAC é calculado."""
        payload = {
            "seq": self.seq,
            "ts": self.ts,
            "op": self.op,
            "actor": self.actor,
            "prev": self.prev,
            "record_id": self.record_id,
            "source_class": self.source_class,
            "decision": self.decision,
            "extra": self.extra,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()

    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(self.canonical()).hexdigest()


class AuditLog:
    """Um arquivo JSONL por dia, em `root/YYYY-MM-DD.jsonl`."""

    def __init__(self, root: Path, key: bytes) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._key = key

    # -- escrita ------------------------------------------------------------

    def append(
        self,
        op: str,
        actor: str,
        *,
        record_id: str | None = None,
        source_class: str | None = None,
        decision: str | None = None,
        **extra: Any,
    ) -> Entry:
        bad = _FORBIDDEN_FIELDS & set(extra)
        if bad:
            raise ValueError(f"o audit log não aceita conteúdo de memória: {sorted(bad)}")

        last = self.last()
        entry = Entry(
            seq=(last.seq + 1) if last else 1,
            ts=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            op=op,
            actor=actor,
            prev=last.digest() if last else GENESIS,
            record_id=record_id,
            source_class=source_class,
            decision=decision,
            extra=extra,
        )
        line = json.dumps(
            json.loads(entry.canonical()) | {"hmac": self._hmac(entry)},
            sort_keys=True,
            separators=(",", ":"),
        )
        path = self.root / f"{datetime.now(timezone.utc).date().isoformat()}.jsonl"
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        return entry

    def _hmac(self, entry: Entry) -> str:
        return "sha256:" + hmac.new(self._key, entry.canonical(), hashlib.sha256).hexdigest()

    # -- leitura ------------------------------------------------------------

    def _files(self) -> list[Path]:
        return sorted(self.root.glob("*.jsonl"))

    def entries(self) -> Iterator[tuple[Entry, str]]:
        for path in self._files():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                d = json.loads(line)
                mac = d.pop("hmac")
                yield Entry(**d), mac

    def last(self) -> Entry | None:
        tail: Entry | None = None
        for entry, _ in self.entries():
            tail = entry
        return tail

    # -- verificação --------------------------------------------------------

    def verify(self) -> tuple[bool, str | None]:
        """Percorre a cadeia inteira. Devolve (íntegra, primeiro problema)."""
        expected_prev = GENESIS
        expected_seq = 1
        for entry, mac in self.entries():
            if entry.seq != expected_seq:
                return False, f"seq {entry.seq}: esperado {expected_seq}"
            if entry.prev != expected_prev:
                return False, f"seq {entry.seq}: elo anterior não confere"
            if not hmac.compare_digest(mac, self._hmac(entry)):
                return False, f"seq {entry.seq}: HMAC inválido"
            expected_prev = entry.digest()
            expected_seq += 1
        return True, None

    # -- âncora diária ------------------------------------------------------

    def anchor(self, day: date | None = None) -> str | None:
        """Grava o hash raiz do dia em `anchors/YYYY-MM-DD.txt`."""
        day = day or datetime.now(timezone.utc).date()
        path = self.root / f"{day.isoformat()}.jsonl"
        if not path.exists():
            return None
        root_hash = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        out = self.root / "anchors"
        out.mkdir(exist_ok=True)
        (out / f"{day.isoformat()}.txt").write_text(root_hash + "\n")
        return root_hash
