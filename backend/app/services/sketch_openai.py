"""OpenAI vision + JSON for sketch jobs; polish edits the uploaded sketch into a look image."""

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
            "You are a senior fashion design director. A young designer uploaded a rough fashion sketch. "
            "Your job is to extract the DESIGN CONCEPT for a professional fashion-illustration edit. "
            "Distinguish clearly: (A) design decisions that MUST be preserved from visible evidence, versus "
            "(B) drawing imperfections that may be professionally refined (wobbly lines, uneven fill, crude shading). "
            "Respond ONLY with valid JSON using keys: "
            "summary (one short exciting sentence about the design concept, not the rough drawing), "
            "polish_bullets (array of 3–5 concise tips for the young designer), "
            "design_identity (object with evidence-backed fields; use null only when not visible: "
            "garment_category, silhouette, pose, neckline, sleeve_type, sleeve_length, hemline, "
            "main_colors, fabric_patterns, accessories, asymmetry_notes, distinctive_details), "
            "refine_ok (array of short drawing imperfections that MAY be upgraded — never design decisions), "
            "image_prompt (one English paragraph for an image EDIT listing ONLY visible design attributes to preserve: "
            "pose, hat/hair, neckline, sleeves, hem, main colors, fabric patterns, asymmetry, accessories, "
            "distinctive details — invent nothing; do not describe amateur line quality or ask to keep a child sketch look)."
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


def _design_identity_clause(structured: dict[str, Any]) -> str:
    """Fold vision design_identity fields into the edit brief when present."""
    identity = structured.get("design_identity")
    if not isinstance(identity, dict) or not identity:
        return ""
    order = (
        "garment_category",
        "silhouette",
        "pose",
        "neckline",
        "sleeve_type",
        "sleeve_length",
        "hemline",
        "main_colors",
        "fabric_patterns",
        "accessories",
        "asymmetry_notes",
        "distinctive_details",
    )
    bits: list[str] = []
    for key in order:
        val = identity.get(key)
        if val is None:
            continue
        text = str(val).strip()
        if text and text.lower() not in {"null", "none", "n/a", "unknown"}:
            bits.append(f"{key.replace('_', ' ')}: {text}")
    if not bits:
        return ""
    return "Preserve these design attributes: " + "; ".join(bits) + "."


def _build_image_prompt(structured: Any, summary: str) -> str:
    """Build a professional fashion-illustration edit brief (not a pale wash / child-sketch retain)."""
    evidence = ""
    identity_clause = ""
    if isinstance(structured, dict):
        evidence = str(structured.get("image_prompt") or "").strip()
        identity_clause = _design_identity_clause(structured)
        if not evidence:
            bullets = structured.get("polish_bullets") or structured.get("cleanup_bullets") or []
            if isinstance(bullets, list) and bullets:
                joined = "; ".join(str(b).strip() for b in bullets if str(b).strip())[:600]
                evidence = f"{summary}. Design details: {joined}"
    if not evidence:
        evidence = summary or "Professional fashion illustration of this sketch"
    detail_parts = [p for p in (identity_clause, evidence) if p]
    detail = " ".join(detail_parts)
    return (
        "Professionally refine THIS uploaded fashion sketch into a beautiful, polished fashion-design "
        "illustration. The uploaded sketch is the SOURCE OF TRUTH for the designer's creative intent. "
        "PRESERVE exactly from visible evidence: garment category, original silhouette, pose, neckline, "
        "sleeve type and length, hemline, main colors, fabric/textile patterns, asymmetry, accessories "
        "(such as hats), and distinctive design details. "
        "UPGRADE construction and presentation: strong clean garment contours; sophisticated tailoring "
        "and garment construction; visible fabric folds, draping, and texture; richer but faithful colors; "
        "crisp repeating textile patterns; clearly defined necklines, sleeves, seams, and hems; attractive "
        "fashion-presentation quality; clean full-body composition on a clean light presentation background. "
        "Do NOT retain rough/amateur drawing imperfections. Do NOT apply only a faint watercolor or light "
        "color wash. Do NOT invent a different garment, change the designer's colors, alter the silhouette, "
        "add unnecessary accessories, or make every design look like the same generic fashion outfit. "
        f"Design evidence: {detail} "
        "Avoid photorealism, photography, CGI, magazine lookbook collage, text, watermark."
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


def _sanitize_provider_error(exc: BaseException) -> str:
    """Bounded log token: exception class only. Never the provider body (may hold image/secrets)."""
    return type(exc).__name__[:80]


def _supports_input_fidelity(model: str) -> bool:
    m = (model or "").strip()
    return m == "gpt-image-1" or m.startswith("gpt-image-1.") or m in {"gpt-image-1.5", "gpt-image-2"}


def _try_edit_look_from_sketch(
    client: OpenAI,
    job: AIJob,
    prompt: str,
    model: str,
    size: str,
    *,
    sketch: tuple[bytes, str],
) -> tuple[bytes | None, str]:
    """Issue exactly one images.edit with the configured model. No model fanout / generate."""
    sketch_bytes, mime = sketch
    model = (model or "").strip()
    if not model.startswith("gpt-image"):
        logger.warning("OpenAI job %s: image model not eligible for edit", job.id)
        return None, ""

    ext = "jpg" if ("jpeg" in mime or "jpg" in mime) else "webp" if "webp" in mime else "png"
    size_value = size if size in {"1024x1024", "1024x1536", "1536x1024", "auto"} else "1024x1536"
    try:
        img = (f"sketch.{ext}", BytesIO(sketch_bytes), mime or f"image/{ext}")
        logger.info(
            "OpenAI job %s: editing sketch with %s size=%s (input_fidelity=%s)",
            job.id,
            model,
            size_value,
            "high" if _supports_input_fidelity(model) else "omit",
        )
        kwargs: dict[str, Any] = {
            "model": model,
            "image": img,
            "prompt": prompt,
            "size": size_value,
            "n": 1,
        }
        if _supports_input_fidelity(model):
            kwargs["input_fidelity"] = "high"
        result = client.images.edit(**kwargs)
        data = getattr(result, "data", None) or []
        raw = _extract_image_bytes(data[0]) if data else None
        if raw:
            return raw, model
        logger.warning("OpenAI job %s: edit returned no image bytes", job.id)
        return None, ""
    except Exception as e:
        logger.warning(
            "OpenAI job %s: image edit failed type=%s",
            job.id,
            _sanitize_provider_error(e),
        )
        return None, ""


def _generate_and_store_look_image(client: OpenAI, job: AIJob, structured: Any, summary: str) -> str | None:
    """Edit the uploaded sketch into a look image. Exactly one images.edit when enabled.

    When the image model is disabled, returns None. When editing is enabled but the sketch
    is missing or the single edit fails, raises SketchCompletionError so the worker reports
    a genuine failure. Never calls images.generate or a secondary edit model.
    """
    settings = get_settings()
    model = (getattr(settings, "openai_image_model", None) or "gpt-image-1").strip()
    if model.lower() in {"", "none", "off", "false", "0"}:
        return None

    sketch = _raw_sketch_bytes(job)
    if sketch is None:
        raise SketchCompletionError("no sketch image for edit")

    prompt = _build_image_prompt(structured, summary)
    size = (getattr(settings, "openai_image_size", None) or "1024x1536").strip()

    raw, used_model = _try_edit_look_from_sketch(
        client, job, prompt, model, size, sketch=sketch
    )
    if not raw:
        raise SketchCompletionError("sketch image edit failed")

    key = f"ai/{job.id.hex if hasattr(job.id, 'hex') else str(job.id).replace('-', '')}_{uuid.uuid4().hex[:10]}.png"
    storage = LocalStorageBackend()
    url = storage.save_file(key=key, data=BytesIO(raw), content_type="image/png")
    logger.info("OpenAI job %s: stored look image via images.edit/%s → %s", job.id, used_model, url)
    return url


def build_sketch_chat_request(
    job: AIJob,
    *,
    model: str,
    reasoning_effort: str | None,
    max_completion_tokens: int,
) -> dict[str, Any]:
    """Assemble the production Chat Completions payload for a sketch job.

    Shared by the worker and the isolated live-eval harness so request shape
    cannot drift. Does not open a client or call image endpoints.
    """
    if job.job_type not in SKETCH_JOB_TYPES:
        raise ValueError(f"unsupported job_type {job.job_type!r}")
    user_content: list[dict[str, Any]] = [{"type": "text", "text": _user_text(job)}]
    img = _image_part(job)
    if img:
        user_content.append(img)
    return chat_completion_kwargs(
        model=model,
        messages=[
            {"role": "system", "content": _system_prompt(job.job_type)},
            {"role": "user", "content": user_content},
        ],
        max_completion_tokens=int(max_completion_tokens),
        reasoning_effort=reasoning_effort,
    )


def complete_sketch_job(job: AIJob) -> dict[str, Any]:
    if job.job_type not in SKETCH_JOB_TYPES:
        raise ValueError(f"unsupported job_type {job.job_type!r}")
    settings = get_settings()
    key = (settings.openai_api_key or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    model = settings.openai_model.strip()
    create_kwargs = build_sketch_chat_request(
        job,
        model=model,
        reasoning_effort=settings.openai_reasoning_effort,
        max_completion_tokens=int(settings.openai_max_completion_tokens),
    )

    client_kwargs: dict[str, Any] = {"api_key": key, "timeout": float(settings.openai_timeout_seconds)}
    bu = (settings.openai_base_url or "").strip()
    if bu:
        client_kwargs["base_url"] = bu
    client = OpenAI(**client_kwargs)
    completion = client.chat.completions.create(**create_kwargs)
    structured, summary, finish_reason, truncated = _parse_chat_completion(completion)

    image_url: str | None = None
    image_provenance: str | None = None
    if job.job_type == "sketch_polish":
        # Only a complete, valid JSON object may drive images.edit (no generate fallback).
        image_url = _generate_and_store_look_image(client, job, structured, summary)
        if image_url:
            image_provenance = "images.edit"

    return {
        "message": "openai",
        "pipeline": job.job_type,
        "model": model,
        "summary": summary,
        "structured": structured,
        "image_url": image_url,
        "image_provenance": image_provenance,
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
