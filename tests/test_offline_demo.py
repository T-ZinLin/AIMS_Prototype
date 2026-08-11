import io
import json
import re

from fastapi.testclient import TestClient
from PIL import Image

from app import llm, main, store
from app.main import app
from app.models import Step
from app.offline_demo import (
    build_cache_entries,
    demo_image_path,
    list_demo_cases,
)
from app.store import get_question
from app.verifier import verify
from scripts.seed_demo_cache import seed_demo_cache


client = TestClient(app)


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), (240, 240, 240)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_manifest_covers_the_three_required_scenarios():
    cases = list_demo_cases()

    assert {
        "correct",
        "lost_root",
        "dropped_plus_minus",
    } <= {case.scenario for case in cases}
    assert len({case.id for case in cases}) == len(cases)


def test_only_the_ai_dependent_stages_have_cache_entries():
    for case in list_demo_cases():
        stages = [entry.stage for entry in build_cache_entries(case)]
        expected = ["marking", "feedback"]
        if case.input_kind == "handwritten":
            expected.insert(0, "transcription")
        assert stages == expected
        assert "verification" not in stages
        assert "practice" not in stages
        assert "class_summary" not in stages


def test_each_case_is_classified_by_the_real_verifier_as_declared():
    for case in list_demo_cases():
        question = get_question(case.question_id)
        steps = [
            Step(index=index, latex=latex)
            for index, latex in enumerate(case.confirmed_steps, start=1)
        ]

        report = verify(steps, question.model_solution_steps, question.variable)

        assert report.candidate_misconceptions == case.expected_misconceptions
        assert report.final_answer_correct is (case.scenario == "correct")


def test_the_handwritten_case_uses_a_real_existing_fixture():
    handwritten = [case for case in list_demo_cases() if case.input_kind == "handwritten"]

    assert handwritten
    path = demo_image_path(handwritten[0])
    assert path.is_file()
    assert path.stat().st_size > 1_000
    assert not path.name.startswith("REPLACE-ME")


def test_seeder_writes_every_entry_without_constructing_an_anthropic_client(
    tmp_path, monkeypatch
):
    class ForbiddenAnthropic:
        def __init__(self, *args, **kwargs):
            raise AssertionError("offline demo seeding must never construct an API client")

    monkeypatch.setattr(llm, "Anthropic", ForbiddenAnthropic)

    expected_count = sum(
        len(build_cache_entries(case)) for case in list_demo_cases()
    )
    count = seed_demo_cache(cache_dir=tmp_path)

    files = list(tmp_path.glob("*.json"))
    assert count == expected_count
    assert len(files) == count
    assert all(json.loads(path.read_text(encoding="utf-8")) for path in files)


def test_reset_preserves_unrelated_live_cache_entries(tmp_path):
    unrelated = tmp_path / "unrelated-live-key.json"
    unrelated.write_text('{"keep": true}', encoding="utf-8")

    seed_demo_cache(cache_dir=tmp_path, reset=True)

    assert json.loads(unrelated.read_text(encoding="utf-8")) == {"keep": True}


def test_demo_catalogue_and_whitelisted_image_are_available(monkeypatch):
    monkeypatch.setattr(main, "DEMO_MODE", "offline")
    response = client.get("/api/demo")

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "offline"
    assert body["offline"] is True
    assert len(body["cases"]) >= 3
    assert all(case["cache_ready"] for case in body["cases"])

    image_case = next(case for case in body["cases"] if case["input_kind"] == "handwritten")
    image_response = client.get(f"/api/demo/cases/{image_case['id']}/image")
    assert image_response.status_code == 200
    assert image_response.headers["content-type"].startswith("image/")

    typed_case = next(case for case in body["cases"] if case["input_kind"] == "prepared_steps")
    assert client.get(f"/api/demo/cases/{typed_case['id']}/image").status_code == 404
    assert client.get("/api/demo/cases/not-a-case/image").status_code == 404


def test_all_curated_cases_run_end_to_end_offline_through_the_real_pipeline(
    tmp_path, monkeypatch
):
    cache_dir = tmp_path / "cache"
    images_dir = tmp_path / "images"
    submissions_dir = tmp_path / "submissions"
    cache_dir.mkdir()
    images_dir.mkdir()
    submissions_dir.mkdir()

    monkeypatch.setattr(llm, "LLM_CACHE_DIR", cache_dir)
    monkeypatch.setattr(llm, "DEMO_MODE", "offline")
    monkeypatch.setattr(main, "IMAGES_DIR", images_dir)
    monkeypatch.setattr(store, "SUBMISSIONS_DIR", submissions_dir)
    seed_demo_cache(cache_dir=cache_dir)

    class ForbiddenAnthropic:
        def __init__(self, *args, **kwargs):
            raise AssertionError("a seeded offline flow must never construct an API client")

    monkeypatch.setattr(llm, "Anthropic", ForbiddenAnthropic)

    for case in list_demo_cases():
        created = client.post(
            "/api/submissions",
            json={
                "question_id": case.question_id,
                "student_pseudonym": case.student_pseudonym,
            },
        )
        assert created.status_code == 200
        submission_id = created.json()["id"]

        if case.input_kind == "handwritten":
            image_path = demo_image_path(case)
            transcribed = client.post(
                f"/api/submissions/{submission_id}/transcribe",
                files={
                    "file": (
                        image_path.name,
                        io.BytesIO(image_path.read_bytes()),
                        "image/jpeg",
                    )
                },
            )
            assert transcribed.status_code == 200
            confirmed = transcribed.json()["confirmed_steps"]
            assert [step["latex"] for step in confirmed] == case.confirmed_steps
        else:
            updated = client.put(
                f"/api/submissions/{submission_id}/steps",
                json={
                    "steps": [
                        {"index": index, "latex": latex}
                        for index, latex in enumerate(case.confirmed_steps, start=1)
                    ]
                },
            )
            assert updated.status_code == 200

        marked = client.post(f"/api/submissions/{submission_id}/mark")
        assert marked.status_code == 200
        body = marked.json()
        assert body["verification"]["candidate_misconceptions"] == case.expected_misconceptions
        assert body["marks"]["misconceptions"] == case.expected_misconceptions
        assert body["feedback"] is not None
        assert len(body["practice"]) == 3

    summary = client.get("/api/class/summary").json()
    assert summary["source"] == "computed"
    assert summary["cohort_size"] == 3
    assert summary["marked"] == 3


def test_arbitrary_offline_upload_gets_a_friendly_message_without_a_cache_key(
    tmp_path, monkeypatch
):
    cache_dir = tmp_path / "empty-cache"
    images_dir = tmp_path / "images"
    submissions_dir = tmp_path / "submissions"
    cache_dir.mkdir()
    images_dir.mkdir()
    submissions_dir.mkdir()

    monkeypatch.setattr(llm, "LLM_CACHE_DIR", cache_dir)
    monkeypatch.setattr(llm, "DEMO_MODE", "offline")
    monkeypatch.setattr(main, "IMAGES_DIR", images_dir)
    monkeypatch.setattr(store, "SUBMISSIONS_DIR", submissions_dir)

    submission = client.post("/api/submissions", json={"question_id": "q1"}).json()
    response = client.post(
        f"/api/submissions/{submission['id']}/transcribe",
        files={"file": ("new.png", io.BytesIO(_png_bytes()), "image/png")},
    )

    assert response.status_code == 503
    body = response.json()
    assert body["error"] == "offline_cache_miss"
    assert "curated demo sample" in body["hint"].lower()
    assert "for key" not in json.dumps(body).lower()
    assert re.search(r"\b[0-9a-f]{32}\b", json.dumps(body).lower()) is None
    assert list(images_dir.iterdir()) == []
