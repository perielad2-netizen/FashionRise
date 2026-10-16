"""OpenAI vision + JSON for sketch jobs; polish also edits the child's sketch into a look image."""

from __future__ import annotations

import base64
import json
import logging
import uuid
from io import BytesIO
from typing import Any

import httpx
from openai import OpenAI

from app.core.config import get_settings
from app.models.ai_job import AIJob
from app.storage.local import LocalStorageBackend

logger = logging.getLogger(__name__)

SKETCH_JOB_TYPES = frozenset({"sketch_clean", "sketch_polish", "style_suggest"})

# Chat Completions JSON mode. gpt-6-luna also supports json_schema; we keep json_object
# so Unity continues to read summary / cleanup_bullets / polish_bullets / suggestions
# (and polish's extra image_prompt) without a schema change.
JSON_OBJECT_RESPONSE_FORMAT = {"type": "json_object"}

# Longest-prefix table from official GPT-6 docs. Unknown families fail closed.
# gpt-4o / gpt-4.1 omit reasoning_effort (rollback). Luna/Sol accept "none".
# Astra and GPT-6.1 Sol reject "none" (HTTP 400).
_MODEL_REASONING: tuple[tuple[str, str], ...] = (
    ("gpt-6.1-sol", "no_none"),
    ("gpt-6-luna", "including_none"),
    ("gpt-6-astra", "no_none"),
    ("gpt-6-sol", "including_none"),
    ("gpt-4o", "omit"),
    ("gpt-4.1", "omit"),
    ("gpt-4-", "omit"),
)
_EFFORTS_WITH_NONE = frozenset({"none", "low", "medium", "high", "xhigh", "max"})
_EFFORTS_WITHOUT_NONE = frozenset({"low", "medium", "high", "xhigh", "max"})


class SketchConfigError(ValueError):
    """Sanitized OPENAI_MODEL / OPENAI_REASONING_EFFORT mismatch. No secrets or payloads."""


class SketchCompletionError(RuntimeError):
    """Sanitized completion failure. Worker marks the job failed. No payloads."""


def is_configured() -> bool:
    return bool((get_settings().openai_api_key or "").strip())


def reasoning_family(model: str) -> str:
    """Return omit | including_none | no_none | unknown for a model id / snapshot."""
    name = (model or "").strip().lower()
    if not name:
        return "unknown"
    for prefix, family in _MODEL_REASONING:
        if name == prefix or name.startswith(prefix + "-"):
            return family
    return "unknown"


def resolve_reasoning_effort(model: str, effort: str | None) -> str | None:
    """Effort string to send, or None to omit the field. Raises SketchConfigError."""
    family = reasoning_family(model)
    wanted = (effort or "").strip().lower() or None

    if family == "omit":
        return None

    if family == "unknown":
        raise SketchConfigError(
            "OPENAI_MODEL is not in the known Chat Completions reasoning table; "
            "use gpt-6-luna (or gpt-4o-mini to omit reasoning_effort)"
        )

    if not wanted:
        raise SketchConfigError("OPENAI_REASONING_EFFORT is empty")

    if family == "including_none":
        if wanted not in _EFFORTS_WITH_NONE:
            raise SketchConfigError("OPENAI_REASONING_EFFORT is not supported for this model")
        return wanted

    # no_none: Astra, GPT-6.1 Sol — official docs: none is HTTP 400
    if wanted == "none" or wanted == "minimal":
        raise SketchConfigError(
            "OPENAI_REASONING_EFFORT=none is not supported for this OPENAI_MODEL "
            "(use low, medium, high, xhigh, or max)"
        )
    if wanted not in _EFFORTS_WITHOUT_NONE:
        raise SketchConfigError("OPENAI_REASONING_EFFORT is not supported for this model")
    return wanted


def uses_chat_reasoning_effort(model: str) -> bool:
    """True when this model id may include a Chat Completions reasoning_effort field."""
    return reasoning_family(model) in {"including_none", "no_none"}


def chat_completion_kwargs(
    *,
    model: str,
    messages: list[dict[str, Any]],
    max_completion_tokens: int,
    reasoning_effort: str | None = None,
) -> dict[str, Any]:
    """Build Chat Completions args. Omit or reject reasoning per model family."""
    kwargs: dict[str, Any] = {
        "model": model,
        "response_format": JSON_OBJECT_RESPONSE_FORMAT,
        "messages": messages,
        "max_completion_tokens": max_completion_tokens,
    }
    resolved = resolve_reasoning_effort(model, reasoning_effort)
    if resolved is not None:
        # Official Chat Completions field (not Responses API reasoning.effort).
        kwargs["reasoning_effort"] = resolved
    return kwargs


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


def _raw_sketch_bytes(job: AIJob) -> tuple[bytes, str] | None:
    d = job.input_data or {}
    url = (d.get("image_url") or "").strip()
    if url.startswith("http://") or url.startswith("https://"):
        try:
            return _fetch_image(url)
        except Exception as e:
            logger.warning("OpenAI job %s: could not fetch image_url: %s", job.id, e)
            return None
    b64raw = d.get("image_base64")
    if isinstance(b64raw, str) and b64raw.strip():
        try:
            return _decode_inline_base64(b64raw)
        except Exception as e:
            logger.warning("OpenAI job %s: bad image_base64: %s", job.id, e)
            return None
    return None


def _image_part(job: AIJob) -> dict[str, Any] | None:
    raw = _raw_sketch_bytes(job)
    if raw is None:
        return None
    data, mime = raw
    b64 = base64.b64encode(data).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}


def _system_prompt(job_type: str) -> str:
    if job_type == "sketch_clean":
        return (
            "You are an expert fashion sketch tutor. The user may attach a rough garment sketch and/or notes. "
            "Respond ONLY with valid JSON (no markdown fences) using keys: "
            "summary (one sentence), cleanup_bullets (array of 3–7 short actionable tips)."
        )
    if job_type == "sketch_polish":
        return (
            "You are a senior fashion design mentor helping kids polish a garment sketch. "
            "Respond ONLY with valid JSON using keys: "
            "summary (one short exciting sentence), "
            "polish_bullets (array of 3–5 concise tips), "
            "image_prompt (one short English paragraph listing ONLY what is visible in the sketch: "
            "pose, hat/hair, neckline, sleeves, hem, shapes — for an image EDIT; invent nothing extra)."
        )
    return (
        "You are a fashion stylist AI. Respond ONLY with valid JSON using keys: "
        "summary (one line), suggestions (array of exactly 5 objects with title and description)."
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


def _build_image_prompt(structured: Any, summary: str) -> str:
    prompt = ""
    if isinstance(structured, dict):
        prompt = str(structured.get("image_prompt") or "").strip()
        if not prompt:
            bullets = structured.get("polish_bullets") or structured.get("cleanup_bullets") or []
            if isinstance(bullets, list) and bullets:
                joined = "; ".join(str(b).strip() for b in bullets if str(b).strip())[:600]
                prompt = f"{summary}. Design details: {joined}"
    if not prompt:
        prompt = summary or "Polish this fashion sketch"
    return (
        "Edit THIS uploaded fashion sketch. Keep the SAME pose, body proportions, hat shape, neckline, "
        "sleeve style, hem length, and outfit silhouette. Only clean the linework and add a light color wash. "
        f"{prompt} "
        "Result must still look like the child's sketch — refined fashion croquis on white paper. "
        "Do NOT invent a new character or outfit. Avoid photorealism, photography, CGI, magazine lookbook, "
        "text, watermark, collage."
    )[:3800]


def _extract_image_bytes(item: Any) -> bytes | None:
    url = getattr(item, "url", None)
    b64 = getattr(item, "b64_json", None)
    if url:
        raw, _ = _fetch_image(url)
        return raw
    if b64:
        return base64.b64decode(b64)
    return None


def _try_edit_look_from_sketch(
    client: OpenAI, job: AIJob, prompt: str, model: str, size: str
) -> tuple[bytes | None, str]:
    sketch = _raw_sketch_bytes(job)
    if sketch is None:
        logger.warning("OpenAI job %s: no sketch bytes for image edit", job.id)
        return None, ""

    sketch_bytes, mime = sketch
    ext = "jpg" if ("jpeg" in mime or "jpg" in mime) else "webp" if "webp" in mime else "png"
    models: list[str] = []
    for m in (model, "gpt-image-1", "gpt-image-1-mini"):
        if m and m not in models and str(m).startswith("gpt-image"):
            models.append(m)

    size_value = size if size in {"1024x1024", "1024x1536", "1536x1024", "auto"} else "1024x1536"
    last_error: Exception | None = None
    for m in models:
        try:
            img = (f"sketch.{ext}", BytesIO(sketch_bytes), mime or f"image/{ext}")
            logger.info(
                "OpenAI job %s: editing sketch with %s size=%s (input_fidelity=high)",
                job.id,
                m,
                size_value,
            )
            kwargs: dict[str, Any] = {
                "model": m,
                "image": img,
                "prompt": prompt,
                "size": size_value,
                "n": 1,
            }
            if m == "gpt-image-1" or m.startswith("gpt-image-1.") or m in {"gpt-image-1.5", "gpt-image-2"}:
                kwargs["input_fidelity"] = "high"
            result = client.images.edit(**kwargs)
            raw = _extract_image_bytes(result.data[0])
            if raw:
                return raw, m
            logger.warning("OpenAI job %s: edit via %s returned no image bytes", job.id, m)
        except Exception as e:
            last_error = e
            logger.warning("OpenAI job %s: image edit via %s failed: %s", job.id, m, e)

    if last_error is not None:
        logger.warning("OpenAI job %s: all sketch-edit attempts failed (last: %s)", job.id, last_error)
    return None, ""


def _image_gen_attempts(preferred_model: str, preferred_size: str, quality: str) -> list[dict[str, Any]]:
    preferred = (preferred_model or "").strip() or "gpt-image-1"
    size = (preferred_size or "").strip()
    attempts: list[dict[str, Any]] = []

    def add(model: str, size_value: str, *, with_quality: bool = False) -> None:
        kw: dict[str, Any] = {"model": model, "prompt": "", "n": 1, "size": size_value}
        if with_quality:
            kw["quality"] = quality or "standard"
        key = (model, size_value, with_quality)
        if any((a["model"], a["size"], "quality" in a) == key for a in attempts):
            return
        attempts.append(kw)

    if preferred.startswith("gpt-image"):
        add(preferred, size if size in {"1024x1024", "1024x1536", "1536x1024", "auto"} else "1024x1536")
    elif preferred == "dall-e-3":
        add(preferred, size if size in {"1024x1024", "1024x1792", "1792x1024"} else "1024x1792", with_quality=True)
    elif preferred == "dall-e-2":
        add(preferred, "1024x1024")
    else:
        add(preferred, size or "1024x1024")

    add("gpt-image-1", "1024x1536")
    add("gpt-image-1-mini", "1024x1536")
    add("dall-e-2", "1024x1024")
    return attempts


def _generate_and_store_look_image(client: OpenAI, job: AIJob, structured: Any, summary: str) -> str | None:
    settings = get_settings()
    model = (getattr(settings, "openai_image_model", None) or "gpt-image-1").strip()
    if model.lower() in {"", "none", "off", "false", "0"}:
        return None

    prompt = _build_image_prompt(structured, summary)
    size = (getattr(settings, "openai_image_size", None) or "1024x1536").strip()
    quality = (getattr(settings, "openai_image_quality", None) or "standard").strip()

    raw, used_model = _try_edit_look_from_sketch(client, job, prompt, model, size)

    if not raw:
        last_error: Exception | None = None
        for attempt in _image_gen_attempts(model, size, quality):
            attempt = dict(attempt)
            attempt["prompt"] = prompt
            try:
                logger.info(
                    "OpenAI job %s: fallback generate model %s size=%s",
                    job.id,
                    attempt["model"],
                    attempt.get("size"),
                )
                result = client.images.generate(**attempt)
                raw = _extract_image_bytes(result.data[0])
                if raw:
                    used_model = f"{attempt['model']}(generate)"
                    break
            except Exception as e:
                last_error = e
                logger.warning("OpenAI job %s: image model %s failed: %s", job.id, attempt["model"], e)
        if not raw and last_error is not None:
            logger.warning("OpenAI job %s: all image generation attempts failed (last: %s)", job.id, last_error)

    if not raw:
        return None

    key = f"ai/{job.id.hex if hasattr(job.id, 'hex') else str(job.id).replace('-', '')}_{uuid.uuid4().hex[:10]}.png"
    storage = LocalStorageBackend()
    url = storage.save_file(key=key, data=BytesIO(raw), content_type="image/png")
    logger.info("OpenAI job %s: stored look image via %s → %s", job.id, used_model, url)
    return url


def complete_sketch_job(job: AIJob) -> dict[str, Any]:
    if job.job_type not in SKETCH_JOB_TYPES:
        raise ValueError(f"unsupported job_type {job.job_type!r}")
    settings = get_settings()
    key = (settings.openai_api_key or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    model = settings.openai_model.strip()
    user_content: list[dict[str, Any]] = [{"type": "text", "text": _user_text(job)}]
    img = _image_part(job)
    if img:
        user_content.append(img)

    create_kwargs = chat_completion_kwargs(
        model=model,
        messages=[
            {"role": "system", "content": _system_prompt(job.job_type)},
            {"role": "user", "content": user_content},
        ],
        max_completion_tokens=int(settings.openai_max_completion_tokens),
        reasoning_effort=settings.openai_reasoning_effort,
    )

    client_kwargs: dict[str, Any] = {"api_key": key, "timeout": float(settings.openai_timeout_seconds)}
    bu = (settings.openai_base_url or "").strip()
    if bu:
        client_kwargs["base_url"] = bu
    client = OpenAI(**client_kwargs)
    completion = client.chat.completions.create(**create_kwargs)
    structured, summary, finish_reason, truncated = _parse_chat_completion(completion)

    image_url: str | None = None
    if job.job_type == "sketch_polish":
        # Only a complete, valid JSON object may drive images.edit / images.generate.
        image_url = _generate_and_store_look_image(client, job, structured, summary)

    return {
        "message": "openai",
        "pipeline": job.job_type,
        "model": model,
        "summary": summary,
        "structured": structured,
        "image_url": image_url,
        "finish_reason": finish_reason,
        "truncated": truncated,
    }


def _parse_chat_completion(completion: Any) -> tuple[Any, str, str | None, bool]:
    """Turn a finished Chat Completions result into the Unity-facing payload.

    Incomplete, refused, empty, or non-JSON completions raise SketchCompletionError
    so the worker marks failed and sketch_polish never starts a paid image call.
    Exception text is a short status token — no raw model output.
    """
    if not getattr(completion, "choices", None):
        raise SketchCompletionError("model returned no choices")

    choice = completion.choices[0]
    message = getattr(choice, "message", None)
    finish_reason = getattr(choice, "finish_reason", None)

    refusal = getattr(message, "refusal", None) if message is not None else None
    if isinstance(refusal, str) and refusal.strip():
        raise SketchCompletionError("model refused the request")

    raw = ""
    if message is not None:
        raw = (getattr(message, "content", None) or "").strip()
    if not raw:
        raise SketchCompletionError("model returned an empty completion")

    if finish_reason == "length":
        raise SketchCompletionError("model completion was truncated")

    try:
        structured: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SketchCompletionError("model returned invalid JSON") from exc

    if not isinstance(structured, dict):
        raise SketchCompletionError("model JSON was not an object")

    summary = str(structured.get("summary") or "").strip() or raw[:500]
    return structured, summary, finish_reason, False
