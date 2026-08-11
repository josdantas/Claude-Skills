"""Versionamento do vault.

O git dá histórico e portabilidade de graça — exportar o cofre é um `git clone`,
que é a resposta do ARCA ao lock-in. Mas ele guarda tudo para sempre por
natureza, o que colide com a deleção verificável: por isso o Forget Engine
(Fase 3) precisa reescrever histórico, e não apenas commitar uma remoção.

Aqui na Fase 0 o escopo é só registrar as mudanças.
"""

from __future__ import annotations

from pathlib import Path

import pygit2

SIGNATURE = pygit2.Signature("ARCA", "arca@localhost")


class VaultGit:
    def __init__(self, root: Path) -> None:
        self.root = root
        git_dir = root / ".git"
        if git_dir.exists():
            self.repo = pygit2.Repository(str(git_dir))
        else:
            root.mkdir(parents=True, exist_ok=True)
            self.repo = pygit2.init_repository(str(root), bare=False)

    def commit_all(self, message: str) -> str | None:
        """Commita o estado atual do vault. Devolve o oid, ou None se nada mudou."""
        index = self.repo.index
        index.add_all()
        index.write()

        tree = index.write_tree()
        parents = [] if self.repo.head_is_unborn else [self.repo.head.target]

        if parents:
            head = self.repo.get(parents[0])
            if head is not None and head.tree.id == tree:
                return None  # nada a commitar

        oid = self.repo.create_commit(
            "HEAD", SIGNATURE, SIGNATURE, message, tree, parents
        )
        return str(oid)

    def log(self, limit: int = 20) -> list[tuple[str, str]]:
        if self.repo.head_is_unborn:
            return []
        return [
            (str(c.id)[:8], c.message.strip())
            for c in list(self.repo.walk(self.repo.head.target))[:limit]
        ]
