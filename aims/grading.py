from __future__ import annotations

from aims.fixtures import RUBRIC
from aims.math_engine import analyse_steps
from aims.models import AnalysisResult, CriterionResult


def _first_with_tag(checks, tag: str):
    return next((check for check in checks if tag in check.tags), None)


def grade_submission(question: str, steps: list[str] | tuple[str, ...]) -> AnalysisResult:
    checks, target_roots = analyse_steps(question, steps)
    rubric = {item[0]: item for item in RUBRIC}

    setup = _first_with_tag(checks, "setup_correct")
    factor_correct = _first_with_tag(checks, "factor_correct")
    factor_partial = _first_with_tag(checks, "factor_partial")
    factor_attempt = _first_with_tag(checks, "factor_attempt")
    zero_product = _first_with_tag(checks, "zero_product_used")
    final_roots = _first_with_tag(checks, "final_roots")
    parseable = tuple(check for check in checks if check.status != "unverified")

    criteria: list[CriterionResult] = []

    _, title, maximum = rubric["setup"]
    criteria.append(
        CriterionResult(
            criterion_id="setup",
            title=title,
            max_marks=maximum,
            recommended_marks=1 if setup else 0,
            rationale=(
                "The opening equation preserves the given problem."
                if setup
                else "No verified opening line matches the given equation."
            ),
            evidence_line_ids=(setup.line_id,) if setup else (),
        )
    )

    _, title, maximum = rubric["factorisation"]
    factor_marks = 2 if factor_correct else 1 if factor_partial else 0
    factor_evidence = factor_correct or factor_partial or factor_attempt
    if factor_correct:
        factor_rationale = "The factors expand to the original quadratic and preserve both roots."
    elif factor_partial:
        factor_rationale = "A recognisable factorisation attempt preserves one root, but a sign changes the other."
    elif factor_attempt:
        factor_rationale = "A factorisation was attempted, but it does not preserve the original roots."
    else:
        factor_rationale = "No supported factorised form was found."
    criteria.append(
        CriterionResult(
            criterion_id="factorisation",
            title=title,
            max_marks=maximum,
            recommended_marks=factor_marks,
            rationale=factor_rationale,
            evidence_line_ids=(factor_evidence.line_id,) if factor_evidence else (),
        )
    )

    _, title, maximum = rubric["zero_product"]
    criteria.append(
        CriterionResult(
            criterion_id="zero_product",
            title=title,
            max_marks=maximum,
            recommended_marks=1 if zero_product else 0,
            rationale=(
                "The two factors are set equal to zero as separate cases."
                if zero_product
                else "The working does not explicitly apply both cases of the zero-product property."
            ),
            evidence_line_ids=(zero_product.line_id,) if zero_product else (),
        )
    )

    _, title, maximum = rubric["solutions"]
    claimed_roots = set(final_roots.roots) if final_roots else set()
    correct_roots = claimed_roots.intersection(target_roots)
    solution_marks = min(len(correct_roots), maximum)
    criteria.append(
        CriterionResult(
            criterion_id="solutions",
            title=title,
            max_marks=maximum,
            recommended_marks=solution_marks,
            rationale=(
                f"The final line contains {len(correct_roots)} of the {len(target_roots)} required roots."
                if final_roots
                else "No final line with x isolated was identified."
            ),
            evidence_line_ids=(final_roots.line_id,) if final_roots else (),
        )
    )

    _, title, maximum = rubric["clarity"]
    clarity_mark = 1 if len(parseable) >= 3 and len(parseable) == len(checks) else 0
    criteria.append(
        CriterionResult(
            criterion_id="clarity",
            title=title,
            max_marks=maximum,
            recommended_marks=clarity_mark,
            rationale=(
                "The submitted lines form a complete, readable sequence."
                if clarity_mark
                else "At least one line is missing or outside the supported notation."
            ),
            evidence_line_ids=tuple(check.line_id for check in parseable),
        )
    )

    misconception_code: str | None = None
    strengths: list[str] = []
    priorities: list[str] = []

    if setup:
        strengths.append("You began from the correct quadratic equation.")
    if zero_product:
        strengths.append("You used the zero-product structure to separate the two cases.")
    if correct_roots:
        strengths.append(f"You found {len(correct_roots)} correct root{'s' if len(correct_roots) != 1 else ''}.")

    if factor_partial:
        misconception_code = "FACTOR_SIGN"
        priorities.append(
            "Check factor signs by expanding before solving: the middle term and constant must both match."
        )
    elif factor_attempt and not factor_correct:
        misconception_code = "FACTOR_EQUIVALENCE"
        priorities.append("Expand the proposed factors to confirm that they reproduce the original quadratic.")
    elif not factor_attempt:
        misconception_code = "FACTOR_MISSING"
        priorities.append("Rewrite the quadratic as a product of two linear factors before finding roots.")

    if final_roots and len(correct_roots) < len(target_roots):
        priorities.append("Check both factors separately so that no root is changed or omitted.")
    elif not final_roots:
        priorities.append("Finish by isolating x and stating every root explicitly.")

    if not strengths:
        strengths.append("Your submission contains working that the lecturer can review and build on.")
    if not priorities:
        priorities.append("Verify each root by substituting it into the original equation.")

    feedback = " ".join(strengths + priorities)
    return AnalysisResult(
        step_checks=checks,
        criteria=tuple(criteria),
        strengths=tuple(strengths),
        priorities=tuple(priorities),
        student_feedback=feedback,
        misconception_code=misconception_code,
        target_roots=target_roots,
        metadata={"engine": "deterministic-offline", "domain": "real monic quadratics"},
    )
