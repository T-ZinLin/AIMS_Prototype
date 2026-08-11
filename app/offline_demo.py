"""Curated, API-key-free demonstration cases.

The JSON manifest is the only place that contains sample-specific inputs and
hand-reviewed AI outputs. This module turns those definitions into the exact
content-addressed cache entries the normal runtime will request. It does not
short-circuit transcription, verification, marking, feedback, practice, or
cohort aggregation.

Only the genuinely AI-dependent responses live in the manifest:

* vision transcription, and only when a real fixture image exists;
* rubric-marking output;
* feedback prose.

SymPy verification, misconception classification, response validation,
practice generation, persistence, and class aggregation all execute normally.
"""

import base64
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app import feedback, llm, marker, uploads
from app.config import (
    IMAGES_DIR,
    MARKING_MODEL,
    OFFLINE_DEMO_CASES_FILE,
    VISION_MODEL,
)
from app.models import Confidence, Feedback, Step
from app.store import get_question
from app.transcriber import build_prompt as build_transcription_prompt
from app.verifier import verify


class CachedTranscriptionStep(BaseModel):
    latex: str
    confidence: Confidence = "high"


class CachedTranscription(BaseModel):
    steps: list[CachedTranscriptionStep]
    notes: str = ""


class OfflineDemoCase(BaseModel):
    id: str
    title: str
    summary: str
    scenario: str = Field(min_length=1)
    question_id: str
    student_pseudonym: str
    image_filename: str | None = None
    transcription: CachedTranscription | None = None
    confirmed_steps: list[str] = Field(min_length=1)
    expected_misconceptions: list[str] = Field(default_factory=list)
    mark_response: dict[str, Any]
    feedback_response: dict[str, Any]

    @field_validator("id")
    @classmethod
    def safe_id(cls, value: str) -> str:
        allowed = "abcdefghijklmnopqrstuvwxyz0123456789-_"
        if not value or any(ch not in allowed for ch in value):
            raise ValueError(
                "demo case ids may contain only lowercase letters, digits, - and _"
            )
        return value

    @field_validator("image_filename")
    @classmethod
    def safe_image_filename(cls, value: str | None) -> str | None:
        if value is not None and Path(value).name != value:
            raise ValueError("demo image_filename must be a plain filename")
        if value is not None and Path(value).suffix.lower() not in {
            ".jpg",
            ".jpeg",
            ".png",
        }:
            raise ValueError("demo fixture images must be JPEG or PNG files")
        return value

    @model_validator(mode="after")
    def image_and_transcription_are_paired(self) -> "OfflineDemoCase":
        if bool(self.image_filename) != bool(self.transcription):
            raise ValueError(
                "image_filename and transcription must either both be present or both be null"
            )
        if any(not step.strip() for step in self.confirmed_steps):
            raise ValueError("confirmed demo steps cannot be blank")
        if self.transcription is not None:
            transcribed = [step.latex for step in self.transcription.steps]
            if transcribed != self.confirmed_steps:
                raise ValueError(
                    "an image case's prepared transcription must match its default "
                    "confirmed steps so the one-click walkthrough stays cache-safe"
                )
        return self

    @property
    def input_kind(self) -> Literal["handwritten", "prepared_steps"]:
        return "handwritten" if self.image_filename else "prepared_steps"


class DemoCaseInfo(BaseModel):
    id: str
    title: str
    summary: str
    scenario: str
    question_id: str
    student_pseudonym: str
    input_kind: Literal["handwritten", "prepared_steps"]
    prepared_steps: list[Step] = Field(default_factory=list)
    cache_ready: bool


class DemoCatalogue(BaseModel):
    mode: str
    offline: bool
    cases: list[DemoCaseInfo]


@dataclass(frozen=True)
class DemoCacheEntry:
    stage: Literal["transcription", "marking", "feedback"]
    key: str
    payload: dict[str, Any]


@lru_cache(maxsize=1)
def list_demo_cases() -> list[OfflineDemoCase]:
    raw = json.loads(OFFLINE_DEMO_CASES_FILE.read_text(encoding="utf-8"))
    cases = [OfflineDemoCase.model_validate(item) for item in raw]
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("offline demo case ids must be unique")
    return cases


def get_demo_case(case_id: str) -> OfflineDemoCase:
    try:
        return next(case for case in list_demo_cases() if case.id == case_id)
    except StopIteration as error:
        raise KeyError(f"unknown demo case: {case_id}") from error


def demo_image_path(case: OfflineDemoCase) -> Path:
    """Resolve a manifest-whitelisted fixture image without exposing the directory."""
    if not case.image_filename:
        raise FileNotFoundError(f"demo case {case.id!r} has no fixture image")
    root = IMAGES_DIR.resolve()
    path = (root / case.image_filename).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise FileNotFoundError(
            f"demo image {case.image_filename!r} is missing from {IMAGES_DIR}"
        )
    return path


def _confirmed_steps(case: OfflineDemoCase) -> list[Step]:
    return [
        Step(index=index, latex=latex)
        for index, latex in enumerate(case.confirmed_steps, start=1)
    ]


def build_cache_entries(case: OfflineDemoCase) -> list[DemoCacheEntry]:
    """Derive every AI cache entry needed by one case, without calling an API."""
    question = get_question(case.question_id)
    steps = _confirmed_steps(case)
    report = verify(steps, question.model_solution_steps, question.variable)

    if report.candidate_misconceptions != case.expected_misconceptions:
        raise ValueError(
            f"{case.id}: verifier produced {report.candidate_misconceptions}, "
            f"manifest expects {case.expected_misconceptions}"
        )
    if case.scenario == "correct" and not report.final_answer_correct:
        raise ValueError(f"{case.id}: a correct demo case must verify as correct")

    entries: list[DemoCacheEntry] = []
    if case.transcription is not None:
        png = uploads.render_page(demo_image_path(case).read_bytes())
        image_b64 = base64.b64encode(png).decode()
        entries.append(
            DemoCacheEntry(
                stage="transcription",
                key=llm.cache_key(
                    VISION_MODEL,
                    build_transcription_prompt("student"),
                    image_b64,
                ),
                payload=case.transcription.model_dump(),
            )
        )

    returned_criteria = {
        item.get("criterion_id")
        for item in case.mark_response.get("criteria", [])
        if isinstance(item, dict)
    }
    rubric_criteria = {criterion.id for criterion in question.criteria}
    if returned_criteria != rubric_criteria:
        raise ValueError(
            f"{case.id}: marking fixture criteria {sorted(returned_criteria)} "
            f"do not match rubric criteria {sorted(rubric_criteria)}"
        )

    mark_prompt = marker.build_prompt(question, steps, report)
    entries.append(
        DemoCacheEntry(
            stage="marking",
            key=llm.cache_key(MARKING_MODEL, mark_prompt, None),
            payload=case.mark_response,
        )
    )

    proposal = marker.proposal_from_payload(question, report, case.mark_response)
    if proposal.misconceptions != case.expected_misconceptions:
        raise ValueError(
            f"{case.id}: marking fixture returned {proposal.misconceptions}, "
            f"expected {case.expected_misconceptions}"
        )
    Feedback.model_validate(case.feedback_response)
    feedback_prompt = feedback.build_prompt(question, steps, proposal, report)
    entries.append(
        DemoCacheEntry(
            stage="feedback",
            key=llm.cache_key(MARKING_MODEL, feedback_prompt, None),
            payload=case.feedback_response,
        )
    )
    return entries


def case_cache_ready(case: OfflineDemoCase) -> bool:
    """True only when every required key contains the manifest's exact payload."""
    try:
        entries = build_cache_entries(case)
    except FileNotFoundError:
        return False
    return all(llm.read_cache(entry.key) == entry.payload for entry in entries)


def catalogue(mode: str) -> DemoCatalogue:
    cases: list[DemoCaseInfo] = []
    for case in list_demo_cases():
        prepared_steps = []
        if case.input_kind == "prepared_steps":
            prepared_steps = _confirmed_steps(case)
        cases.append(
            DemoCaseInfo(
                id=case.id,
                title=case.title,
                summary=case.summary,
                scenario=case.scenario,
                question_id=case.question_id,
                student_pseudonym=case.student_pseudonym,
                input_kind=case.input_kind,
                prepared_steps=prepared_steps,
                cache_ready=case_cache_ready(case),
            )
        )
    return DemoCatalogue(mode=mode, offline=mode == "offline", cases=cases)
