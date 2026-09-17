"""OpenAI Chat Completions (vision + JSON) for sketch jobs; polish also generates a shareable look image."""

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
from app.storage.local import LocalStorageBackend, is_loopback_url

logger = logging.getLogger(__name__)

SKETCH_JOB_TYPES = frozenset({"sketch_clean", "sketch_polish", "style_suggest"})


def is_configured() -> bool:
    key = (get_settings().openai_api_key or "").strip()
    return bool(key)


def _mime_from_url(url: str) -> str:
    low = url.lower()
    if low.endswith(".jpg") or low.endswith(".jpeg"):
        return "image/jpeg"
    if low.endswith(".webp"):
        return "image/webp"
    return "image/png"


def _fetch_image(url: str) -> tuple[bytes, str]:
    local = LocalStorageBackend().read_public_url(url)
    if local:
        return local, _mime_from_url(url)
    if is_loopback_url(url):
        raise FileNotFoundError(f"loopback image not on disk: {url}")
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
            "You are an expert fashion sketch tutor. The user may attach a rough garment sketch image and/or notes. "
            "Respond ONLY with valid JSON (no markdown fences) using keys: "
            "summary (one sentence), cleanup_bullets (array of 3–7 short actionable tips for cleaner linework, "
            "silhouette, and proportions). Audience: serious design students."
        )
    if job_type == "sketch_polish":
        return (
            "You are a senior fashion design mentor helping kids and teens polish the garment they already drew. "
            "Respond ONLY with valid JSON using keys: "
            "summary (one short exciting sentence for the creator), "
            "polish_bullets (array of 3–5 concise tips). "
            "Do NOT invent garments, jackets, extra layers, or colors that are not in the sketch. "
            "Unpainted / white / paper-colored areas stay light. Keep the same figure gender and pose."
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
    fabric = d.get("fabric")
    if isinstance(fabric, str) and fabric.strip():
        parts.append(
            f"Primary fabric for painted regions only (do not invent extra garments for it): {fabric.strip()}. "
            "Describe realistic material qualities for this fabric."
        )
    figure = _figure_label(job)
    if figure:
        parts.append(
            f"Figure lock: this is a {figure} fashion croquis. Keep that gender, body, and pose."
        )
    pairs = d.get("material_pairs")
    if isinstance(pairs, str) and pairs.strip():
        mapped = []
        for part in pairs.split(";"):
            if not _pair_matches_painted(part, job):
                continue
            bits = part.split(":")
            if len(bits) < 2:
                continue
            c_name, f_name = bits[0].strip(), bits[1].strip()
            hex_code = bits[2].strip() if len(bits) >= 3 else ""
            if c_name and f_name:
                label = f"{c_name}"
                if hex_code:
                    label += f" ink≈{hex_code}"
                mapped.append(f"{label} → {f_name} fabric ({_fabric_render_hint(f_name)})")
        if mapped:
            parts.append(
                "Per-region color→fabric map for colors ACTUALLY painted in the sketch "
                "(ignore any other studio chips):\n- " + "\n- ".join(mapped)
            )
    regions = _color_regions(job)
    if regions:
        listed = "\n- ".join(
            f"{hex_code} at {zone} ({pct}% of painted area)" for hex_code, zone, pct in regions
        )
        parts.append(
            "Measured ink colors in the sketch (STRICT — reproduce each one separately, in the same "
            "place on the figure; never apply a single one of them to the whole outfit):\n- " + listed
        )
    color = d.get("color")
    # With several measured colors a single palette name reads as "recolor everything".
    if isinstance(color, str) and color.strip() and len(regions) <= 1:
        parts.append(f"Color direction from the studio palette: {color.strip()}.")
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


def _color_regions(job: AIJob | None) -> list[tuple[str, str, int]]:
    """Parse Unity's measured ink colors: ``#RRGGBB,zone(+zone),pct`` joined by ``;``."""
    if job is None:
        return []
    raw = (job.input_data or {}).get("color_regions")
    if not isinstance(raw, str) or not raw.strip():
        return []
    out: list[tuple[str, str, int]] = []
    for chunk in raw.split(";"):
        bits = chunk.split(",")
        if len(bits) < 3:
            continue
        hex_code, zone, pct_raw = bits[0].strip(), bits[1].strip(), bits[2].strip()
        if not hex_code or not zone:
            continue
        try:
            pct = int(float(pct_raw))
        except ValueError:
            continue
        out.append((hex_code, zone, pct))
    return out


def _figure_label(job: AIJob | None) -> str:
    if job is None:
        return ""
    raw = str((job.input_data or {}).get("figure") or "").strip().lower()
    if raw in {"male", "man", "men", "boy"}:
        return "male"
    if raw in {"female", "woman", "women", "girl"}:
        return "female"
    return ""


def _hex_rgb(value: str) -> tuple[int, int, int] | None:
    s = value.strip().lstrip("#")
    if len(s) != 6:
        return None
    try:
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    except ValueError:
        return None


def _hex_near(a: str, b: str, tol: int = 90) -> bool:
    ra, rb = _hex_rgb(a), _hex_rgb(b)
    if ra is None or rb is None:
        return False
    return abs(ra[0] - rb[0]) + abs(ra[1] - rb[1]) + abs(ra[2] - rb[2]) <= tol


def _pair_matches_painted(part: str, job: AIJob | None) -> bool:
    """Drop leftover color chips that were tapped but never painted on this sketch."""
    regions = _color_regions(job)
    if not regions:
        return True
    bits = part.split(":")
    hex_code = bits[2].strip() if len(bits) >= 3 else ""
    if not hex_code:
        return True
    return any(_hex_near(hex_code, painted) for painted, _, _ in regions)


def _color_regions_clause(job: AIJob | None) -> str:
    regions = _color_regions(job)
    if not regions:
        return (
            "Keep unpainted / white / paper-colored garment areas light. "
            "Do not invent a jacket or extra layer. "
        )
    listed = "; ".join(f"{hex_code} on the {zone} (~{pct}% of the drawing)" for hex_code, zone, pct in regions)
    return (
        f"The sketch was painted with these exact colors: {listed}. "
        "Keep every one of them on the same body area. "
        "Never unify the outfit under one of these colors. "
        "Unpainted or white/cream paper areas stay light — do not invent a new color or a jacket there. "
    )


def _fabric_from_job(job: AIJob | None) -> str:
    if job is None:
        return ""
    d = job.input_data or {}
    fabric = d.get("fabric")
    if isinstance(fabric, str) and fabric.strip():
        return fabric.strip()
    notes = d.get("notes")
    if isinstance(notes, str) and "Primary fabric chosen by the designer:" in notes:
        try:
            after = notes.split("Primary fabric chosen by the designer:", 1)[1]
            return after.split(".", 1)[0].strip()
        except Exception:
            return ""
    return ""


def _fabric_render_hint(fabric: str) -> str:
    key = fabric.strip().lower()
    hints = {
        "silk": "luxurious silk with soft sheen, fluid drape, and delicate light highlights",
        "denim": "fashion denim with visible twill weave, structured seams, and casual-chic finish",
        "velvet": "rich velvet with deep pile, soft light absorption, and luxe runway depth",
        "glitter": "glam glitter/sparkle fabric with catch-lights and party-fashion energy",
        "leather": "fashion leather with smooth grain, soft specular edges, and modern polish",
        "cotton": "soft fashion cotton with matte folds and clean ready-to-wear texture",
    }
    return hints.get(key, f"realistic {fabric} material with believable drape and surface detail")


def _build_image_prompt(structured: Any, summary: str, job: AIJob | None = None) -> str:
    # Do not paste vision `image_prompt` / polish bullets into the image API.
    # Those often invent a different outfit (jacket, extra colors) and the model
    # follows the words more than the uploaded sketch pixels.
    _ = structured, summary

    fabric = _fabric_from_job(job)
    fabric_clause = ""
    pairs_clause = _material_pairs_clause(job)
    if pairs_clause:
        fabric_clause = pairs_clause
    elif fabric:
        fabric_clause = (
            f"Painted garments use {fabric} — {_fabric_render_hint(fabric)}. "
            "Do not add extra garments just to show this fabric. "
        )

    figure = _figure_label(job)
    figure_clause = ""
    if figure:
        figure_clause = (
            f"The croquis is {figure}. Keep a clearly {figure} body, face, and proportions. "
            "Do not change gender. "
        )

    return (
        "Edit the uploaded fashion sketch. You are a fabric renderer, not a fashion designer. "
        "Keep this exact pose, silhouette, garment count, neckline, sleeves, hem, and painted colors. "
        "Do not add jackets, coats, extra layers, or accessories that are not drawn. "
        "Do not invent a new outfit or a new character. "
        "Unpainted / white / paper-colored garment areas stay white or very light. "
        f"{figure_clause}"
        f"{_color_regions_clause(job)}"
        f"{fabric_clause}"
        "Render the existing garments with realistic fabric, elegant drape, and soft studio lighting. "
        "Full figure visible head-to-toe on a clean light background. "
        "Avoid: merging garments, recoloring regions, adding a jacket, changing gender, "
        "cartoonish fills, text, watermark, collage."
    )[:3800]


def _material_pairs_clause(job: AIJob | None) -> str:
    if job is None:
        return ""
    d = job.input_data or {}
    pairs = d.get("material_pairs")
    if not isinstance(pairs, str) or not pairs.strip():
        return ""
    chunks: list[str] = []
    for part in pairs.split(";"):
        if not _pair_matches_painted(part, job):
            continue
        bits = part.split(":")
        if len(bits) < 2:
            continue
        c_name, f_name = bits[0].strip(), bits[1].strip()
        hex_code = bits[2].strip() if len(bits) >= 3 else ""
        if not c_name or not f_name:
            continue
        color_bit = f"{c_name} ink"
        if hex_code:
            color_bit += f" (approx {hex_code})"
        chunks.append(
            f"Wherever the sketch shows {color_bit}, keep that color family and render that garment "
            f"region in {_fabric_render_hint(f_name)}."
        )
    if not chunks:
        return ""
    return " ".join(chunks) + " "


def _image_edit_file(sketch: bytes, mime: str) -> tuple[str, BytesIO, str]:
    ext = "png"
    if "jpeg" in mime or "jpg" in mime:
        ext = "jpg"
    elif "webp" in mime:
        ext = "webp"
    return (f"sketch.{ext}", BytesIO(sketch), mime or f"image/{ext}")


def _image_gen_attempts(preferred_model: str, preferred_size: str, quality: str) -> list[dict[str, Any]]:
    """Build ordered Images API attempt configs (accounts differ on which models exist)."""
    preferred = (preferred_model or "").strip() or "gpt-image-1"
    size = (preferred_size or "").strip()
    attempts: list[dict[str, Any]] = []

    def add(model: str, size_value: str, *, with_quality: bool = False) -> None:
        kw: dict[str, Any] = {"model": model, "prompt": "", "n": 1, "size": size_value}
        if with_quality:
            kw["quality"] = quality or "standard"
        # Deduplicate by model+size
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

    # Fallbacks for orgs without dall-e-3
    add("gpt-image-1", "1024x1536")
    add("gpt-image-1-mini", "1024x1536")
    add("dall-e-2", "1024x1024")
    return attempts


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
    client: OpenAI,
    job: AIJob,
    prompt: str,
    model: str,
    size: str,
) -> tuple[bytes | None, str]:
    """Prefer Images edits so the output stays tied to the child's sketch pixels."""
    sketch = _raw_sketch_bytes(job)
    if sketch is None:
        logger.warning("OpenAI job %s: no sketch bytes for image edit; refusing text-only generate", job.id)
        return None, ""

    sketch_bytes, mime = sketch
    file_tuple = _image_edit_file(sketch_bytes, mime)
    models = []
    for m in (model, "gpt-image-1", "gpt-image-1-mini"):
        if m and m not in models and m.startswith("gpt-image"):
            models.append(m)

    size_value = size if size in {"1024x1024", "1024x1536", "1536x1024", "auto"} else "1024x1536"
    last_error: Exception | None = None
    for m in models:
        try:
            # Fresh buffer each attempt — SDK may consume the stream.
            img = (file_tuple[0], BytesIO(sketch_bytes), file_tuple[2])
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
            # High fidelity keeps silhouette / garment details from the input sketch.
            # Not supported on gpt-image-1-mini.
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


def _generate_and_store_look_image(client: OpenAI, job: AIJob, structured: Any, summary: str) -> str | None:
    """Generate a shareable look image for sketch_polish; return public URL or None."""
    settings = get_settings()
    model = (settings.openai_image_model or "").strip()
    if model.lower() in {"", "none", "off", "false", "0"}:
        return None

    prompt = _build_image_prompt(structured, summary, job)
    size = (settings.openai_image_size or "1024x1536").strip()

    raw, used_model = _try_edit_look_from_sketch(client, job, prompt, model, size)

    # Never fall back to text-only generate for Magic. That path invents a new look
    # from words and is not chargeable-quality when the user paid for their sketch.
    if not raw:
        logger.warning(
            "OpenAI job %s: sketch edit failed; skipping text-only generate so we do not invent a different look",
            job.id,
        )
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
        max_completion_tokens=1400,
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

    image_url: str | None = None
    if job.job_type == "sketch_polish":
        image_url = _generate_and_store_look_image(client, job, structured, summary)

    return {
        "message": "openai",
        "pipeline": job.job_type,
        "model": model,
        "summary": summary,
        "structured": structured,
        "image_url": image_url,
    }
