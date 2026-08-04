from __future__ import annotations

from dataclasses import dataclass

from aims.models import AnalysisResult, StepCheck


@dataclass(frozen=True)
class StepPresentation:
    line_id: str
    label: str
    tone: str


def present_steps(checks: tuple[StepCheck, ...]) -> tuple[StepPresentation, ...]:
    """Convert checker facts into lecturer-friendly propagation labels."""
    first_error_index = next(
        (index for index, check in enumerate(checks) if check.status == "incorrect"),
        None,
    )
    presentations: list[StepPresentation] = []

    for index, check in enumerate(checks):
        if check.status == "unverified":
            label, tone = "Needs review", "unverified"
        elif first_error_index is not None and index == first_error_index:
            label, tone = "First error", "error"
        elif first_error_index is not None and index > first_error_index:
            if "zero_product_used" in check.tags:
                label, tone = "Method credit", "method"
            else:
                label, tone = "Carried forward", "carried"
        else:
            label, tone = "Verified", "verified"
        presentations.append(StepPresentation(check.line_id, label, tone))

    return tuple(presentations)


def divergence_summary(result: AnalysisResult) -> tuple[str, str]:
    first_error = next((check for check in result.step_checks if check.status == "incorrect"), None)
    if first_error is None:
        first_unverified = next((check for check in result.step_checks if check.status == "unverified"), None)
        if first_unverified:
            return (
                f"Review required · {first_unverified.line_id}",
                "This line is outside the supported checker and needs lecturer judgement.",
            )
        return "No divergence detected", "Every submitted line preserves the expected real solution set."

    if result.misconception_code == "FACTOR_SIGN":
        return (
            f"First divergence · {first_error.line_id}",
            "A factor sign changes one root. Later lines may still demonstrate valid method using that factorisation.",
        )
    return f"First divergence · {first_error.line_id}", first_error.explanation

