"""O vault: fonte da verdade em Markdown, versionada em git.

Layout em disco:

    vault/
      <scope>/<YYYY-MM>/<mem_id>.md     ← shard = scope + mês (ver S3)
      .git/

Cada arquivo tem front-matter YAML em claro (metadados, nunca conteúdo) e o
corpo. No perfil `standard` o corpo fica legível; no `hardened` ele é o
envelope em base64. Os metadados permanecem em claro nos dois porque é deles
que o rebuild do índice depende, e eles não carregam conteúdo sensível.

Escrita atômica: grava em `.tmp`, `fsync`, `rename`, `fsync` do diretório. Uma
queda de energia deixa o arquivo antigo ou o novo, nunca metade dos dois.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Literal

import yaml
from ulid import ULID

from arca.crypto.envelope import Envelope, open_, seal
from arca.vault.record import MemoryRecord, SourceClass, rule_for

Profile = Literal["standard", "hardened"]
SEPARATOR = "---\n"


def new_id() -> str:
    return f"mem_{ULID()}"


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@dataclass(frozen=True, slots=True)
class Shard:
    scope: str
    month: str  # YYYY-MM

    @property
    def rel(self) -> Path:
        return Path(self.scope) / self.month

    @classmethod
    def of(cls, record: MemoryRecord) -> "Shard":
        return cls(record.scope, record.created_at.strftime("%Y-%m"))


class Vault:
    def __init__(self, root: Path, mk: bytes, profile: Profile = "standard") -> None:
        self.root = root
        self.profile: Profile = profile
        self._mk = mk
        self.root.mkdir(parents=True, exist_ok=True)

    # -- serialização --------------------------------------------------------

    def _frontmatter(self, r: MemoryRecord) -> str:
        meta = r.model_dump(mode="json", exclude={"body"})
        return SEPARATOR + yaml.safe_dump(meta, sort_keys=True, allow_unicode=True) + SEPARATOR

    def _encode_body(self, r: MemoryRecord) -> str:
        if self.profile == "standard":
            return r.body
        env = seal(self._mk, r.id, r.body.encode("utf-8"))
        return base64.b64encode(env.to_bytes()).decode()

    def _decode_body(self, record_id: str, raw: str) -> str:
        if self.profile == "standard":
            return raw
        return open_(self._mk, record_id, Envelope.from_bytes(base64.b64decode(raw))).decode()

    # -- operações -----------------------------------------------------------

    def path_of(self, record: MemoryRecord) -> Path:
        return self.root / Shard.of(record).rel / f"{record.id}.md"

    def write(self, record: MemoryRecord) -> Path:
        path = self.path_of(record)
        payload = self._frontmatter(record) + "\n" + self._encode_body(record)
        _atomic_write(path, payload.encode("utf-8"))
        return path

    def read(self, path: Path) -> MemoryRecord:
        text = path.read_text(encoding="utf-8")
        if not text.startswith(SEPARATOR):
            raise ValueError(f"{path}: front-matter ausente")
        _, meta_block, body_block = text.split(SEPARATOR, 2)
        meta = yaml.safe_load(meta_block)
        body = self._decode_body(meta["id"], body_block.lstrip("\n"))
        return MemoryRecord.model_validate(meta | {"body": body})

    def iter_records(self, shard: Shard | None = None) -> Iterator[MemoryRecord]:
        base = self.root / shard.rel if shard else self.root
        if not base.exists():
            return
        for path in sorted(base.rglob("*.md")):
            yield self.read(path)

    def delete(self, record_id: str) -> Path | None:
        """Remove o arquivo. O rebuild do índice é responsabilidade do Forget Engine."""
        for path in self.root.rglob(f"{record_id}.md"):
            path.unlink()
            return path
        return None

    def shards(self) -> list[Shard]:
        out = []
        for scope_dir in sorted(p for p in self.root.iterdir() if p.is_dir() and p.name != ".git"):
            for month_dir in sorted(p for p in scope_dir.iterdir() if p.is_dir()):
                out.append(Shard(scope_dir.name, month_dir.name))
        return out


def make_record(
    body: str,
    source_class: SourceClass,
    source_ref: str,
    *,
    scope: str = "user",
    sensitivity: str = "normal",
    entities: list[str] | None = None,
    confidence: float = 0.9,
) -> MemoryRecord:
    """Cria um registro aplicando a política de confiança.

    `status` e `ttl` vêm da política, nunca do chamador — é o que impede um
    chamador de se autodeclarar confiável.
    """
    rule = rule_for(source_class)
    now = datetime.now(timezone.utc)
    return MemoryRecord(
        id=new_id(),
        created_at=now,
        valid_from=now.date(),
        scope=scope,  # type: ignore[arg-type]
        source_class=source_class,
        source_ref=source_ref,
        confidence=confidence,
        sensitivity=sensitivity,  # type: ignore[arg-type]
        status=rule.initial_status,
        ttl=rule.default_ttl,
        entities=entities or [],
        body=body,
    )
