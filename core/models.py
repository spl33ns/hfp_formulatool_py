from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


LiteralOp = Literal["EQ1", "EQ0", "NEQ1"]


@dataclass(frozen=True)
class LiteralModel:
    id: str
    display_name: str
    op: LiteralOp


@dataclass(frozen=True)
class SectionKey:
    env_objective: str | None
    section_number: str | None
    activity: str | None
    dnsh_goal: str | None
    formula_ids: str | None
    type_label: str | None


@dataclass
class SectionResult:
    key: SectionKey
    sheet_name: str | None
    formula_ids: str | None
    formula_display: str | None
    variables: list[LiteralModel]
    dnf: list[list[LiteralModel]]
    status: str
    error: str | None
