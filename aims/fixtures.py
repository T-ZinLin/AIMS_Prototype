from __future__ import annotations


QUESTION = r"x^2 - 5x + 6 = 0"
QUESTION_DISPLAY = r"x^2 - 5x + 6 = 0"
INSTRUCTION = "Solve by factorisation. Show every step."

MODEL_STEPS = (
    r"x^2 - 5x + 6 = 0",
    r"(x - 2)(x - 3) = 0",
    r"x - 2 = 0 \text{ or } x - 3 = 0",
    r"x = 2 \text{ or } x = 3",
)

RUBRIC = (
    ("setup", "Uses the given equation correctly", 1),
    ("factorisation", "Factorises the quadratic", 2),
    ("zero_product", "Applies the zero-product property", 1),
    ("solutions", "Obtains both roots", 2),
    ("clarity", "Presents a coherent chain of working", 1),
)

DEMO_SUBMISSIONS = {
    "Sign error — recommended demo": (
        r"x^2 - 5x + 6 = 0",
        r"(x - 2)(x + 3) = 0",
        r"x - 2 = 0 \text{ or } x + 3 = 0",
        r"x = 2 \text{ or } x = -3",
    ),
    "Completely correct": MODEL_STEPS,
    "Missing one root": (
        r"x^2 - 5x + 6 = 0",
        r"(x - 2)(x - 3) = 0",
        r"x - 2 = 0",
        r"x = 2",
    ),
    "Blank manual entry": ("", "", "", ""),
}

