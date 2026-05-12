"""OpenAI Chat Completions (vision + JSON) for sketch_clean / sketch_polish / style_suggest AI jobs."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

import httpx
from openai import OpenAI

from app.core.config import get_settings
from app.models.ai_job import AIJob

logger = logging.getLogger(__name__)

SKETCH_JOB_TYPES = frozenset({"sketch_clean", "sketch_polish", "style_suggest"})


def is_configured() -> bool:
    key = (get_settings().openai_api_key or "").strip()
    return bool(key)


def _fetch_image(url: str) -> tuple[bytes, str]:
    timeout = float(get_settings().openai_http_timeout_seconds)
    with httpx.Client(timeout=timeout) as client:
        r = client.get(url, follow_redirects=True)
        r.raise_for_status()
        ct = (r.headers.get("content-type") or "image/png").split(";")[0].strip().lower()
        if not ct.startswith("image/"):
            ct = "image/png"
        return r.content, ct


def _decode_inline_base64(data: str) -> tuple[bytes, str]:
    raw = data.strip()
    if raw.startswith("data:"):
        meta, _, b64 = raw.partition(",")
        mime = "image/png"
        if "image/" in meta:
            mime = meta.split(";")[0].split(":")[-1].strip()
        return base64.b64decode(b64), mime
    return base64.b64decode(raw), "image/png"


def _image_part(job: AIJob) -> dict[str, Any] | None:
    d = job.input_data or {}
    url = (d.get("image_url") or "").strip()
    if url.startswith("http://") or url.startswith("https://"):
        try:
            data, mime = _fetch_image(url)
            b64 = base64.b64encode(data).decode("ascii")
            return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
        except Exception as e:
            logger.warning("OpenAI job %s: could not fetch image_url: %s", job.id, e)
            return None
    b64raw = d.get("image_base64")
    if isinstance(b64raw, str) and b64raw.strip():
        try:
            data, mime = _decode_inline_base64(b64raw)
            b64 = base64.b64encode(data).decode("ascii")
            return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
        except Exception as e:
            logger.warning("OpenAI job %s: bad image_base64: %s", job.id, e)
            return None
    return None


def _system_prompt(job_type: str) -> str:
    if job_type == "sketch_clean":
        return (
            "You are an expert fashion sketch tutor. The user may attach a rough garment sketch image and/or notes. "
            "Respond ONLY with valid JSON (no markdown fences) using keys: "
            "summary (one sentence), cleanup_bullets (array of 3–7 short actionable tips for cleaner linework, "
            "silhouette, and proportions). Audience: serious design students."
        )
    if job_type == "sketch_polish":
        return (
            "You are a senior fashion design mentor. Help elevate a garment concept toward a polished portfolio piece. "
            "Respond ONLY with valid JSON using keys: summary (one sentence), polish_bullets (array of 3–7 concise "
            "directions: fabric drama, silhouette refinement, detailing, presentation)."
        )
    return (
        "You are a fashion stylist AI. Use mood notes and optional sketch image. "
        "Respond ONLY with valid JSON using keys: summary (one line), suggestions (array of exactly 5 objects, "
        "each with title and description strings)."
    )


def _user_text(job: AIJob) -> str:
    d = job.input_data or {}
    parts: list[str] = []
    notes = d.get("notes")
    if isinstance(notes, str) and notes.strip():
        parts.append(f"Designer notes:\n{notes.strip()}")
    mood = d.get("mood_notes")
    if isinstance(mood, str) and mood.strip():
        parts.append(f"Mood / direction:\n{mood.strip()}")
    lp = d.get("local_path_placeholder")
    if isinstance(lp, str) and lp.strip() and not (d.get("image_url") or "").strip():
        parts.append(
            "(Client-only path token — not readable on the server; rely on attached image if present.) "
            f"Token: {lp[:180]!r}"
        )
    return "\n\n".join(parts) if parts else "Infer from the attached sketch image only."


def complete_sketch_job(job: AIJob) -> dict[str, Any]:
    if job.job_type not in SKETCH_JOB_TYPES:
        raise ValueError(f"unsupported job_type {job.job_type!r}")
    settings = get_settings()
    key = (settings.openai_api_key or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    kwargs: dict[str, Any] = {"api_key": key, "timeout": float(settings.openai_timeout_seconds)}
    bu = (settings.openai_base_url or "").strip()
    if bu:
        kwargs["base_url"] = bu

    client = OpenAI(**kwargs)
    model = settings.openai_model.strip()
    sys_p = _system_prompt(job.job_type)
    user_text = _user_text(job)
    img = _image_part(job)

    user_content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
    if img:
        user_content.append(img)

    completion = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": sys_p},
            {"role": "user", "content": user_content},
        ],
        max_completion_tokens=1200,
    )

    raw = (completion.choices[0].message.content or "").strip()
    try:
        structured: Any = json.loads(raw)
    except json.JSONDecodeError:
        structured = {"summary": raw[:800], "parse_error": True}

    summary = ""
    if isinstance(structured, dict):
        summary = str(structured.get("summary") or "").strip() or raw[:500]
    else:
        summary = raw[:500]

    return {
        "message": "openai",
        "pipeline": job.job_type,
        "model": model,
        "summary": summary,
        "structured": structured,
        "image_url": None,
    }
