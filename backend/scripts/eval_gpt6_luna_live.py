"""Bounded gpt-6-luna Chat Completions eval. Default is DRY RUN (zero network).

Live spend requires BOTH flags:
  python scripts/eval_gpt6_luna_live.py --execute --acknowledge-paid-test

This file is not authorization to spend. Do not call images.edit / images.generate.
Uses the production request builder and completion parser. No database, no email.
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import os
import struct
import subprocess
import sys
import time
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import sketch_openai  # noqa: E402

EVAL_BRANCH = "cursor/openai-gpt6-luna-77c6"
REVIEWED_HEAD = "3b0abb1ff62cd1c9fc1b3ef1d2b41d39057e8332"
EVAL_MODEL = "gpt-6-luna"
EVAL_REASONING_EFFORT = "none"
EVAL_MAX_COMPLETION_TOKENS = 1400
EVAL_IMAGE_MODEL = "off"
MAX_LIVE_REQUESTS = 3
BUDGET_USD = 0.05
LUNA_INPUT_USD_PER_M = 0.10
LUNA_OUTPUT_USD_PER_M = 0.50
SKETCH_WIDTH = 160
SKETCH_HEIGHT = 240

# Terms the synthetic A-line dress sketch is expected to evoke.
_SKETCH_TERMS = (
    "dress",
    "a-line",
    "aline",
    "sleeve",
    "neck",
    "hem",
    "skirt",
    "silhouette",
    "bodice",
    "croquis",
    "garment",
    "hat",
    "neckline",
    "proportion",
    "linework",
)
_FASHION_TERMS = _SKETCH_TERMS + (
    "dart",
    "seam",
    "ease",
    "drape",
    "grainline",
    "bodice",
    "waist",
    "shoulder",
    "armhole",
    "pleat",
    "facing",
    "muslin",
    "toile",
)


class EvalGuardError(RuntimeError):
    """Safety preflight or image-endpoint guard failed. No provider spend implied."""


class _ForbiddenImages:
    def edit(self, *args: Any, **kwargs: Any) -> None:
        raise EvalGuardError("EVAL GUARD: images.edit is forbidden in this harness")

    def generate(self, *args: Any, **kwargs: Any) -> None:
        raise EvalGuardError("EVAL GUARD: images.generate is forbidden in this harness")


def _png_rgb(pixels: list[list[tuple[int, int, int]]]) -> bytes:
    height = len(pixels)
    width = len(pixels[0])
    raw = bytearray()
    for row in pixels:
        raw.append(0)
        for r, g, b in row:
            raw.extend((r, g, b))

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def _blank(w: int, h: int, color: tuple[int, int, int] = (255, 255, 252)) -> list[list[tuple[int, int, int]]]:
    return [[color for _ in range(w)] for _ in range(h)]


def _dot(px: list[list[tuple[int, int, int]]], x: int, y: int, color: tuple[int, int, int], radius: int = 0) -> None:
    h = len(px)
    w = len(px[0])
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx * dx + dy * dy <= radius * radius + 1:
                xx, yy = x + dx, y + dy
                if 0 <= xx < w and 0 <= yy < h:
                    px[yy][xx] = color


def _line(
    px: list[list[tuple[int, int, int]]],
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: tuple[int, int, int],
    *,
    radius: int = 0,
    jitter: int = 0,
) -> None:
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    for i in range(steps + 1):
        t = i / steps
        x = int(round(x0 + (x1 - x0) * t))
        y = int(round(y0 + (y1 - y0) * t))
        if jitter:
            x += ((i * 17) % (2 * jitter + 1)) - jitter
            y += ((i * 13) % (2 * jitter + 1)) - jitter
        _dot(px, x, y, color, radius)


def _ellipse(
    px: list[list[tuple[int, int, int]]],
    cx: int,
    cy: int,
    rx: int,
    ry: int,
    color: tuple[int, int, int],
    *,
    jitter: int = 0,
) -> None:
    for i in range(360):
        ang = math.radians(i)
        x = int(round(cx + rx * math.cos(ang)))
        y = int(round(cy + ry * math.sin(ang)))
        if jitter:
            x += (i % (2 * jitter + 1)) - jitter
            y += ((i * 3) % (2 * jitter + 1)) - jitter
        _dot(px, x, y, color, 0)


def _fashion_croquis(*, rough: bool) -> bytes:
    """Fully synthetic A-line day-dress croquis. Not a customer or production asset."""
    w, h = SKETCH_WIDTH, SKETCH_HEIGHT
    px = _blank(w, h)
    ink = (32, 32, 40)
    j = 2 if rough else 0
    rad = 1 if rough else 0
    # Head + neck
    _ellipse(px, 80, 28, 14, 16, ink, jitter=j)
    _line(px, 80, 44, 80, 58, ink, radius=rad, jitter=j)
    # Shoulders + arms
    _line(px, 48, 62, 112, 62, ink, radius=rad, jitter=j)
    _line(px, 48, 62, 36, 118, ink, radius=rad, jitter=j)
    _line(px, 112, 62, 124, 118, ink, radius=rad, jitter=j)
    # Boat neck + bodice + A-line skirt to knee
    _line(px, 58, 58, 102, 58, ink, radius=rad, jitter=j)
    _line(px, 58, 58, 62, 108, ink, radius=rad, jitter=j)
    _line(px, 102, 58, 98, 108, ink, radius=rad, jitter=j)
    _line(px, 62, 108, 38, 168, ink, radius=rad, jitter=j)
    _line(px, 98, 108, 122, 168, ink, radius=rad, jitter=j)
    _line(px, 38, 168, 122, 168, ink, radius=rad, jitter=j)
    # Short sleeves
    _line(px, 48, 62, 44, 86, ink, radius=rad, jitter=j)
    _line(px, 112, 62, 116, 86, ink, radius=rad, jitter=j)
    # Legs
    _line(px, 70, 168, 66, 220, ink, radius=rad, jitter=j)
    _line(px, 90, 168, 94, 220, ink, radius=rad, jitter=j)
    if rough:
        _line(px, 70, 80, 92, 86, ink, radius=0, jitter=2)
        _line(px, 74, 130, 100, 124, ink, radius=0, jitter=2)
    else:
        _line(px, 62, 108, 98, 108, ink, radius=0, jitter=0)
        _ellipse(px, 80, 22, 18, 8, ink, jitter=0)  # simple hat brim
    return _png_rgb(px)


def _data_url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


@dataclass
class Scenario:
    name: str
    job_type: str
    notes: str
    mood_notes: str = ""
    attach_sketch: bool = False
    rough: bool = False
    image_bytes: bytes | None = field(default=None, repr=False)

    def job(self) -> SimpleNamespace:
        data: dict[str, Any] = {}
        if self.notes:
            data["notes"] = self.notes
        if self.mood_notes:
            data["mood_notes"] = self.mood_notes
        if self.attach_sketch:
            png = self.image_bytes if self.image_bytes is not None else _fashion_croquis(rough=self.rough)
            self.image_bytes = png
            data["image_base64"] = _data_url(png)
        return SimpleNamespace(id=uuid4(), job_type=self.job_type, input_data=data)


def synthetic_scenarios() -> list[Scenario]:
    return [
        Scenario(
            name="sketch_clean",
            job_type="sketch_clean",
            attach_sketch=True,
            rough=True,
            notes=(
                "Synthetic study only — not a customer sketch. Rough kid drawing of an "
                "A-line summer day dress, boat neck, short sleeves, knee hem. Please "
                "advise on cleaner linework, a clearer silhouette, and more believable "
                "head-to-hem proportions."
            ),
        ),
        Scenario(
            name="sketch_polish",
            job_type="sketch_polish",
            attach_sketch=True,
            rough=False,
            notes=(
                "Synthetic portfolio study only — not a customer sketch. Keep the same "
                "A-line dress, boat neck, short sleeves, and knee hem. Suggest "
                "professional presentation improvements a teen fashion student could "
                "apply for a classroom portfolio. Do not invent a new garment."
            ),
        ),
        Scenario(
            name="style_suggest",
            job_type="style_suggest",
            attach_sketch=False,
            notes="Synthetic brief only. Five wearable looks, not costume.",
            mood_notes=(
                "Mood: coastal summer, light linen, ages 10–14, cheerful but not "
                "costume-y. Garment preference: A-line day dress, short sleeves, boat "
                "neck, knee length, optional straw hat. Fabric: washable cotton-linen, "
                "soft pastels, no logos."
            ),
        ),
    ]


def _text_tokens(text: str) -> int:
    # Conservative overestimate (~3 chars/token) for preflight only.
    return max(1, (len(text) + 2) // 3)


def _image_tokens(width: int, height: int) -> int:
    # High-detail tile formula (85 + 170 * tiles) with 2× safety. Not a bill.
    tiles = max(1, math.ceil(width / 512) * math.ceil(height / 512))
    return (85 + 170 * tiles) * 2


def _message_text(messages: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text") or ""))
    return "\n".join(parts)


def _has_vision(messages: list[dict[str, Any]]) -> bool:
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "image_url":
                    return True
    return False


def estimate_request_cost_usd(kwargs: dict[str, Any], *, has_image: bool) -> dict[str, Any]:
    text = _message_text(kwargs["messages"])
    in_tokens = _text_tokens(text)
    if has_image:
        in_tokens += _image_tokens(SKETCH_WIDTH, SKETCH_HEIGHT)
    out_tokens = int(kwargs["max_completion_tokens"])
    usd = (in_tokens * LUNA_INPUT_USD_PER_M + out_tokens * LUNA_OUTPUT_USD_PER_M) / 1_000_000
    return {
        "estimated_input_tokens": in_tokens,
        "budgeted_output_tokens": out_tokens,
        "estimated_usd": round(usd, 6),
        "not_a_billing_guarantee": True,
    }


def sanitize_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Redact data URLs and never include secrets."""
    out = {
        "model": kwargs.get("model"),
        "response_format": kwargs.get("response_format"),
        "max_completion_tokens": kwargs.get("max_completion_tokens"),
        "reasoning_effort": kwargs.get("reasoning_effort"),
        "has_temperature": "temperature" in kwargs,
        "message_roles": [m.get("role") for m in kwargs.get("messages", [])],
        "vision_attached": _has_vision(kwargs.get("messages", [])),
    }
    texts: list[str] = []
    for msg in kwargs.get("messages", []):
        content = msg.get("content")
        if isinstance(content, str):
            texts.append(content[:240])
        elif isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text":
                    texts.append(str(item.get("text") or "")[:240])
                elif item.get("type") == "image_url":
                    url = str((item.get("image_url") or {}).get("url") or "")
                    texts.append(f"[redacted data-url chars={len(url)}]")
    out["text_previews"] = texts
    return out


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True).strip()


def verify_repo_state() -> dict[str, Any]:
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    head = _git("rev-parse", "HEAD")
    if branch != EVAL_BRANCH:
        raise EvalGuardError(f"refusing to run: branch is {branch!r}, expected {EVAL_BRANCH!r}")
    try:
        _git("merge-base", "--is-ancestor", REVIEWED_HEAD, "HEAD")
    except subprocess.CalledProcessError as exc:
        raise EvalGuardError(
            f"refusing to run: reviewed migration SHA {REVIEWED_HEAD} is not an ancestor of {head}"
        ) from exc
    return {"branch": branch, "head": head, "reviewed_ancestor": REVIEWED_HEAD}


def build_scenario_request(scenario: Scenario) -> dict[str, Any]:
    job = scenario.job()
    kwargs = sketch_openai.build_sketch_chat_request(
        job,
        model=EVAL_MODEL,
        reasoning_effort=EVAL_REASONING_EFFORT,
        max_completion_tokens=EVAL_MAX_COMPLETION_TOKENS,
    )
    if kwargs["model"] != EVAL_MODEL:
        raise EvalGuardError("request model is not gpt-6-luna")
    if kwargs.get("reasoning_effort") != EVAL_REASONING_EFFORT:
        raise EvalGuardError("request reasoning_effort is not none")
    if int(kwargs["max_completion_tokens"]) > EVAL_MAX_COMPLETION_TOKENS:
        raise EvalGuardError("max_completion_tokens exceeds 1400")
    if "temperature" in kwargs or "top_p" in kwargs:
        raise EvalGuardError("sampling parameters must not be sent")
    return kwargs


def validate_contract(job_type: str, structured: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(structured, dict):
        return ["structured output is not a JSON object"]
    summary = str(structured.get("summary") or "").strip()
    if not summary:
        errors.append("summary is missing or empty")

    if job_type == "sketch_clean":
        bullets = structured.get("cleanup_bullets")
        if not isinstance(bullets, list) or not (3 <= len(bullets) <= 7):
            errors.append("cleanup_bullets must be an array of 3–7 items")
        elif any(not str(b).strip() for b in bullets):
            errors.append("cleanup_bullets contains an empty item")
    elif job_type == "sketch_polish":
        bullets = structured.get("polish_bullets")
        if not isinstance(bullets, list) or not (3 <= len(bullets) <= 5):
            errors.append("polish_bullets must be an array of 3–5 items")
        elif any(not str(b).strip() for b in bullets):
            errors.append("polish_bullets contains an empty item")
        prompt = structured.get("image_prompt")
        if prompt is None or not str(prompt).strip():
            errors.append("image_prompt is missing or empty")
        elif not any(term in str(prompt).lower() for term in _SKETCH_TERMS):
            errors.append("image_prompt is not relevant to the synthetic A-line dress sketch")
    elif job_type == "style_suggest":
        suggestions = structured.get("suggestions")
        if not isinstance(suggestions, list) or len(suggestions) != 5:
            errors.append("suggestions must be an array of exactly 5 objects")
        else:
            for i, item in enumerate(suggestions):
                if not isinstance(item, dict):
                    errors.append(f"suggestions[{i}] is not an object")
                    continue
                if not str(item.get("title") or "").strip():
                    errors.append(f"suggestions[{i}].title is empty")
                if not str(item.get("description") or "").strip():
                    errors.append(f"suggestions[{i}].description is empty")
    else:
        errors.append(f"unsupported job_type {job_type!r}")
    return errors


def quality_notes(job_type: str, structured: dict[str, Any]) -> dict[str, Any]:
    blob = json.dumps(structured).lower()
    fashion_hits = sorted({term for term in _FASHION_TERMS if term in blob})
    generic = ("nice", "better", "improve", "make it", "good job", "awesome")
    generic_hits = [g for g in generic if g in blob]
    return {
        "fashion_term_hits": fashion_hits,
        "generic_filler_hits": generic_hits,
        "has_professional_vocabulary": len(fashion_hits) >= 2,
        "json_object": True,
        "note": "A valid JSON object alone is not a passing quality result.",
    }


def preflight(scenarios: list[Scenario], requests: list[dict[str, Any]], *, repo: dict[str, Any] | None) -> dict[str, Any]:
    if len(scenarios) != MAX_LIVE_REQUESTS or len(requests) != MAX_LIVE_REQUESTS:
        raise EvalGuardError(f"eval is locked to exactly {MAX_LIVE_REQUESTS} Chat Completions")
    for kwargs in requests:
        if kwargs["model"] != EVAL_MODEL:
            raise EvalGuardError("selected model is not gpt-6-luna")
        if kwargs.get("reasoning_effort") != "none":
            raise EvalGuardError("reasoning_effort must be none")
        if int(kwargs["max_completion_tokens"]) > 1400:
            raise EvalGuardError("max_completion_tokens exceeds 1400")
    estimates = [
        estimate_request_cost_usd(kw, has_image=_has_vision(kw["messages"]))
        for kw in requests
    ]
    total = round(sum(e["estimated_usd"] for e in estimates), 6)
    if total > BUDGET_USD:
        raise EvalGuardError(f"projected estimate ${total} exceeds ${BUDGET_USD} ceiling")
    vision = [_has_vision(kw["messages"]) for kw in requests]
    if not vision[0] or not vision[1] or vision[2]:
        raise EvalGuardError("vision attachments must be clean+polish only")
    return {
        "repo": repo,
        "model": EVAL_MODEL,
        "reasoning_effort": EVAL_REASONING_EFFORT,
        "max_completion_tokens": EVAL_MAX_COMPLETION_TOKENS,
        "image_model": EVAL_IMAGE_MODEL,
        "max_retries": 0,
        "planned_chat_completions": MAX_LIVE_REQUESTS,
        "planned_image_edits": 0,
        "planned_image_generations": 0,
        "database": "not used",
        "email": "not used",
        "production_assets": "none — synthetic PNG croquis generated in-process",
        "vision_attached": vision,
        "per_request_estimates": estimates,
        "estimated_total_usd": total,
        "budget_usd": BUDGET_USD,
        "not_a_billing_guarantee": True,
        "images_guard": "client.images.edit/generate raise EvalGuardError",
    }


def _usage_dict(completion: Any) -> dict[str, Any]:
    usage = getattr(completion, "usage", None)
    if usage is None:
        return {}
    details = getattr(usage, "completion_tokens_details", None)
    reasoning = getattr(details, "reasoning_tokens", None) if details is not None else None
    return {
        "input_tokens": getattr(usage, "prompt_tokens", None),
        "output_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
        "reasoning_tokens": reasoning,
    }


def _actual_cost_usd(usage: dict[str, Any]) -> float | None:
    inp = usage.get("input_tokens")
    out = usage.get("output_tokens")
    if not isinstance(inp, int) or not isinstance(out, int):
        return None
    return round((inp * LUNA_INPUT_USD_PER_M + out * LUNA_OUTPUT_USD_PER_M) / 1_000_000, 6)


def validate_live_flags(execute: bool, acknowledge: bool) -> None:
    if execute and not acknowledge:
        raise EvalGuardError(
            "live mode requires --execute AND --acknowledge-paid-test; "
            "this invocation is not authorization to spend"
        )
    if acknowledge and not execute:
        raise EvalGuardError("--acknowledge-paid-test without --execute is ignored; staying dry-run")


def run_live_scenario(
    scenario: Scenario,
    kwargs: dict[str, Any],
    *,
    create: Callable[..., Any],
) -> dict[str, Any]:
    started = time.monotonic()
    completion = create(**kwargs)
    latency_ms = int((time.monotonic() - started) * 1000)
    structured, summary, finish_reason, truncated = sketch_openai._parse_chat_completion(completion)
    contract_errors = validate_contract(scenario.job_type, structured)
    usage = _usage_dict(completion)
    returned_model = getattr(completion, "model", None)
    result = {
        "scenario": scenario.name,
        "job_type": scenario.job_type,
        "requested_model": kwargs["model"],
        "returned_model": returned_model,
        "finish_reason": finish_reason,
        "truncated": truncated,
        "json_parsed": isinstance(structured, dict),
        "summary": summary,
        "contract_errors": contract_errors,
        "quality": quality_notes(scenario.job_type, structured) if isinstance(structured, dict) else {},
        "usage": usage,
        "estimated_usd_from_usage": _actual_cost_usd(usage),
        "latency_ms": latency_ms,
        "pass": not contract_errors and finish_reason == "stop" and not truncated,
    }
    if contract_errors:
        raise EvalGuardError(f"{scenario.name} contract failed: {contract_errors}")
    if finish_reason != "stop":
        raise EvalGuardError(f"{scenario.name} finish_reason={finish_reason!r}")
    return result


def open_chat_only_client(api_key: str) -> Any:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, max_retries=0, timeout=180.0)
    retries = getattr(client, "max_retries", None)
    if retries != 0:
        raise EvalGuardError(f"max_retries is {retries!r}, expected 0")
    client.images = _ForbiddenImages()
    return client


def env_api_key(environ: dict[str, str] | None = None) -> str:
    env = environ if environ is not None else os.environ
    key = (env.get("OPENAI_API_KEY") or "").strip()
    if not key:
        raise EvalGuardError("OPENAI_API_KEY is not set in the process environment")
    return key


def run_eval(
    *,
    execute: bool = False,
    acknowledge: bool = False,
    skip_git: bool = False,
    chat_create: Callable[..., Any] | None = None,
    environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    if execute and not acknowledge:
        validate_live_flags(True, False)
    if acknowledge and not execute:
        execute = False

    scenarios = synthetic_scenarios()
    requests = [build_scenario_request(s) for s in scenarios]
    repo = None if skip_git else verify_repo_state()
    safety = preflight(scenarios, requests, repo=repo)
    report: dict[str, Any] = {
        "mode": "live" if execute else "dry-run",
        "live_authorization": bool(execute and acknowledge),
        "safety": safety,
        "planned_requests": [sanitize_kwargs(kw) for kw in requests],
        "expected_json_contracts": {
            "sketch_clean": ["summary", "cleanup_bullets (3-7 nonempty)"],
            "sketch_polish": ["summary", "polish_bullets (3-5 nonempty)", "image_prompt relevant to sketch"],
            "style_suggest": ["summary", "suggestions (exactly 5 title+description)"],
        },
        "results": [],
        "live_requests_made": 0,
        "live_image_calls": 0,
        "stopped_reason": None,
    }

    if not execute:
        report["stopped_reason"] = "dry-run default — no network calls"
        return report

    key = env_api_key(environ)
    create = chat_create
    client = None
    if create is None:
        client = open_chat_only_client(key)
        create = client.chat.completions.create

    spent = 0.0
    try:
        for i, (scenario, kwargs) in enumerate(zip(scenarios, requests)):
            remaining_worst = safety["per_request_estimates"][i]["estimated_usd"]
            if spent + remaining_worst > BUDGET_USD:
                raise EvalGuardError(
                    f"next request would exceed ${BUDGET_USD} estimate ceiling "
                    f"(spent_est={spent}, next={remaining_worst})"
                )

            def _counted_create(**kw: Any) -> Any:
                report["live_requests_made"] += 1
                return create(**kw)

            row = run_live_scenario(scenario, kwargs, create=_counted_create)
            report["results"].append(row)
            if row.get("estimated_usd_from_usage") is not None:
                spent += row["estimated_usd_from_usage"]
            else:
                spent += remaining_worst
    except Exception as exc:
        report["stopped_reason"] = f"{type(exc).__name__}: {exc}"
        report["pass"] = False
        raise
    finally:
        report["estimated_spend_usd"] = round(spent, 6)
        report["not_a_billing_guarantee"] = True

    report["pass"] = all(r.get("pass") for r in report["results"]) and report["live_requests_made"] == 3
    return report


def _print_report(report: dict[str, Any]) -> None:
    print("FashionRise — gpt-6-luna bounded eval")
    print(f"  mode: {report['mode']}")
    print(f"  live_authorization: {report['live_authorization']}")
    safety = report["safety"]
    repo = safety.get("repo") or {}
    if repo:
        print(f"  branch: {repo.get('branch')}")
        print(f"  head: {repo.get('head')}")
        print(f"  reviewed_ancestor: {repo.get('reviewed_ancestor')}")
    print(f"  model: {safety['model']}  effort: {safety['reasoning_effort']}  max_tokens: {safety['max_completion_tokens']}")
    print(f"  image_model: {safety['image_model']}  max_retries: {safety['max_retries']}")
    print(f"  planned chat completions: {safety['planned_chat_completions']}")
    print(f"  planned image edit/generate: {safety['planned_image_edits']}/{safety['planned_image_generations']}")
    print(f"  vision attached: {safety['vision_attached']}")
    print(f"  estimated total USD: {safety['estimated_total_usd']}  (NOT a billing guarantee)")
    print(f"  budget ceiling USD: {safety['budget_usd']}")
    print("  planned request parameters:")
    print(json.dumps(report["planned_requests"], indent=2))
    print("  expected JSON contracts:")
    print(json.dumps(report["expected_json_contracts"], indent=2))
    print(f"  live_requests_made: {report['live_requests_made']}")
    if report.get("results"):
        print("  results:")
        print(json.dumps(report["results"], indent=2, default=str))
    if report.get("stopped_reason"):
        print(f"  stopped: {report['stopped_reason']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Make live Chat Completions (requires --acknowledge-paid-test).")
    parser.add_argument(
        "--acknowledge-paid-test",
        action="store_true",
        help="Acknowledge this run may spend a few cents. Not implied by other prompts.",
    )
    parser.add_argument("--json", action="store_true", help="Print the full report as JSON.")
    args = parser.parse_args(argv)

    os.chdir(ROOT)
    try:
        if args.execute and not args.acknowledge_paid_test:
            print(
                "Refusing live run: --execute requires --acknowledge-paid-test. "
                "Default dry-run makes zero network calls.",
                file=sys.stderr,
            )
            return 2
        report = run_eval(execute=args.execute, acknowledge=args.acknowledge_paid_test)
    except (EvalGuardError, sketch_openai.SketchCompletionError, sketch_openai.SketchConfigError) as exc:
        print(f"EVAL GUARD: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        _print_report(report)
    return 0 if report.get("mode") == "dry-run" or report.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
