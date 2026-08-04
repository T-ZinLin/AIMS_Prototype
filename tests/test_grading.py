from aims.fixtures import DEMO_SUBMISSIONS, QUESTION
from aims.grading import grade_submission


def test_correct_submission_receives_full_recommendation():
    result = grade_submission(QUESTION, DEMO_SUBMISSIONS["Completely correct"])

    assert result.recommended_total == 7
    assert result.maximum_total == 7
    assert all(check.status == "verified" for check in result.step_checks)
    assert result.misconception_code is None


def test_sign_error_is_partial_credit_and_targeted_feedback():
    result = grade_submission(QUESTION, DEMO_SUBMISSIONS["Sign error — recommended demo"])
    marks = {criterion.criterion_id: criterion.recommended_marks for criterion in result.criteria}

    assert result.recommended_total == 5
    assert marks == {
        "setup": 1,
        "factorisation": 1,
        "zero_product": 1,
        "solutions": 1,
        "clarity": 1,
    }
    assert result.misconception_code == "FACTOR_SIGN"
    assert "factor signs" in result.priorities[0].lower()


def test_missing_root_is_detected_from_solution_set():
    result = grade_submission(QUESTION, DEMO_SUBMISSIONS["Missing one root"])
    final_step = result.step_checks[-1]

    assert final_step.status == "incorrect"
    assert final_step.title == "Incomplete solution set"
    assert final_step.roots == ("2",)


def test_unsupported_notation_fails_closed():
    result = grade_submission(QUESTION, [QUESTION, r"x=\sqrt{2}", "", ""])

    assert result.step_checks[1].status == "unverified"
    assert "Only x, integers" in result.step_checks[1].explanation
