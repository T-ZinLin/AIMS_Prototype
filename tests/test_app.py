from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_lecturer_workspace_loads_without_runtime_errors():
    app_path = Path(__file__).parents[1] / "app.py"
    app = AppTest.from_file(str(app_path)).run(timeout=15)

    assert not app.exception
    assert app.segmented_control[0].value == "Prepared example"
    assert app.segmented_control[1].value == "Transcript"
    assert app.text_input[0].value == "x^2 - 5x + 6 = 0"
    assert any(button.label == "Check mathematics" for button in app.button)
    assert any(button.label == "Approve review" for button in app.button)


def test_review_can_be_checked_and_approved():
    app_path = Path(__file__).parents[1] / "app.py"
    app = AppTest.from_file(str(app_path)).run(timeout=15)

    app.checkbox[0].check().run(timeout=15)
    next(button for button in app.button if button.label == "Check mathematics").click().run(timeout=15)
    next(button for button in app.button if button.label == "Approve review").click().run(timeout=15)

    assert app.session_state["approved_review_signature"]
    assert any("Approved · 5/7" in markdown.value for markdown in app.markdown)

    next(
        button
        for button in app.button
        if button.label == "Increase mark for Factorises the quadratic"
    ).click().run(timeout=15)

    assert not any("Approved ·" in markdown.value for markdown in app.markdown)
    assert any("Reviewing · 6/7" in markdown.value for markdown in app.markdown)
    assert not app.number_input

    next(
        button
        for button in app.button
        if button.label == "Decrease mark for Factorises the quadratic"
    ).click().run(timeout=15)

    assert app.session_state["mark_factorisation"] == 1
    assert any("5/7" in markdown.value for markdown in app.markdown)


def test_student_queue_switches_the_active_lecturer_submission():
    app_path = Path(__file__).parents[1] / "app.py"
    app = AppTest.from_file(str(app_path)).run(timeout=15)

    next(button for button in app.button if button.label == "Tessa (S028)").click().run(timeout=15)

    assert app.session_state["selected_submission_id"] == "S028"
    assert [field.value for field in app.text_input] == ["", "", "", ""]
    assert any(
        "Tessa (S028)" in markdown.value and "Lecturer marking workspace" in markdown.value
        for markdown in app.markdown
    )
    assert any("Camera capture placeholder" in markdown.value for markdown in app.markdown)
