"""Critério de aceite da Fase 0: qualquer sequência de operações mantém a
cadeia de auditoria íntegra, e nenhuma adulteração passa despercebida."""

from __future__ import annotations

import json
import os

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from arca.audit.chain import AuditLog, audit_key

OPS = st.sampled_from(["write", "recall", "forget", "promote", "unlock", "quarantine"])
ACTORS = st.sampled_from(["mcp://claude-code/s1", "cli://arca", "mcp://cursor/s2"])


def _log(tmp_path) -> AuditLog:
    return AuditLog(tmp_path / "audit", audit_key(os.urandom(32)))


@settings(max_examples=40, deadline=None)
@given(ops=st.lists(st.tuples(OPS, ACTORS), min_size=1, max_size=60))
def test_chain_holds_for_any_sequence(ops, tmp_path_factory):
    log = _log(tmp_path_factory.mktemp("audit"))
    for op, actor in ops:
        log.append(op, actor, record_id="mem_x")

    ok, problem = log.verify()
    assert ok, problem
    assert log.last().seq == len(ops)


def test_tamper_in_the_middle_is_detected(tmp_path):
    log = _log(tmp_path)
    for i in range(10):
        log.append("write", "cli://arca", record_id=f"mem_{i}")

    path = next((tmp_path / "audit").glob("*.jsonl"))
    lines = path.read_text().splitlines()
    entry = json.loads(lines[4])
    entry["decision"] = "trusted"  # muda a decisão registrada
    lines[4] = json.dumps(entry, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n")

    ok, problem = log.verify()
    assert not ok
    assert "seq 5" in problem


def test_deleting_an_entry_is_detected(tmp_path):
    log = _log(tmp_path)
    for i in range(6):
        log.append("write", "cli://arca", record_id=f"mem_{i}")

    path = next((tmp_path / "audit").glob("*.jsonl"))
    lines = path.read_text().splitlines()
    del lines[2]
    path.write_text("\n".join(lines) + "\n")

    ok, problem = log.verify()
    assert not ok


def test_log_from_another_key_does_not_verify(tmp_path):
    log = _log(tmp_path)
    log.append("write", "cli://arca")
    impostor = AuditLog(tmp_path / "audit", audit_key(os.urandom(32)))
    ok, problem = impostor.verify()
    assert not ok
    assert "HMAC" in problem


def test_no_body_leaks_into_log(tmp_path):
    """O log carrega metadados, nunca conteúdo de memória."""
    log = _log(tmp_path)
    for field in ("body", "plaintext", "content", "text"):
        with pytest.raises(ValueError, match="conteúdo de memória"):
            log.append("write", "cli://arca", **{field: "segredo do usuário"})


def test_anchor_covers_the_day(tmp_path):
    log = _log(tmp_path)
    log.append("write", "cli://arca")
    first = log.anchor()
    assert first and first.startswith("sha256:")

    log.append("write", "cli://arca")
    assert log.anchor() != first  # a âncora acompanha o crescimento do dia
