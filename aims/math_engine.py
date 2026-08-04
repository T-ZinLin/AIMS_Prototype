from __future__ import annotations

import re
from dataclasses import dataclass

from sympy import FiniteSet, Poly, S, Symbol, default_sort_key, solveset
from sympy.core.expr import Expr
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

from aims.models import StepCheck


X = Symbol("x", real=True)
TRANSFORMATIONS = standard_transformations + (
    convert_xor,
    implicit_multiplication_application,
)
ALLOWED_EXPRESSION = re.compile(r"^[0-9xX+\-*/^=().\s]+$")


class UnsupportedMath(ValueError):
    """Raised when an expression is outside the intentionally small MVP grammar."""


@dataclass(frozen=True)
class ParsedLine:
    normalized: str
    relations: tuple[Expr, ...]
    roots: FiniteSet


def normalize_math(raw: str) -> str:
    """Convert the small supported subset of LaTeX into parser-friendly text."""
    value = raw.strip().strip("$")
    value = value.replace("−", "-").replace("×", "*")
    value = value.replace(r"\left", "").replace(r"\right", "")
    value = value.replace(r"\cdot", "*").replace(r"\times", "*")
    value = re.sub(r"\\(?:text|mathrm)\s*\{\s*or\s*\}", " or ", value)
    value = value.replace(r"\quad", " or ")
    value = value.replace(r"\;", " ").replace(r"\,", " ")
    value = re.sub(r"\^\{\s*([+-]?\d+)\s*\}", r"^\1", value)
    value = value.replace("{", "(").replace("}", ")")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _parse_relation(value: str) -> Expr:
    if not value or not ALLOWED_EXPRESSION.fullmatch(value):
        raise UnsupportedMath("Only x, integers, basic operators and equations are supported.")
    if value.count("=") != 1:
        raise UnsupportedMath("Each step must contain exactly one equals sign.")

    left_text, right_text = (part.strip() for part in value.split("=", maxsplit=1))
    if not left_text or not right_text:
        raise UnsupportedMath("Both sides of the equation are required.")

    local_symbols = {"x": X, "X": X}
    left = parse_expr(
        left_text,
        local_dict=local_symbols,
        transformations=TRANSFORMATIONS,
        evaluate=True,
    )
    right = parse_expr(
        right_text,
        local_dict=local_symbols,
        transformations=TRANSFORMATIONS,
        evaluate=True,
    )
    relation = left - right

    if relation.free_symbols - {X}:
        raise UnsupportedMath("Only the variable x is supported.")
    try:
        polynomial = Poly(relation, X)
    except Exception as exc:  # SymPy raises several polynomial-specific exceptions.
        raise UnsupportedMath("The step is not a polynomial equation in x.") from exc
    if polynomial.degree() > 2:
        raise UnsupportedMath("Only equations up to degree two are supported.")
    return relation


def parse_line(raw: str) -> ParsedLine:
    normalized = normalize_math(raw)
    parts = tuple(part.strip() for part in re.split(r"\bor\b", normalized) if part.strip())
    if not parts:
        raise UnsupportedMath("The step is empty.")

    relations = tuple(_parse_relation(part) for part in parts)
    roots = S.EmptySet
    for relation in relations:
        solution = solveset(relation, X, domain=S.Reals)
        if not isinstance(solution, FiniteSet):
            raise UnsupportedMath("The solution set is not finite in the supported domain.")
        roots = roots.union(solution)
    if not isinstance(roots, FiniteSet):
        raise UnsupportedMath("The combined solution set is not supported.")
    return ParsedLine(normalized=normalized, relations=relations, roots=roots)


def _root_strings(roots: FiniteSet) -> tuple[str, ...]:
    return tuple(str(root) for root in sorted(roots, key=default_sort_key))


def _is_factor_attempt(normalized: str) -> bool:
    compact = normalized.replace(" ", "")
    return bool(re.search(r"(?:\)|x)\(", compact)) and "^" not in compact.split("=", 1)[0]


def _is_final_root_line(normalized: str) -> bool:
    parts = tuple(part.strip() for part in re.split(r"\bor\b", normalized))
    if not parts:
        return False
    for part in parts:
        if part.count("=") != 1:
            return False
        left, right = (side.replace(" ", "") for side in part.split("=", 1))
        if left.lower() != "x" and right.lower() != "x":
            return False
    return True


def analyse_steps(question: str, steps: list[str] | tuple[str, ...]) -> tuple[tuple[StepCheck, ...], tuple[str, ...]]:
    target = parse_line(question)
    target_roots = target.roots
    checks: list[StepCheck] = []

    for index, raw in enumerate(steps, start=1):
        line_id = f"L{index}"
        try:
            parsed = parse_line(raw)
        except (UnsupportedMath, TypeError, ValueError) as exc:
            checks.append(
                StepCheck(
                    line_id=line_id,
                    raw=raw,
                    normalized=normalize_math(raw),
                    status="unverified",
                    title="Not automatically verified",
                    explanation=str(exc),
                )
            )
            continue

        tags: list[str] = []
        factor_attempt = _is_factor_attempt(parsed.normalized)
        final_root_line = _is_final_root_line(parsed.normalized)
        if index == 1 and parsed.roots == target_roots:
            tags.append("setup_correct")
        if factor_attempt:
            tags.append("factor_attempt")
            if parsed.roots == target_roots:
                tags.append("factor_correct")
            elif parsed.roots.intersect(target_roots) is not S.EmptySet:
                tags.append("factor_partial")
        if len(parsed.relations) > 1 and not final_root_line:
            tags.append("zero_product_used")
        if final_root_line:
            tags.append("final_roots")

        if parsed.roots == target_roots:
            status = "verified"
            title = "Equivalent step"
            explanation = "This line has the same real solution set as the original equation."
        elif parsed.roots.is_subset(target_roots):
            status = "incorrect"
            title = "Incomplete solution set"
            explanation = "This line keeps some valid roots but omits at least one solution."
        elif parsed.roots.intersect(target_roots) is not S.EmptySet:
            status = "incorrect"
            title = "Partially overlaps"
            explanation = "This line retains a valid root but also changes or loses part of the solution set."
        else:
            status = "incorrect"
            title = "Changes the solution set"
            explanation = "The real solutions of this line do not match the original equation."

        checks.append(
            StepCheck(
                line_id=line_id,
                raw=raw,
                normalized=parsed.normalized,
                status=status,
                title=title,
                explanation=explanation,
                roots=_root_strings(parsed.roots),
                tags=tuple(tags),
            )
        )

    return tuple(checks), _root_strings(target_roots)

