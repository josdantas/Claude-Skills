"""Servidor MCP do ARCA — camada fina sobre `MemoryService`.

Fase 0 expõe três das seis ferramentas do plano §10: `arca_remember`,
`arca_recall` e `arca_forget`. `arca_review`, `arca_timeline` e `arca_audit`
entram nas fases seguintes.

Nota de segurança: **não existe ferramenta de promoção para `trusted`**. Isso é
deliberado — promoção é ato humano, via CLI. Um agente comprometido não eleva a
própria memória.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from arca.service import MemoryService

ARCA_HOME = Path(os.environ.get("ARCA_HOME", Path.home() / ".arca"))


def build_server(service: MemoryService, name: str = "arca") -> MCPServer:
    mcp = MCPServer(name)

    @mcp.tool()
    def arca_remember(
        body: str,
        channel: str = "mcp:agent",
        scope: str = "user",
        sensitivity: str = "normal",
        entities: list[str] | None = None,
        source_class: str | None = None,
    ) -> dict[str, Any]:
        """Grava uma memória.

        `source_class` é apenas uma sugestão: o canal da chamada determina a
        classe efetiva, e uma tentativa de elevar a confiança é ignorada.
        """
        record = service.remember(
            body,
            channel=channel,
            actor="mcp",
            declared_source_class=source_class,
            scope=scope,
            sensitivity=sensitivity,
            entities=entities,
        )
        return {
            "id": record.id,
            "status": record.status,
            "source_class": record.source_class.value,
            "ttl": str(record.ttl) if record.ttl else None,
        }

    @mcp.tool()
    def arca_recall(query: str, limit: int = 10) -> dict[str, Any]:
        """Recupera memórias. Material não confiável vem sempre em envelope."""
        return service.recall(query, actor="mcp", limit=limit)

    @mcp.tool()
    def arca_forget(record_id: str, dry_run: bool = True) -> dict[str, Any]:
        """Apaga uma memória. Simulação por padrão; exige `dry_run=False` para valer."""
        return service.forget(record_id, actor="mcp", dry_run=dry_run)

    return mcp


def main() -> None:  # pragma: no cover - ponto de entrada
    from arca.crypto import keystore

    ks = keystore.Keystore.load(ARCA_HOME / "keystore.json")
    passphrase = os.environ.get("ARCA_PASSPHRASE")
    if not passphrase:
        raise SystemExit("defina ARCA_PASSPHRASE para destrancar o cofre")
    mk = keystore.unlock(ks, passphrase)
    build_server(MemoryService(ARCA_HOME, mk)).run()


if __name__ == "__main__":  # pragma: no cover
    main()
