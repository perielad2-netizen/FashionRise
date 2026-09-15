"""Probe which OpenAI image models work for this account (reads backend/.env)."""
from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
import os

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "backend" / ".env")

from openai import OpenAI

key = (os.getenv("OPENAI_API_KEY") or "").strip()
if not key:
    print("NO_KEY")
    sys.exit(1)

client = OpenAI(api_key=key, timeout=120)
prompt = "A simple red dress fashion illustration on white background, no text"

attempts = [
    {"model": "gpt-image-1", "size": "1024x1536", "n": 1},
    {"model": "gpt-image-1", "size": "1024x1024", "n": 1},
    {"model": "gpt-image-1-mini", "size": "1024x1536", "n": 1},
    {"model": "dall-e-2", "size": "1024x1024", "n": 1},
    {"model": "dall-e-3", "size": "1024x1024", "n": 1, "quality": "standard"},
]

for kw in attempts:
    model = kw["model"]
    try:
        print(f"TRY {model} size={kw.get('size')} ...", flush=True)
        r = client.images.generate(prompt=prompt, **kw)
        item = r.data[0]
        has_url = bool(getattr(item, "url", None))
        has_b64 = bool(getattr(item, "b64_json", None))
        print(f"OK  {model} url={has_url} b64={has_b64}")
        break
    except Exception as e:
        print(f"FAIL {model}: {e}")
