"""Serviço de memória — a lógica que o servidor MCP expõe.

Fica separado da camada MCP de propósito: assim as regras de segurança são
testáveis sem subir um transporte, e trocar de protocolo não toca em nada disto.

Escopo da Fase 0: escrever, recuperar e apagar. A recuperação aqui é uma
varredura léxica ingênua — o índice híbrido (vetorial + BM25 + grafo) é a Fase 1.
Está assim de propósito, e o retorno avisa (`retrieval: "naive-lexical"`) para
que ninguém confunda o esqueleto com o produto.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arca.audit.chain import AuditLog, audit_key
from arca.vault.git import VaultGit
from arca.vault.record import MemoryRecord, SourceClass
from arca.vault.store import Profile, Vault, make_record

# De onde veio a chamada → qual classe de origem. É o canal que decide, nunca
# o conteúdo nem um parâmetro que o chamador possa forjar (plano §6, estágio 2).
CHANNEL_TO_CLASS: dict[str, SourceClass] = {
    "cli": SourceClass.USER_DIRECT,
    "mcp:user": SourceClass.USER_DIRECT,
    "mcp:agent": SourceClass.AGENT_INFERENCE,
    "mcp:tool": SourceClass.TOOL_OUTPUT,
    "mcp:web": SourceClass.WEB_CONTENT,
    "mcp:external": SourceClass.THIRD_PARTY_AGENT,
}

# Ordem de confiança: um canal só pode rebaixar a própria classe, nunca elevá-la.
_RANK = {
    SourceClass.USER_DIRECT: 5,
    SourceClass.USER_DOCUMENT: 4,
    SourceClass.AGENT_INFERENCE: 3,
    SourceClass.TOOL_OUTPUT: 2,
    SourceClass.WEB_CONTENT: 1,
    SourceClass.THIRD_PARTY_AGENT: 0,
}


def resolve_source_class(channel: str, declared: str | None) -> SourceClass:
    """Resolve a classe efetiva. Uma declaração que tenta subir é ignorada."""
    actual = CHANNEL_TO_CLASS.get(channel, SourceClass.THIRD_PARTY_AGENT)
    if declared is None:
        return actual
    try:
        wanted = SourceClass(declared)
    except ValueError:
        return actual
    return wanted if _RANK[wanted] < _RANK[actual] else actual


@dataclass(frozen=True, slots=True)
class RecallHit:
    record: MemoryRecord
    score: float

    def as_prompt_block(self) -> str:
        return self.record.render_for_prompt()


class MemoryService:
    def __init__(self, home: Path, mk: bytes, profile: Profile = "standard") -> None:
        self.home = home
        self.vault = Vault(home / "vault", mk, profile=profile)
        self.git = VaultGit(home / "vault")
        self.audit = AuditLog(home / "audit", audit_key(mk))

    # -- escrita -------------------------------------------------------------

    def remember(
        self,
        body: str,
        *,
        channel: str,
        actor: str,
        declared_source_class: str | None = None,
        scope: str = "user",
        sensitivity: str = "normal",
        entities: list[str] | None = None,
    ) -> MemoryRecord:
        source_class = resolve_source_class(channel, declared_source_class)
        record = make_record(
            body,
            source_class,
            source_ref=f"{channel}://{actor}",
            scope=scope,
            sensitivity=sensitivity,
            entities=entities,
        )
        self.vault.write(record)
        self.git.commit_all(f"remember {record.id} [{source_class.value}]")
        self.audit.append(
            "write",
            actor,
            record_id=record.id,
            source_class=source_class.value,
            decision=record.status,
        )
        return record

    # -- leitura -------------------------------------------------------------

    def recall(self, query: str, *, actor: str, limit: int = 10) -> dict[str, Any]:
        terms = [t for t in re.findall(r"\w+", query.lower()) if len(t) > 2]
        now = datetime.now(timezone.utc)

        hits: list[RecallHit] = []
        for record in self.vault.iter_records():
            if record.status == "revoked" or record.is_expired(now):
                continue
            body = record.body.lower()
            overlap = sum(1 for t in terms if t in body)
            if not overlap:
                continue
            score = (overlap / max(len(terms), 1)) * record.trust_weight
            hits.append(RecallHit(record, score))

        hits.sort(key=lambda h: h.score, reverse=True)
        hits = hits[:limit]

        self.audit.append("recall", actor, decision=f"{len(hits)} hits")
        return {
            "retrieval": "naive-lexical",  # Fase 0. Índice híbrido = Fase 1.
            "hits": [
                {"id": h.record.id, "score": round(h.score, 4), "block": h.as_prompt_block()}
                for h in hits
            ],
        }

    # -- deleção -------------------------------------------------------------

    def forget(self, record_id: str, *, actor: str, dry_run: bool = True) -> dict[str, Any]:
        """`dry_run=True` é o default. Ver plano §10."""
        target = next(
            (r for r in self.vault.iter_records() if r.id == record_id), None
        )
        if target is None:
            return {"found": False, "deleted": False}

        if dry_run:
            self.audit.append("forget_preview", actor, record_id=record_id)
            return {"found": True, "deleted": False, "dry_run": True}

        self.vault.delete(record_id)
        self.git.commit_all(f"forget {record_id}")
        self.audit.append("forget", actor, record_id=record_id, decision="deleted")
        # O rebuild do índice e o recibo assinado entram na Fase 3, junto com a
        # reescrita de histórico do git. Enquanto isso não existe, esta deleção
        # ainda é recuperável pelo histórico — e o retorno diz isso.
        return {
            "found": True,
            "deleted": True,
            "irreversible": False,
            "note": "Fase 0: histórico git ainda retém o conteúdo. Forget Engine = Fase 3.",
        }
