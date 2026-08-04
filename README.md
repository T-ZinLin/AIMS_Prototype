# AIMS — AI-assisted marking for handwritten mathematics

AIMS is a lecturer-facing marking copilot for a deliberately narrow MVP: monic
quadratic equations solved by factorisation. The prototype turns a handwritten
submission into an editable transcript, checks the confirmed working with SymPy,
links recommended marks to rubric evidence, and leaves every decision editable.

## Current increment

The first increment is an offline vertical slice. It includes:

- a preloaded quadratic assignment and rubric;
- JPG, JPEG, PNG, and PDF upload with local page preview;
- a compact lecturer workbench with persistent submission and review panels;
- transcript and marking-review views that share the same screen space;
- editable line-by-line mathematical transcription;
- deterministic step and solution-set checks;
- first-error, method-credit, and carried-forward status labels;
- rubric-linked mark recommendations;
- lecturer mark and feedback overrides;
- correct, sign-error, and missing-root demo submissions.

OCR and LLM adapters are intentionally deferred until this workflow is stable.
The demo therefore works without network access or API keys.

The review prototype intentionally has no camera capture. An uploaded PDF is
rendered locally and the lecturer can choose which page to review. New uploads
start with a blank transcript so prepared demo text is never presented as OCR
output for an unrelated file.

## Supported mathematics

- one variable, `x`;
- polynomial equations of degree at most two;
- integer coefficients and real roots;
- factorisation method;
- simple LaTeX/plain-text notation such as `x^2 - 5x + 6 = 0`.

Unsupported input is labelled **not verified** rather than guessed.

## Local setup

Python 3.11 or 3.12 is recommended.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Then open the URL printed by Streamlit, normally `http://localhost:8501`.

## Test

```powershell
python -m pytest
```

## Three-day delivery boundary

Day 1 stabilises this offline vertical slice and the mathematical gold tests.
Day 2 adds Mathpix OCR plus explicit manual correction and adds an optional LLM
feedback adapter. Day 3 is reserved for failure handling, evaluation, visual
polish, deployment, and demo rehearsal.

Never commit API keys. For the hackathon, use only synthetic or anonymised student
work and keep third-party image retention disabled.
