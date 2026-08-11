"""Seed every curated offline demo case without calling Anthropic.

The source of truth is ``fixtures/offline_demo_cases.json``. For each case this
script runs the real deterministic verifier, builds the real marking and
feedback prompts, derives the exact content-addressed keys used at runtime,
and writes only the prepared AI responses:

* transcription for cases backed by a real fixture image;
* marking;
* feedback.

Verification, misconception detection, practice generation, persistence and
class aggregation are deliberately not cached.

Examples (from the repository root):

    python scripts/seed_demo_cache.py
    python scripts/seed_demo_cache.py --check
    python scripts/seed_demo_cache.py --reset
    python scripts/seed_demo_cache.py --reset-submissions

``--reset`` removes and recreates only keys owned by the current demo
manifest; unrelated live-mode cache entries are preserved. The separate,
explicit ``--reset-submissions`` flag clears local submission JSON so the
class dashboard starts empty again.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import LLM_CACHE_DIR, SUBMISSIONS_DIR  # noqa: E402
from app.offline_demo import build_cache_entries, list_demo_cases  # noqa: E402


def _write_cache(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def seed_demo_cache(cache_dir: Path = LLM_CACHE_DIR, reset: bool = False) -> int:
    """Write the manifest-owned entries and return the number of unique keys."""
    cases = list_demo_cases()
    planned = []
    for case in cases:
        entries = build_cache_entries(case)
        planned.append((case, entries))

    unique = {entry.key for _, entries in planned for entry in entries}
    if reset:
        for key in unique:
            (cache_dir / f"{key}.json").unlink(missing_ok=True)

    print(f"Seeding {len(cases)} curated offline demo cases:")
    for case, entries in planned:
        print(f"\n  {case.id}: {case.title}")
        print(f"    question: {case.question_id}; input: {case.input_kind}")
        for entry in entries:
            path = cache_dir / f"{entry.key}.json"
            _write_cache(path, entry.payload)
            print(f"    {entry.stage:<13} -> {path.as_posix()}")

    print(f"\nReady: {len(cases)} cases, {len(unique)} AI cache entries, 0 API calls.")
    return len(unique)


def check_demo_cache(cache_dir: Path = LLM_CACHE_DIR) -> bool:
    """Validate that every runtime key exists with the exact prepared payload."""
    ok = True
    for case in list_demo_cases():
        for entry in build_cache_entries(case):
            path = cache_dir / f"{entry.key}.json"
            try:
                actual = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                print(f"MISSING  {case.id:<30} {entry.stage:<13} {entry.key}")
                ok = False
                continue
            if actual != entry.payload:
                print(f"STALE    {case.id:<30} {entry.stage:<13} {entry.key}")
                ok = False
            else:
                print(f"READY    {case.id:<30} {entry.stage:<13} {entry.key}")
    return ok


def reset_submissions(directory: Path = SUBMISSIONS_DIR) -> int:
    """Clear local persisted submissions only; fixture images are never touched."""
    directory.mkdir(parents=True, exist_ok=True)
    removed = 0
    for path in directory.glob("*.json"):
        if path.is_file():
            path.unlink()
            removed += 1
    print(f"Cleared {removed} local submission file(s) from {directory}.")
    return removed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify all prepared cache entries without writing anything",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="remove and recreate only cache keys owned by the demo manifest",
    )
    parser.add_argument(
        "--reset-submissions",
        action="store_true",
        help="also clear data/submissions/*.json so class analytics starts empty",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        return 0 if check_demo_cache() else 1

    if args.reset_submissions:
        reset_submissions()
    seed_demo_cache(reset=args.reset)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
