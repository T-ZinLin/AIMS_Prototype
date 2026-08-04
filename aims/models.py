from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


CheckStatus = Literal["verified", "incorrect", "unverified"]


@dataclass(frozen=True)
class StepCheck:
    line_id: str
    raw: str
    normalized: str
    status: CheckStatus
    title: str
    explanation: str
    roots: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class CriterionResult:
    criterion_id: str
    title: str
    max_marks: int
    recommended_marks: int
    rationale: str
    evidence_line_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnalysisResult:
    step_checks: tuple[StepCheck, ...]
    criteria: tuple[CriterionResult, ...]
    strengths: tuple[str, ...]
    priorities: tuple[str, ...]
    student_feedback: str
    misconception_code: str | None = None
    target_roots: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def recommended_total(self) -> int:
        return sum(item.recommended_marks for item in self.criteria)

    @property
    def maximum_total(self) -> int:
        return sum(item.max_marks for item in self.criteria)
