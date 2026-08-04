from aims.fixtures import DEMO_SUBMISSIONS, QUESTION
from aims.grading import grade_submission
from aims.review import divergence_summary, present_steps


def test_sign_error_is_presented_as_first_error_then_propagation():
    result = grade_submission(QUESTION, DEMO_SUBMISSIONS["Sign error — recommended demo"])

    labels = [step.label for step in present_steps(result.step_checks)]

    assert labels == ["Verified", "First error", "Method credit", "Carried forward"]
    title, explanation = divergence_summary(result)
    assert title == "First divergence · L2"
    assert "factor sign" in explanation.lower()


def test_correct_work_has_no_divergence():
    result = grade_submission(QUESTION, DEMO_SUBMISSIONS["Completely correct"])

    assert all(step.label == "Verified" for step in present_steps(result.step_checks))
    assert divergence_summary(result)[0] == "No divergence detected"
