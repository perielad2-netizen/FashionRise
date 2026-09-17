"""
Quick config check: will sketch / style / tech_pack jobs use OpenAI or the stub?

Run from the backend folder (so .env is found):
  py -3 scripts/check_sketch_ai.py
  py -3 scripts/check_sketch_ai.py --strict   # exit code 1 if OpenAI is not configured
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 if OPENAI_API_KEY is missing (for scripts/CI).",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    os.chdir(root)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    # Fresh read (avoid stale lru_cache if this file is imported elsewhere)
    from app.core.config import get_settings

    get_settings.cache_clear()

    from app.services import sketch_openai, tech_pack_openai

    s = get_settings()
    key = (s.openai_api_key or "").strip()
    ok = sketch_openai.is_configured()
    tech_ok = tech_pack_openai.is_configured()

    print("FashionRise - sketch AI worker")
    print(f"  Working directory: {os.getcwd()}")
    print(f"  OPENAI_API_KEY set: {bool(key)}")
    if key:
        tail = key[-4:] if len(key) >= 4 else key
        print(f"  Key ends with: ...{tail}")
    print(f"  OPENAI_MODEL: {s.openai_model!r}")
    print(f"  sketch_openai.is_configured(): {ok}")
    print(f"  tech_pack_openai.is_configured(): {tech_ok}")
    if ok:
        print("  => sketch_clean / sketch_polish / style_suggest will use OpenAI when jobs are processed.")
    else:
        print("  => Those job types will use the STUB until you set OPENAI_API_KEY in backend/.env.")
    if tech_ok:
        print("  => tech_pack will use OpenAI (+ blueprint images when image model is enabled).")
    else:
        print("  => tech_pack will return a rich demo stub for Unity UI development.")

    if args.strict and not ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
