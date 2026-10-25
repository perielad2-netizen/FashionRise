"""OpenAI vision + JSON for sketch jobs; polish edits the uploaded sketch into a look image."""

from __future__ import annotations

import base64
import json
import logging
import re
import uuid
from dataclasses import dataclass
from io import BytesIO
from typing import Any

import httpx
from openai import OpenAI

from app.core.config import get_settings
from app.models.ai_job import AIJob
from app.services.reference_croquis import (
    edit_reference_instructions,
    reference_from_job_input,
    vision_reference_instructions,
)
from app.storage.local import LocalStorageBackend

logger = logging.getLogger(__name__)

SKETCH_JOB_TYPES = frozenset({"sketch_clean", "sketch_polish", "style_suggest"})

# Chat Completions JSON mode. gpt-6-luna also supports json_schema; we keep json_object
# so Unity continues to read summary / cleanup_bullets / polish_bullets / suggestions
# (and polish's extra image_prompt) without a schema change.
JSON_OBJECT_RESPONSE_FORMAT = {"type": "json_object"}

# Hard budget for the images.edit brief (production maint slice). Protected
# instructions (coverage + non-photoreal illustration style) always fit inside
# this budget; only lower-priority vision prose is bounded to fill the remainder.
IMAGE_PROMPT_MAX_CHARS = 3800

# Fixed garment-coverage contract for adult, non-explicit fashion (Issue #64).
# Distinguishes drawn fabric from exposed skin / croquis body / paper — does not
# alter provider moderation settings or request explicit content.
_COVERAGE_PRESERVATION_CONTRACT = (
    "COVERAGE FIDELITY (adult fashion croquis): Distinguish actual drawn garment "
    "material from exposed skin and from blank/light croquis-body or paper background. "
    "Preserve two-piece and one-piece swimsuits, lingerie/underwear construction, "
    "exposed midriff, cut-outs, straps, necklines, and leg openings exactly as drawn. "
    "Never invent an extra bodysuit, white lining, modesty insert, or coverage panel. "
    "Preserve intentionally drawn white or pale fabric only when garment material is "
    "actually present in the sketch. Do not reinterpret bare skin or croquis body tone "
    "as opaque fabric. When coverage fields are missing, null, unknown, or contradictory, "
    "rely on the uploaded sketch only — do not invent bare-skin regions or extra fabric "
    "panels, and do not automatically make the design more revealing or more covered. "
    "Keep the professional fashion-illustration finish."
)

# Applied-fill color authority — outlines must not become fabric (Dual Magic color fix).
_COLOR_FIDELITY_CONTRACT = (
    "COLOR FIDELITY: Follow applied garment fill/fabric colors from the sketch and any "
    "shared garment-spec main_colors. Black or dark outline strokes are linework, not "
    "fabric fill — do not replace pink, fuchsia, coral, or other applied fill colors with "
    "black unless black fabric was actually drawn as a filled garment region. Keep Front "
    "and Back material colors, straps, cut-outs, and silhouette consistent with the sketch."
)

# Illustration-style restriction — equal priority with coverage; must not be truncated
# away by verbose vision evidence (Issue #64 PM amendment).
_ILLUSTRATION_STYLE_CONTRACT = (
    "Avoid photorealism, photography, CGI, magazine lookbook collage, text, watermark. "
    "Deliver a polished non-photorealistic fashion illustration."
)

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
    """Sanitized completion failure. Worker marks the job failed. No payloads.

    Optional ``safe_meta`` carries allowlisted diagnostic fields only
    (exception class, HTTP status, short provider code, request id, stage).
    Never attach prompts, images, raw provider bodies, or credentials.
    """

    def __init__(self, message: str, *, safe_meta: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.safe_meta = dict(safe_meta or {})


# Strict allowlists for persisted/logged diagnostics (never free-form provider text).
_SAFE_PROVIDER_CODES = frozenset(
    {
        "content_policy_violation",
        "moderation_blocked",
        "invalid_image",
        "invalid_image_format",
        "invalid_image_size",
        "image_too_large",
        "image_parse_error",
        "billing_hard_limit_reached",
        "insufficient_quota",
        "rate_limit_exceeded",
        "model_not_found",
        "unsupported_value",
        "invalid_value",
        "missing_required_parameter",
    }
)

_SAFE_ERROR_CATEGORIES = frozenset(
    {
        "provider_content_policy",
        "provider_quota",
        "provider_rate_limit",
        "provider_auth",
        "provider_unavailable",
        "provider_model_unavailable",
        "provider_bad_request",
        "empty_edit_response",
        "image_edit_failed",
        "sketch_completion_failed",
        "no_sketch_image",
        "retired_image_model",
        "unsupported_image_model",
    }
)

_SAFE_STAGES = frozenset({"images.edit", "chat.completions", "config"})

_SAFE_ERROR_TYPES = frozenset(
    {
        "BadRequestError",
        "AuthenticationError",
        "PermissionDeniedError",
        "NotFoundError",
        "RateLimitError",
        "InternalServerError",
        "APIConnectionError",
        "APITimeoutError",
        "APIStatusError",
        "APIError",
        "EmptyEditResponse",
        "ImageModelNotEligible",
        "NoSketchImage",
        "RetiredImageModel",
        "UnsupportedImageModel",
        "RuntimeError",
        "ValueError",
        "TimeoutError",
        "ProviderError",
    }
)

_CONTENT_POLICY_CODES = frozenset({"content_policy_violation", "moderation_blocked"})
_QUOTA_CODES = frozenset({"billing_hard_limit_reached", "insufficient_quota"})
_MODEL_UNAVAILABLE_CODES = frozenset({"model_not_found"})


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
            "When the user message includes SELECTED STUDIO REFERENCE metadata, that selection is authoritative "
            "over any conflicting impression of the figure's fashion-croquis family (male vs female presentation). "
            "Respond ONLY with valid JSON using keys: "
            "summary (one short exciting sentence about the design concept, not the rough drawing), "
            "polish_bullets (array of 3–5 concise tips for the young designer), "
            "design_identity (object with evidence-backed fields; use null only when not visible: "
            "garment_category, silhouette, pose, neckline, sleeve_type, sleeve_length, hemline, "
            "main_colors, fabric_patterns, accessories, asymmetry_notes, distinctive_details, "
            "skin_visible_regions, garment_panels, cutouts_and_openings, intended_pale_or_white_fabric), "
            "refine_ok (array of short drawing imperfections that MAY be upgraded — never design decisions), "
            "image_prompt (one English paragraph for an image EDIT listing ONLY visible design attributes to preserve: "
            "pose, hat/hair, neckline, sleeves, hem, main colors, fabric patterns, asymmetry, accessories, "
            "distinctive details, garment coverage boundaries, exposed skin/midriff/cut-outs, and any "
            "intentionally drawn white/pale fabric — invent nothing; never invent bodysuits, linings, or "
            "modesty panels; do not treat blank/light croquis body or paper as garment fabric; "
            "do not describe amateur line quality or ask to keep a child sketch look; "
            "do not request a different croquis family than the SELECTED STUDIO REFERENCE)."
        )
    return (
        "You are a fashion stylist AI. Respond ONLY with valid JSON using keys: "
        "summary (one line), suggestions (array of exactly 5 objects with title and description)."
    )


def _normalized_studio_side(input_data: dict[str, Any]) -> str | None:
    raw = input_data.get("studio_side")
    if not isinstance(raw, str) or not raw.strip():
        return None
    return raw.strip().lower()


def _shared_garment_spec_clause(input_data: dict[str, Any]) -> str:
    spec = input_data.get("shared_garment_spec")
    if spec is None:
        return ""
    if isinstance(spec, str) and spec.strip():
        text = spec.strip()
    elif isinstance(spec, dict) and spec:
        try:
            text = json.dumps(spec, ensure_ascii=True, sort_keys=True)
        except (TypeError, ValueError):
            text = str(spec)
    else:
        return ""
    return (
        "SHARED GARMENT SPEC (keep front/back Magic results consistent — do not contradict): "
        f"{text[:1200]}"
    )


def _studio_side_vision_clause(side: str | None) -> str:
    if side == "front":
        return (
            "STUDIO VIEW: FRONT of the garment (viewer-facing). This upload is the front sketch only. "
            "Describe and preserve front-facing design elements. Do NOT describe rear/back-only details "
            "or claim this is a rear view."
        )
    if side == "back":
        return (
            "STUDIO VIEW: REAR / BACK of the garment. This upload is the back sketch only — use neutral "
            "professional fashion-illustration language for adult swimwear and rear garment construction "
            "(dorsal silhouette, back neckline, back straps or ties, rear closures, center-back seams, "
            "rear hem, coverage panels as drawn). Do NOT claim this is the front view, invent front-only "
            "details, or add coverage that is not drawn."
        )
    return ""


def _studio_side_edit_clause(side: str | None) -> str:
    if side == "front":
        return (
            "VIEW: front-facing fashion illustration — preserve front garment details only; "
            "this is not a rear/back view. "
        )
    if side == "back":
        return (
            "VIEW: rear/back fashion illustration of adult swimwear or similar rear garment "
            "construction — show the garment from behind with accurate back necklines, straps or "
            "ties, dorsal seams, and rear hem as drawn; use neutral technical fashion language; "
            "never describe this upload as a front-facing sketch. "
        )
    return ""


def _user_text(job: AIJob) -> str:
    d = job.input_data or {}
    parts: list[str] = []
    if job.job_type == "sketch_polish":
        ref = reference_from_job_input(d if isinstance(d, dict) else {})
        parts.append(vision_reference_instructions(ref))
        side = _normalized_studio_side(d if isinstance(d, dict) else {})
        side_clause = _studio_side_vision_clause(side)
        if side_clause:
            parts.append(side_clause)
        spec_clause = _shared_garment_spec_clause(d if isinstance(d, dict) else {})
        if spec_clause:
            parts.append(spec_clause)
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


def _neutralize_opposite_subject_language(text: str, family: str) -> str:
    """Neutralize opposite-family *subject/figure* claims without stripping garment/hair details."""
    if not text or family not in {"male", "female"}:
        return text
    selected = f"selected {family} fashion croquis"
    if family == "male":
        patterns = (
            (
                r"\bfemale-presenting(?:\s+(?:fashion\s+)?(?:model|figure|croquis))?\b",
                selected,
            ),
            (r"\bfemale(?:\s+fashion)?\s+(?:model|figure|croquis)\b", selected),
            (r"\bwoman(?:\s+model|\s+figure)?\b", selected),
            (r"\bgirl(?:\s+model|\s+figure)?\b", selected),
            (
                r"\bfeminine(?:\s+facial|\s+body|\s+figure|\s+model|\s+presentation)\b",
                f"selected {family} croquis presentation",
            ),
            (r"\ba\s+female\b", f"a {selected}"),
            (r"\bthe\s+female\b", f"the {selected}"),
        )
    else:
        patterns = (
            (
                r"\bmale-presenting(?:\s+(?:fashion\s+)?(?:model|figure|croquis))?\b",
                selected,
            ),
            (r"\bmale(?:\s+fashion)?\s+(?:model|figure|croquis)\b", selected),
            (r"\bman(?:\s+model|\s+figure)?\b", selected),
            (r"\bboy(?:\s+model|\s+figure)?\b", selected),
            (
                r"\bmasculine(?:\s+facial|\s+body|\s+figure|\s+model|\s+presentation)\b",
                f"selected {family} croquis presentation",
            ),
            (r"\ba\s+male\b", f"a {selected}"),
            (r"\bthe\s+male\b", f"the {selected}"),
        )
    out = text
    for pat, replacement in patterns:
        out = re.sub(pat, replacement, out, flags=re.IGNORECASE)
    return out


def _scrub_structured_subject_fields(structured: dict[str, Any], family: str) -> dict[str, Any]:
    out = dict(structured)
    for key in ("image_prompt", "summary"):
        val = out.get(key)
        if isinstance(val, str) and val.strip():
            out[key] = _neutralize_opposite_subject_language(val, family)
    for key in ("polish_bullets", "cleanup_bullets"):
        bullets = out.get(key)
        if isinstance(bullets, list):
            out[key] = [
                _neutralize_opposite_subject_language(item, family) if isinstance(item, str) else item
                for item in bullets
            ]
    identity = out.get("design_identity")
    if isinstance(identity, dict):
        identity = dict(identity)
        for key, val in list(identity.items()):
            if key in {
                "selected_croquis_family",
                "selected_reference_model_id",
                "croquis_presentation",
            }:
                continue
            if isinstance(val, str):
                identity[key] = _neutralize_opposite_subject_language(val, family)
        out["design_identity"] = identity
    return out


def _apply_reference_precedence(structured: Any, job: AIJob | None) -> Any:
    if job is None or not isinstance(structured, dict):
        return structured
    ref = reference_from_job_input(job.input_data if isinstance(job.input_data, dict) else {})
    if ref is None or ref.family is None:
        return structured
    out = _scrub_structured_subject_fields(structured, ref.family)
    identity = out.get("design_identity")
    if not isinstance(identity, dict):
        identity = {}
    else:
        identity = dict(identity)
    identity["selected_croquis_family"] = ref.family
    identity["selected_reference_model_id"] = ref.model_id
    identity["croquis_presentation"] = (
        f"{ref.family} fashion croquis (selected Studio reference `{ref.model_id}`)"
    )
    out["design_identity"] = identity
    return out


def _is_usable_identity_value(val: Any) -> bool:
    if val is None:
        return False
    text = str(val).strip()
    return bool(text) and text.lower() not in {"null", "none", "n/a", "unknown"}


def _design_identity_bits(structured: dict[str, Any]) -> list[str]:
    """Return ordered evidence-backed design_identity labels (skip null/unknown)."""
    identity = structured.get("design_identity")
    if not isinstance(identity, dict) or not identity:
        return []
    order = (
        "croquis_presentation",
        "garment_category",
        "silhouette",
        # Coverage facts early among evidence so they win budget over free-text prose.
        "skin_visible_regions",
        "garment_panels",
        "cutouts_and_openings",
        "intended_pale_or_white_fabric",
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
        if not _is_usable_identity_value(val):
            continue
        bits.append(f"{key.replace('_', ' ')}: {str(val).strip()}")
    return bits


def _design_identity_clause(structured: dict[str, Any]) -> str:
    """Fold vision design_identity fields into the edit brief when present."""
    bits = _design_identity_bits(structured)
    if not bits:
        return ""
    return "Preserve these design attributes: " + "; ".join(bits) + "."


def _bound_at_boundary(text: str, max_chars: int) -> str:
    """Bound lower-priority prose without raising IMAGE_PROMPT_MAX_CHARS.

    Prefers cutting at `;` / sentence / word boundaries. Does not invent content.
    Empty when the budget is exhausted.
    """
    if max_chars <= 0:
        return ""
    text = (text or "").strip()
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    # Leave room for an ellipsis marker when we must cut.
    hard = max_chars - 1 if max_chars > 1 else max_chars
    window = text[:hard]
    for sep in ("; ", ". ", ", ", " "):
        idx = window.rfind(sep)
        if idx >= max(24, hard // 4):
            return window[: idx + len(sep.rstrip())].rstrip() + "…"
    return window.rstrip() + ("…" if max_chars > 1 else "")


def _assemble_design_evidence(
    *,
    identity_bits: list[str],
    free_text: str,
    budget: int,
) -> str:
    """Pack structured identity facts first, then free-text vision notes, within budget."""
    if budget <= 0:
        return ""
    prefix = "Design evidence: "
    remaining = budget - len(prefix)
    if remaining <= 0:
        return ""
    parts: list[str] = []
    if identity_bits:
        identity_block = "Preserve these design attributes: " + "; ".join(identity_bits) + "."
        if len(identity_block) <= remaining:
            parts.append(identity_block)
            remaining -= len(identity_block) + (1 if free_text.strip() else 0)
        else:
            # Keep as many leading fields as fit (field boundary), never inventing coverage.
            kept: list[str] = []
            head = "Preserve these design attributes: "
            used = len(head) + 1  # trailing period
            for bit in identity_bits:
                add = len(bit) + (2 if kept else 0)  # "; " between bits
                if used + add > remaining:
                    break
                kept.append(bit)
                used += add
            if kept:
                parts.append(head + "; ".join(kept) + ".")
                remaining = budget - len(prefix) - len(parts[0]) - (1 if free_text.strip() else 0)
            else:
                remaining = 0
    prose = (free_text or "").strip()
    if prose and remaining > 0:
        bounded = _bound_at_boundary(prose, remaining)
        if bounded:
            parts.append(bounded)
    if not parts:
        return ""
    return prefix + " ".join(parts)


def _build_image_prompt(structured: Any, summary: str, job: AIJob | None = None) -> str:
    """Build a professional fashion-illustration edit brief (production maint prompt + identity).

    Protected instructions (source-of-truth, selected croquis, coverage fidelity, and
    non-photoreal illustration style) always remain intact. Only lower-priority vision
    prose is bounded to fit ``IMAGE_PROMPT_MAX_CHARS``. Does not import undeployed
    PR #41 pose_lock packing and does not raise the global character cap.
    """
    structured = _apply_reference_precedence(structured, job)
    summary_text = summary or ""
    ref = None
    if job is not None:
        ref = reference_from_job_input(job.input_data if isinstance(job.input_data, dict) else {})
        if ref is not None and ref.family is not None:
            summary_text = _neutralize_opposite_subject_language(summary_text, ref.family)
            if isinstance(structured, dict) and isinstance(structured.get("summary"), str):
                summary_text = str(structured.get("summary") or summary_text)

    evidence = ""
    identity_bits: list[str] = []
    if isinstance(structured, dict):
        evidence = str(structured.get("image_prompt") or "").strip()
        if ref is not None and ref.family is not None and evidence:
            evidence = _neutralize_opposite_subject_language(evidence, ref.family)
        identity_bits = _design_identity_bits(structured)
        if not evidence:
            bullets = structured.get("polish_bullets") or structured.get("cleanup_bullets") or []
            if isinstance(bullets, list) and bullets:
                joined = "; ".join(str(b).strip() for b in bullets if str(b).strip())[:600]
                evidence = f"{summary_text}. Design details: {joined}"
    if not evidence and not identity_bits:
        evidence = summary_text or "Professional fashion illustration of this sketch"

    reference_clause = edit_reference_instructions(ref) + " "
    side_clause = ""
    if job is not None:
        side_clause = _studio_side_edit_clause(
            _normalized_studio_side(job.input_data if isinstance(job.input_data, dict) else {})
        )
        shared_edit = _shared_garment_spec_clause(
            job.input_data if isinstance(job.input_data, dict) else {}
        )
        if shared_edit:
            side_clause = f"{side_clause}{shared_edit} "
    protected = (
        "Professionally refine THIS uploaded fashion sketch into a beautiful, polished fashion-design "
        "illustration. The uploaded sketch is the SOURCE OF TRUTH for the designer's creative intent. "
        f"{reference_clause}"
        f"{side_clause}"
        f"{_COVERAGE_PRESERVATION_CONTRACT} "
        f"{_COLOR_FIDELITY_CONTRACT} "
        "PRESERVE exactly from visible evidence: garment category, original silhouette, pose, neckline, "
        "sleeve type and length, hemline, main colors, fabric/textile patterns, asymmetry, accessories "
        "(such as hats), distinctive design details, and the exact garment coverage map (panels vs "
        "exposed skin, cut-outs, straps, openings). "
        "UPGRADE construction and presentation: strong clean garment contours; sophisticated tailoring "
        "and garment construction; visible fabric folds, draping, and texture; richer but faithful colors; "
        "crisp repeating textile patterns; clearly defined necklines, sleeves, seams, and hems; attractive "
        "fashion-presentation quality; clean full-body composition on a clean light presentation background. "
        "Do NOT retain rough/amateur drawing imperfections. Do NOT apply only a faint watercolor or light "
        "color wash. Do NOT invent a different garment, change the designer's colors, alter the silhouette, "
        "add unnecessary accessories, invent white linings/bodysuits/modesty panels, or make every design "
        "look like the same generic fashion outfit. "
        f"{_ILLUSTRATION_STYLE_CONTRACT}"
    )
    # Reserve space for a separating space + design evidence block when budget allows.
    evidence_budget = IMAGE_PROMPT_MAX_CHARS - len(protected) - 1
    evidence_block = _assemble_design_evidence(
        identity_bits=identity_bits,
        free_text=evidence,
        budget=evidence_budget,
    )
    if evidence_block:
        prompt = f"{protected} {evidence_block}"
    else:
        prompt = protected
    if len(prompt) > IMAGE_PROMPT_MAX_CHARS:
        # Defensive: protected alone must fit; never slice mid-instruction.
        prompt = protected[:IMAGE_PROMPT_MAX_CHARS]
    return prompt


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
    """Bounded log token: allowlisted exception class only. Never the provider body."""
    name = type(exc).__name__[:80]
    if name in _SAFE_ERROR_TYPES:
        return name
    return "ProviderError"


def _safe_provider_code(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    code = raw.strip()[:64]
    if not code or code not in _SAFE_PROVIDER_CODES:
        return None
    return code


def _safe_request_id(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    rid = raw.strip()[:128]
    if not rid or len(rid) < 8 or len(rid) > 128:
        return None
    # Correlation ids are typically alnum / hyphen / underscore (OpenAI req_* style).
    if not all(ch.isalnum() or ch in "-_" for ch in rid):
        return None
    return rid


def _safe_error_type_token(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    name = raw.strip()[:80]
    if name in _SAFE_ERROR_TYPES:
        return name
    return None


def _safe_stage_token(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    stage = raw.strip()[:64]
    if stage in _SAFE_STAGES:
        return stage
    return None


def _safe_error_category_token(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    category = raw.strip()[:64]
    if category in _SAFE_ERROR_CATEGORIES:
        return category
    return None


def _safe_provider_error_fields(exc: BaseException) -> dict[str, Any]:
    """Allowlisted provider diagnostics. Never includes message/body/prompt/image bytes."""
    fields: dict[str, Any] = {"error_type": _sanitize_provider_error(exc)}
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and 100 <= status <= 599:
        fields["http_status"] = status
    code = _safe_provider_code(getattr(exc, "code", None))
    if code:
        fields["provider_code"] = code
    request_id = _safe_request_id(getattr(exc, "request_id", None))
    if request_id:
        fields["request_id"] = request_id
    return fields


def normalize_failure_meta(meta: Any) -> dict[str, Any]:
    """Return only allowlisted diagnostic fields suitable for DB/API/logs."""
    if not isinstance(meta, dict) or not meta:
        return {}
    out: dict[str, Any] = {}
    category = _safe_error_category_token(meta.get("error_category"))
    if category:
        out["error_category"] = category
    error_type = _safe_error_type_token(meta.get("error_type"))
    if error_type:
        out["error_type"] = error_type
    status = meta.get("http_status")
    if isinstance(status, int) and 100 <= status <= 599:
        out["http_status"] = status
    code = _safe_provider_code(meta.get("provider_code"))
    if code:
        out["provider_code"] = code
    request_id = _safe_request_id(meta.get("request_id"))
    if request_id:
        out["request_id"] = request_id
    stage = _safe_stage_token(meta.get("stage"))
    if stage:
        out["stage"] = stage
    for bool_key in ("image_edit_attempted", "image_bytes_returned"):
        if bool_key in meta and isinstance(meta[bool_key], bool):
            out[bool_key] = meta[bool_key]
    return out


def failure_result_for_storage(meta: Any) -> dict[str, Any] | None:
    """Worker persistence shape: ``{\"error\": {allowlisted…}}`` or None."""
    cleaned = normalize_failure_meta(meta)
    return {"error": cleaned} if cleaned else None


def _classify_edit_failure(meta: dict[str, Any]) -> str:
    """Map allowlisted fields to a stable error category for UI/ops (not a provider body).

    Ordinary HTTP 400 without a confirmed safety code is never treated as content policy.
    """
    cleaned = normalize_failure_meta(meta)
    if cleaned.get("error_category") in _SAFE_ERROR_CATEGORIES:
        return cleaned["error_category"]  # type: ignore[return-value]
    code = cleaned.get("provider_code")
    status = cleaned.get("http_status")
    error_type = cleaned.get("error_type")
    if code in _CONTENT_POLICY_CODES:
        return "provider_content_policy"
    if code in _QUOTA_CODES:
        return "provider_quota"
    if code in _MODEL_UNAVAILABLE_CODES:
        return "provider_model_unavailable"
    if code == "rate_limit_exceeded" or status == 429 or error_type == "RateLimitError":
        return "provider_rate_limit"
    if status in {401, 403} or error_type in {"AuthenticationError", "PermissionDeniedError"}:
        return "provider_auth"
    if status in {500, 502, 503, 504} or error_type == "InternalServerError":
        return "provider_unavailable"
    if error_type == "EmptyEditResponse":
        return "empty_edit_response"
    if error_type in {"RetiredImageModel", "UnsupportedImageModel", "ImageModelNotEligible"}:
        if error_type == "RetiredImageModel":
            return "retired_image_model"
        return "unsupported_image_model"
    if isinstance(status, int) and 400 <= status < 500:
        return "provider_bad_request"
    if cleaned.get("image_edit_attempted"):
        return "image_edit_failed"
    return "sketch_completion_failed"


def _user_message_for_edit_failure(category: str) -> str:
    """Short, safe user-facing copy. Original sketch is never modified by these failures."""
    if category == "provider_content_policy":
        return (
            "Magic could not edit this sketch under the image provider's safety rules. "
            "Your original design is unchanged. Edit the sketch, then start a new Magic "
            "operation — identical retries are not sent automatically."
        )
    if category == "provider_rate_limit":
        return "Magic is temporarily busy. Your original design is unchanged — try again shortly."
    if category == "provider_quota":
        return "Magic is temporarily unavailable (provider quota). Your original design is unchanged."
    if category == "provider_auth":
        return "Magic is temporarily unavailable. Your original design is unchanged."
    if category in {"provider_unavailable", "provider_model_unavailable"}:
        return "Magic is temporarily unavailable. Your original design is unchanged — try again shortly."
    if category == "retired_image_model":
        return (
            "Magic image editing is temporarily unavailable (image model configuration). "
            "Your original design is unchanged."
        )
    if category == "unsupported_image_model":
        return (
            "Magic image editing is temporarily unavailable (image model configuration). "
            "Your original design is unchanged."
        )
    # Keep the historical generic string for unclassified edit failures (compat + ops grep).
    return "sketch image edit failed"



# Explicit per-model edit capabilities (do not infer from string prefixes alone).
# Sources: OpenAI Images edit API + GPT Image 2.5 / deprecation docs (2026-10).
@dataclass(frozen=True)
class ImageEditCapabilities:
    model_id: str
    status: str  # supported | retired | unsupported
    sizes: frozenset[str]
    qualities: frozenset[str]
    default_quality: str
    output_formats: frozenset[str]
    supports_input_fidelity: bool
    input_fidelity_values: frozenset[str]
    max_n: int


_DEFAULT_IMAGE_MODEL = "gpt-image-2.5-sunburst"
_DEFAULT_IMAGE_SIZE = "1024x1536"

# Exact documented snapshot aliases only (OpenAI model pages). No prefix wildcards.
# Unknown suffix / future IDs fail closed before any billable images.edit.
_IMAGE_EDIT_SNAPSHOT_ALIASES: dict[str, str] = {
    "gpt-image-2.5-sunburst-2026-09-08": "gpt-image-2.5-sunburst",
}

# Qualities FashionRise may send on a paid edit. xhigh/max are API-legal for Sunburst
# but rejected here as a cost/config guard (fail closed, 0 HTTP).
_FASHIONRISE_EDIT_QUALITIES: frozenset[str] = frozenset({"low", "medium", "high", "auto"})

_IMAGE_EDIT_CAPABILITIES: dict[str, ImageEditCapabilities] = {
    "gpt-image-2.5-sunburst": ImageEditCapabilities(
        model_id="gpt-image-2.5-sunburst",
        status="supported",
        sizes=frozenset({"1024x1024", "1024x1536", "1536x1024", "auto"}),
        qualities=frozenset({"low", "medium", "high", "xhigh", "max", "auto"}),
        default_quality="high",
        output_formats=frozenset({"png", "jpeg", "webp"}),
        supports_input_fidelity=False,
        input_fidelity_values=frozenset(),
        max_n=10,
    ),
    "gpt-image-2.5-flare": ImageEditCapabilities(
        model_id="gpt-image-2.5-flare",
        status="supported",
        sizes=frozenset({"1024x1024", "1024x1536", "1536x1024", "auto"}),
        qualities=frozenset({"low", "medium", "high", "xhigh", "max", "auto"}),
        default_quality="high",
        output_formats=frozenset({"png", "jpeg", "webp"}),
        supports_input_fidelity=False,
        input_fidelity_values=frozenset(),
        max_n=10,
    ),
    "gpt-image-2": ImageEditCapabilities(
        model_id="gpt-image-2",
        status="supported",
        sizes=frozenset({"1024x1024", "1024x1536", "1536x1024", "auto"}),
        qualities=frozenset({"low", "medium", "high", "auto"}),
        default_quality="high",
        output_formats=frozenset({"png", "jpeg", "webp"}),
        # Official docs: omit input_fidelity for gpt-image-2 (always high fidelity).
        supports_input_fidelity=False,
        input_fidelity_values=frozenset(),
        max_n=10,
    ),
    "gpt-image-1.5": ImageEditCapabilities(
        model_id="gpt-image-1.5",
        status="supported",
        sizes=frozenset({"1024x1024", "1024x1536", "1536x1024", "auto"}),
        qualities=frozenset({"low", "medium", "high", "auto", "standard"}),
        default_quality="high",
        output_formats=frozenset({"png", "jpeg", "webp"}),
        supports_input_fidelity=True,
        input_fidelity_values=frozenset({"high", "low"}),
        max_n=10,
    ),
    # Retired 2026-10-23 — never issue a paid edit against these ids.
    "gpt-image-1": ImageEditCapabilities(
        model_id="gpt-image-1",
        status="retired",
        sizes=frozenset({"1024x1024", "1024x1536", "1536x1024", "auto"}),
        qualities=frozenset({"low", "medium", "high", "auto", "standard"}),
        default_quality="high",
        output_formats=frozenset({"png", "jpeg", "webp"}),
        supports_input_fidelity=True,
        input_fidelity_values=frozenset({"high", "low"}),
        max_n=10,
    ),
    "gpt-image-1-mini": ImageEditCapabilities(
        model_id="gpt-image-1-mini",
        status="retired",
        sizes=frozenset({"1024x1024", "1024x1536", "1536x1024", "auto"}),
        qualities=frozenset({"low", "medium", "high", "auto", "standard"}),
        default_quality="high",
        output_formats=frozenset({"png", "jpeg", "webp"}),
        supports_input_fidelity=True,
        input_fidelity_values=frozenset({"low"}),
        max_n=10,
    ),
}


def image_edit_capabilities(model: str) -> ImageEditCapabilities | None:
    """Return the capability row for an exact model id or documented snapshot alias only."""
    m = (model or "").strip()
    if not m:
        return None
    if m in _IMAGE_EDIT_CAPABILITIES:
        return _IMAGE_EDIT_CAPABILITIES[m]
    canonical = _IMAGE_EDIT_SNAPSHOT_ALIASES.get(m)
    if canonical is not None:
        return _IMAGE_EDIT_CAPABILITIES.get(canonical)
    return None


def resolve_image_edit_quality(caps: ImageEditCapabilities, configured: str | None) -> str:
    """Resolve FashionRise-allowed edit quality.

    Legacy ``standard`` maps to ``high``. Explicit ``xhigh`` / ``max`` and other
    unexpected values raise before any paid HTTP (no silent premium upgrade, no
    silent fallback to default for unknown strings).
    """
    raw = (configured or "").strip().lower() or caps.default_quality
    if raw == "standard":
        # Documented legacy compatibility (older GPT Image envs used "standard").
        raw = "high"
    if raw in {"xhigh", "max"}:
        raise SketchCompletionError(
            "Magic image editing is temporarily unavailable (image quality configuration). "
            "Your original design is unchanged."
        )
    if raw not in _FASHIONRISE_EDIT_QUALITIES or raw not in caps.qualities:
        raise SketchCompletionError(
            "Magic image editing is temporarily unavailable (image quality configuration). "
            "Your original design is unchanged."
        )
    return raw


def assert_image_model_editable(model: str) -> ImageEditCapabilities:
    """Fail closed before any paid images.edit when the model is retired/unknown."""
    caps = image_edit_capabilities(model)
    if caps is None:
        raise SketchCompletionError(
            "Magic image editing is temporarily unavailable (image model configuration). "
            "Your original design is unchanged.",
            safe_meta=normalize_failure_meta(
                {
                    "stage": "config",
                    "image_edit_attempted": False,
                    "image_bytes_returned": False,
                    "error_category": "unsupported_image_model",
                    "error_type": "UnsupportedImageModel",
                }
            ),
        )
    if caps.status == "retired":
        raise SketchCompletionError(
            "Magic image editing is temporarily unavailable (image model configuration). "
            "Your original design is unchanged.",
            safe_meta=normalize_failure_meta(
                {
                    "stage": "config",
                    "image_edit_attempted": False,
                    "image_bytes_returned": False,
                    "error_category": "retired_image_model",
                    "error_type": "RetiredImageModel",
                }
            ),
        )
    if caps.status != "supported":
        raise SketchCompletionError(
            "Magic image editing is temporarily unavailable (image model configuration). "
            "Your original design is unchanged.",
            safe_meta=normalize_failure_meta(
                {
                    "stage": "config",
                    "image_edit_attempted": False,
                    "image_bytes_returned": False,
                    "error_category": "unsupported_image_model",
                    "error_type": "UnsupportedImageModel",
                }
            ),
        )
    return caps


def build_image_edit_kwargs(
    *,
    model: str,
    prompt: str,
    sketch: tuple[bytes, str],
    size: str,
    quality: str | None,
) -> dict[str, Any]:
    """Construct a single images.edit kwargs dict from the model capability table."""
    configured = (model or "").strip()
    caps = assert_image_model_editable(configured)
    sketch_bytes, mime = sketch
    ext = "jpg" if ("jpeg" in mime or "jpg" in mime) else "webp" if "webp" in mime else "png"
    size_value = size if size in caps.sizes else _DEFAULT_IMAGE_SIZE
    if size_value not in caps.sizes:
        size_value = "1024x1536" if "1024x1536" in caps.sizes else next(iter(sorted(caps.sizes)))
    img = (f"sketch.{ext}", BytesIO(sketch_bytes), mime or f"image/{ext}")
    # Forward the exact allowlisted model id (canonical or documented snapshot).
    kwargs: dict[str, Any] = {
        "model": configured,
        "image": img,
        "prompt": prompt,
        "size": size_value,
        "n": 1,
    }
    q = resolve_image_edit_quality(caps, quality)
    kwargs["quality"] = q
    if "png" in caps.output_formats:
        kwargs["output_format"] = "png"
    # Only set input_fidelity when the capability table explicitly allows it.
    if caps.supports_input_fidelity and "high" in caps.input_fidelity_values:
        kwargs["input_fidelity"] = "high"
    return kwargs


def _try_edit_look_from_sketch(
    client: OpenAI,
    job: AIJob,
    prompt: str,
    model: str,
    size: str,
    *,
    sketch: tuple[bytes, str],
    quality: str | None = None,
) -> tuple[bytes | None, str, dict[str, Any]]:
    """Issue exactly one images.edit HTTP attempt with the configured model (SDK max_retries=0)."""
    model = (model or "").strip()
    try:
        kwargs = build_image_edit_kwargs(
            model=model,
            prompt=prompt,
            sketch=sketch,
            size=size,
            quality=quality,
        )
    except SketchCompletionError:
        raise
    except Exception:
        logger.warning("OpenAI job %s: image model not eligible for edit", job.id)
        return None, "", {
            "stage": "images.edit",
            "image_edit_attempted": False,
            "image_bytes_returned": False,
            "error_type": "ImageModelNotEligible",
        }

    fidelity = kwargs.get("input_fidelity", "omit")
    try:
        logger.info(
            "OpenAI job %s: editing sketch with %s size=%s quality=%s output_format=%s input_fidelity=%s",
            job.id,
            kwargs.get("model"),
            kwargs.get("size"),
            kwargs.get("quality"),
            kwargs.get("output_format"),
            fidelity,
        )
        # Disable OpenAI SDK automatic retries for this paid image call only.
        # Chat Completions (vision) keeps the client default retry policy.
        result = client.with_options(max_retries=0).images.edit(**kwargs)
        data = getattr(result, "data", None) or []
        raw = _extract_image_bytes(data[0]) if data else None
        if raw:
            return raw, str(kwargs.get("model") or model), {}
        logger.warning("OpenAI job %s: edit returned no image bytes", job.id)
        return None, "", {
            "stage": "images.edit",
            "image_edit_attempted": True,
            "image_bytes_returned": False,
            "error_type": "EmptyEditResponse",
        }
    except SketchCompletionError:
        raise
    except Exception as exc:
        fields = _safe_provider_error_fields(exc)
        logger.warning(
            "OpenAI job %s: image edit failed type=%s status=%s code=%s request_id=%s",
            job.id,
            fields.get("error_type"),
            fields.get("http_status"),
            fields.get("provider_code"),
            fields.get("request_id"),
        )
        return None, "", {
            "stage": "images.edit",
            "image_edit_attempted": True,
            "image_bytes_returned": False,
            **fields,
        }


def _generate_and_store_look_image(client: OpenAI, job: AIJob, structured: Any, summary: str) -> str | None:
    """Edit the uploaded sketch into a look image. Exactly one images.edit HTTP attempt when enabled.

    Uses SDK max_retries=0 for the edit call only. When the image model is disabled, returns None.
    When editing is enabled but the sketch is missing or the single edit fails, raises
    SketchCompletionError so the worker reports a genuine failure. Never calls images.generate
    or a secondary edit model. Retired models fail closed before any paid edit HTTP call.
    """
    settings = get_settings()
    model = (getattr(settings, "openai_image_model", None) or _DEFAULT_IMAGE_MODEL).strip()
    if model.lower() in {"", "none", "off", "false", "0"}:
        return None

    # Fail closed before sketch decode work when the configured model cannot be edited.
    assert_image_model_editable(model)

    sketch = _raw_sketch_bytes(job)
    if sketch is None:
        raise SketchCompletionError(
            "no sketch image for edit",
            safe_meta=normalize_failure_meta(
                {
                    "stage": "images.edit",
                    "image_edit_attempted": False,
                    "image_bytes_returned": False,
                    "error_category": "no_sketch_image",
                    "error_type": "NoSketchImage",
                }
            ),
        )

    prompt = _build_image_prompt(structured, summary, job=job)
    size = (getattr(settings, "openai_image_size", None) or _DEFAULT_IMAGE_SIZE).strip()
    quality = getattr(settings, "openai_image_quality", None)

    raw, used_model, fail_meta = _try_edit_look_from_sketch(
        client, job, prompt, model, size, sketch=sketch, quality=quality
    )
    if not raw:
        category = _classify_edit_failure(fail_meta)
        raise SketchCompletionError(
            _user_message_for_edit_failure(category),
            safe_meta=normalize_failure_meta({**fail_meta, "error_category": category}),
        )

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
