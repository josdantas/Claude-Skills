"""Modelo do registro de memória.

Campos sem default são obrigatórios por decisão de segurança: **não existe
escrita sem procedência**. A política de confiança mora em YAML versionado
(`arca/gateway/trust_policy.yaml`) para que um auditor a leia sem abrir código.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

POLICY_PATH = Path(__file__).resolve().parents[1] / "gateway" / "trust_policy.yaml"


class SourceClass(StrEnum):
    USER_DIRECT = "user_direct"
    USER_DOCUMENT = "user_document"
    AGENT_INFERENCE = "agent_inference"
    TOOL_OUTPUT = "tool_output"
    WEB_CONTENT = "web_content"
    THIRD_PARTY_AGENT = "third_party_agent"


Status = Literal["candidate", "trusted", "quarantined", "revoked"]
Sensitivity = Literal["public", "normal", "sensitive", "secret"]
Scope = Literal["session", "project", "user", "org"]


class TrustRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    initial_status: Status
    weight: float = Field(ge=0.0, le=1.0)
    may_instruct: bool
    default_ttl: timedelta | None = None


@lru_cache(maxsize=1)
def trust_policy() -> dict[SourceClass, TrustRule]:
    raw = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    return {
        SourceClass(k): TrustRule.model_validate(v)
        for k, v in raw["source_classes"].items()
    }


def rule_for(source_class: SourceClass) -> TrustRule:
    return trust_policy()[source_class]


class MemoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)

    id: str
    created_at: datetime
    valid_from: date
    valid_to: date | None = None
    supersedes: list[str] = Field(default_factory=list)

    scope: Scope
    source_class: SourceClass
    source_ref: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    sensitivity: Sensitivity
    pii: list[str] = Field(default_factory=list)
    status: Status
    ttl: timedelta | None = None
    entities: list[str] = Field(default_factory=list)

    body: str

    # -- invariantes de segurança -------------------------------------------

    @property
    def may_instruct(self) -> bool:
        """Só `user_direct` pode virar instrução. Ver plano §5 e §6."""
        return rule_for(self.source_class).may_instruct and self.status == "trusted"

    @property
    def trust_weight(self) -> float:
        return rule_for(self.source_class).weight

    def render_for_prompt(self) -> str:
        """Renderização segura. Material não confiável sai sempre em envelope."""
        if self.may_instruct:
            return self.body
        return (
            f'<dado_nao_confiavel origem="{self.source_class.value}" '
            f'ref="{self.source_ref}" id="{self.id}">\n{self.body}\n</dado_nao_confiavel>'
        )

    def is_expired(self, now: datetime) -> bool:
        return self.ttl is not None and now >= self.created_at + self.ttl
