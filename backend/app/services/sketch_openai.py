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
            "Distinguish clearly: (A) design decisions that MUST be preserved from visible evidence — including "
            "the model's exact croquis pose/stance and garment silhouette — versus (B) drawing imperfections "
            "that may be professionally refined (wobbly lines, uneven fill, crude shading). "
            "Never invent anatomy, swap left/right, or normalize a dynamic stance into a generic runway pose. "
            "Respond ONLY with valid JSON using keys: "
            "summary (one short exciting sentence about the design concept, not the rough drawing), "
            "polish_bullets (array of 3–5 concise tips for the young designer), "
            "design_identity (object with evidence-backed fields; use null only when not visible: "
            "garment_category, silhouette, pose (short free-text stance summary), neckline, sleeve_type, "
            "sleeve_length, hemline, main_colors, fabric_patterns, accessories, asymmetry_notes, "
            "distinctive_details, pose_lock (object of visible anatomical relationships only; null field "
            "when occluded/uncertain — never invent measurements: torso_orientation, shoulder_alignment, "
            "hip_alignment, supporting_leg, bent_or_lifted_leg, knee_positions, foot_placement, "
            "arm_and_hand_positions, body_asymmetry_and_perspective)), "
            "refine_ok (array of short drawing imperfections that MAY be upgraded — never design decisions "
            "and never pose/stance changes), "
            "image_prompt (one English paragraph for an image EDIT listing ONLY visible design attributes "
            "to preserve: concrete pose relationships from pose_lock, hat/hair, neckline, sleeves, hem, "
            "main colors, fabric patterns, asymmetry, accessories, distinctive details — invent nothing; "
            "do not describe amateur line quality or ask to keep a child sketch look; do not summarize pose "
            "as a generic 'standing front view' when limbs are bent, lifted, crossed, or asymmetric)."
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


# Critical pose relationships first (Issue #39). Order is packing priority.
_POSE_LOCK_FIELD_ORDER = (
    "supporting_leg",
    "bent_or_lifted_leg",
    "foot_placement",
    "knee_positions",
    "arm_and_hand_positions",
    "shoulder_alignment",
    "hip_alignment",
    "torso_orientation",
    "body_asymmetry_and_perspective",
)

_GARMENT_IDENTITY_FIELD_ORDER = (
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

_GENERIC_POSE_PHRASES = frozenset(
    {
        "standing",
        "standing front view",
        "front view",
        "front-facing",
        "upright",
        "neutral stance",
        "fashion pose",
        "elegant fashion pose",
        "runway pose",
        "model pose",
    }
)

# images.edit prompt budget. Evidence is packed as whole facts — never sliced mid-fact.
IMAGE_PROMPT_MAX_CHARS = 3800
_POSE_LOCK_FACT_MAX_CHARS = 220
_GARMENT_FACT_MAX_CHARS = 160
_EVIDENCE_CHUNK_MAX_CHARS = 280


def _is_usable_identity_text(val: Any) -> bool:
    if val is None:
        return False
    text = str(val).strip()
    return bool(text) and text.lower() not in {"null", "none", "n/a", "unknown"}


def _bound_fact(text: str, max_chars: int) -> str:
    """Bound one fact to max_chars without cutting mid-word / mid-sentence fragment."""
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= max_chars:
        return cleaned
    window = cleaned[:max_chars]
    for sep in (". ", "; ", ", ", " "):
        idx = window.rfind(sep)
        if idx >= max(24, max_chars // 3):
            return window[: idx + (0 if sep == " " else 1)].rstrip()
    # Last resort: last whitespace in the window (still not mid-word).
    idx = window.rfind(" ")
    if idx > 0:
        return window[:idx].rstrip()
    return window.rstrip()


def _pack_segments(segments: list[str], budget: int) -> str:
    """Join complete segments in order until budget is exhausted.

    Never truncate a segment mid-text. Oversized single segments are skipped so a
    later shorter critical fact can still pack; once a in-budget segment does not
    fit, packing stops so lower-priority trailing prose cannot displace earlier facts.
    """
    if budget <= 0:
        return ""
    out: list[str] = []
    used = 0
    for seg in segments:
        text = (seg or "").strip()
        if not text:
            continue
        # Drop a single oversized fact rather than slicing mid-sentence.
        if len(text) > budget:
            continue
        need = len(text) + (1 if out else 0)
        if used + need > budget:
            break
        out.append(text)
        used += need
    return " ".join(out)


def _pack_labeled_facts(label: str, facts: list[str], budget: int) -> str:
    """Pack a label only when at least one fact fits (avoids orphan headers)."""
    if not facts or budget <= 0:
        return ""
    label_text = label.strip()
    # Reserve label + space; if label alone cannot fit with one fact, omit group.
    if len(label_text) + 1 >= budget:
        return _pack_segments(facts, budget)
    remaining_after_label = budget - len(label_text) - 1
    packed_facts = _pack_segments(facts, remaining_after_label)
    if not packed_facts:
        return ""
    return f"{label_text} {packed_facts}"


def _pose_lock_facts(identity: dict[str, Any]) -> list[str]:
    """Visible pose_lock facts only — never invent anatomy when fields are null/missing."""
    pose_lock = identity.get("pose_lock")
    if not isinstance(pose_lock, dict) or not pose_lock:
        return []
    facts: list[str] = []
    for key in _POSE_LOCK_FIELD_ORDER:
        val = pose_lock.get(key)
        if not _is_usable_identity_text(val):
            continue
        label = key.replace("_", " ")
        body = _bound_fact(str(val).strip(), _POSE_LOCK_FACT_MAX_CHARS)
        if body:
            facts.append(f"{label}: {body}")
    return facts


def _pose_lock_clause(identity: dict[str, Any]) -> str:
    """Format structured pose_lock relationships for the edit brief."""
    facts = _pose_lock_facts(identity)
    if not facts:
        return ""
    return (
        "POSE LOCK (preserve these visible anatomical relationships exactly; do not normalize): "
        + "; ".join(facts)
        + "."
    )


def _garment_identity_facts(identity: dict[str, Any]) -> list[str]:
    """Garment/design identity facts (pose_lock handled separately for priority packing)."""
    facts: list[str] = []
    has_pose_lock = isinstance(identity.get("pose_lock"), dict) and bool(identity.get("pose_lock"))
    for key in _GARMENT_IDENTITY_FIELD_ORDER:
        val = identity.get(key)
        if not _is_usable_identity_text(val):
            continue
        text = str(val).strip()
        # Prefer structured pose_lock over a generic free-text pose summary.
        if key == "pose" and has_pose_lock and text.lower() in _GENERIC_POSE_PHRASES:
            continue
        body = _bound_fact(text, _GARMENT_FACT_MAX_CHARS)
        if body:
            facts.append(f"{key.replace('_', ' ')}: {body}")
    return facts


def _design_identity_clause(structured: dict[str, Any]) -> str:
    """Fold vision design_identity fields into the edit brief when present."""
    identity = structured.get("design_identity")
    if not isinstance(identity, dict) or not identity:
        return ""
    bits = _garment_identity_facts(identity)
    pose_clause = _pose_lock_clause(identity)
    if pose_clause:
        bits.append(pose_clause)
    if not bits:
        return ""
    return "Preserve these design attributes: " + "; ".join(bits) + "."


def _evidence_chunks(structured: Any, summary: str) -> list[str]:
    """Lower-priority free-text evidence chunks (whole sentences when possible)."""
    evidence = ""
    if isinstance(structured, dict):
        evidence = str(structured.get("image_prompt") or "").strip()
        if not evidence:
            bullets = structured.get("polish_bullets") or structured.get("cleanup_bullets") or []
            if isinstance(bullets, list) and bullets:
                joined = "; ".join(str(b).strip() for b in bullets if str(b).strip())
                evidence = f"{summary}. Design details: {joined}".strip()
    if not evidence:
        evidence = (summary or "Professional fashion illustration of this sketch").strip()
    evidence = " ".join(evidence.split())
    if not evidence:
        return []
    # Split on sentence boundaries when long; each chunk is packed whole or skipped.
    if len(evidence) <= _EVIDENCE_CHUNK_MAX_CHARS:
        return [evidence]
    chunks: list[str] = []
    rest = evidence
    while rest:
        if len(rest) <= _EVIDENCE_CHUNK_MAX_CHARS:
            chunks.append(rest)
            break
        window = rest[:_EVIDENCE_CHUNK_MAX_CHARS]
        cut = -1
        for sep in (". ", "; ", ", "):
            idx = window.rfind(sep)
            if idx >= _EVIDENCE_CHUNK_MAX_CHARS // 3:
                cut = idx + len(sep)
                break
        if cut < 0:
            cut = window.rfind(" ")
        if cut < 0:
            # Pathological no-whitespace blob: skip rather than mid-token slice into the prompt.
            break
        piece = rest[:cut].strip()
        if piece:
            chunks.append(piece)
        rest = rest[cut:].strip()
    return chunks


def _build_image_prompt(structured: Any, summary: str) -> str:
    """Build a professional fashion-illustration edit brief (not a pale wash / child-sketch retain).

    Assembles a fixed instruction frame plus prioritized evidence. Critical pose_lock facts are
    packed before lower-priority garment prose and free-text image_prompt chunks. The budget is
    enforced by omitting whole trailing segments — never by slicing mid-fact.
    """
    identity: dict[str, Any] = {}
    if isinstance(structured, dict):
        raw_identity = structured.get("design_identity")
        if isinstance(raw_identity, dict):
            identity = raw_identity

    pose_facts = _pose_lock_facts(identity)
    garment_facts = _garment_identity_facts(identity)
    evidence_parts = _evidence_chunks(structured, summary)

    lead = (
        "Professionally refine THIS uploaded fashion sketch into a beautiful, polished fashion-design "
        "illustration. The uploaded sketch is the SOURCE OF TRUTH for the designer's creative intent "
        "AND for the model's croquis pose, stance, limb positions, and body proportions. "
    )
    pose_rules = (
        "CRITICAL POSE RULES — professional refinement is NOT a pose rewrite: do NOT straighten bent "
        "limbs; do NOT lower a lifted foot or plant both boots when one foot was raised/angled; do NOT "
        "uncross or newly cross the legs; do NOT change weight distribution or supporting leg; do NOT "
        "reorient the torso, shoulders, or hips; do NOT swap left/right hands or move a hand-on-hip; "
        "do NOT replace the original stance with a generic upright runway pose. "
    )
    preserve = (
        "PRESERVE exactly from visible evidence: garment category, original silhouette, the original "
        "model pose/stance, neckline, sleeve type and length, hemline, main colors, fabric/textile "
        "patterns, asymmetry, accessories (such as hats), and distinctive design details. "
    )
    upgrade = (
        "UPGRADE construction and presentation only: strong clean garment contours; sophisticated "
        "tailoring and garment construction; visible fabric folds, draping, and texture; richer but "
        "faithful colors; crisp repeating textile patterns; clearly defined necklines, sleeves, seams, "
        "and hems; attractive fashion-presentation quality; clean full-body composition on a clean light "
        "presentation background — while keeping the same full-body framing and croquis proportions. "
    )
    bans = (
        "Do NOT retain rough/amateur drawing imperfections. Do NOT apply only a faint watercolor or light "
        "color wash. Do NOT invent a different garment, change the designer's colors, alter the silhouette, "
        "add unnecessary accessories, or make every design look like the same generic fashion outfit. "
    )
    suffix = "Avoid photorealism, photography, CGI, magazine lookbook collage, text, watermark."

    # Fixed instruction frame (without trailing avoid-line) is reserved first so polish/safety
    # language cannot be crowded out by verbose vision text. Pose rules sit immediately after
    # the lead so anti-repose bans are never budget-optional. Evidence packs next by priority;
    # the photorealism avoid-line is always last when budget allows.
    fixed_core = f"{lead}{pose_rules}{preserve}{upgrade}{bans}"
    suffix_budget = len(suffix) + 1  # leading space before suffix
    evidence_budget = max(0, IMAGE_PROMPT_MAX_CHARS - len(fixed_core) - suffix_budget)

    # Priority: pose_lock → garment identity → free-text vision evidence.
    groups = [
        (
            "POSE LOCK (preserve these visible anatomical relationships exactly; do not normalize):",
            pose_facts,
        ),
        ("Garment attributes to preserve:", garment_facts),
        ("Design evidence:", evidence_parts),
    ]
    packed_groups: list[str] = []
    used = 0
    for label, facts in groups:
        room = evidence_budget - used - (1 if packed_groups else 0)
        group_text = _pack_labeled_facts(label, facts, room)
        if not group_text:
            # Try next lower-priority group only if this group had no usable facts.
            if facts:
                # Facts existed but none fit — stop so we do not skip ahead past priority.
                break
            continue
        packed_groups.append(group_text)
        used += len(group_text) + (1 if len(packed_groups) > 1 else 0)

    packed_evidence = " ".join(packed_groups)
    parts = [fixed_core.rstrip()]
    if packed_evidence:
        parts.append(packed_evidence)
    # Always keep the avoid-line when the reserved suffix budget remains (it was reserved above).
    parts.append(suffix)
    return " ".join(parts)


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
    """Issue exactly one images.edit HTTP attempt with the configured model (SDK max_retries=0)."""
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
        # Disable OpenAI SDK automatic retries for this paid image call only.
        # Chat Completions (vision) keeps the client default retry policy.
        result = client.with_options(max_retries=0).images.edit(**kwargs)
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
    """Edit the uploaded sketch into a look image. Exactly one images.edit HTTP attempt when enabled.

    Uses SDK max_retries=0 for the edit call only. When the image model is disabled, returns None.
    When editing is enabled but the sketch is missing or the single edit fails, raises
    SketchCompletionError so the worker reports a genuine failure. Never calls images.generate
    or a secondary edit model.
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
