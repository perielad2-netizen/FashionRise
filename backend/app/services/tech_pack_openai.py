"""OpenAI vision + JSON tech pack pipeline; rich stub when OPENAI_API_KEY is unset."""

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

TECH_PACK_JOB_TYPES = frozenset({"tech_pack", "sketch_tech_pack"})

DISCLAIMER = "Draft measurements — not final manufacturing specs."

SECTIONS = ["design", "measurements", "pattern", "cutting", "materials", "construction"]

_SYSTEM_PROMPT = (
    "You are a technical fashion designer producing a first-draft tech pack for students. "
    "Analyze the attached polished look or sketch image plus designer notes. "
    "Respond ONLY with valid JSON (no markdown fences) using exactly these keys:\n"
    "- summary: one sentence describing the garment and construction approach\n"
    "- garment: object with type (string), construction_description (string), silhouette (string), "
    "neckline (string), sleeves (string), closure (string)\n"
    "- measurements: object with body (object of cm measurements for sample model 170cm tall, "
    "bust 84 / waist 64 / hip 90), finished (object of finished garment measurements in cm: "
    "bust, waist, hip, length, sleeve_length as applicable), sample_size (string e.g. 'EU 36 / US 4')\n"
    "- materials: array of objects each with name, role (shell|lining|interfacing|notion), "
    "recommendation, quantity_m (number meters for 150cm fabric width, or null for notions), "
    "notes (string)\n"
    "- pattern_pieces: array of objects each with name, qty, approx_w_cm, approx_h_cm, "
    "seam_allowance_cm, grainline (string), on_fold (boolean), notches (array of short strings)\n"
    "- construction_steps: array of short ordered sewing/assembly instruction strings\n"
    "- cutting_layout: object with notes (string), fabric_width_cm (number, typically 150), "
    "efficiency_tip (string)\n"
    "- special_instructions: array of short construction tips (zippers, facings, finishes)\n"
    "- front_flat_prompt: one English paragraph for a clean technical FRONT flat sketch "
    "(blueprint/fashion tech-pack style, black lines on white, no model, no shading text)\n"
    "- back_flat_prompt: same for BACK flat\n"
    "- pattern_overview_prompt: one English paragraph describing a clean pattern-piece layout "
    "diagram (labeled pieces, grainlines, notches) suitable for image generation\n"
    "Audience: kids/teens learning fashion — clear language, realistic first-draft numbers."
)


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


def _source_image_bytes(job: AIJob) -> tuple[bytes, str] | None:
    """Prefer polished look URL, then sketch image_url / image_base64 (mirrors polish input_data)."""
    d = job.input_data or {}
    for key in ("polished_image_url", "image_url"):
        url = d.get(key)
        if isinstance(url, str) and url.strip().startswith(("http://", "https://")):
            try:
                return _fetch_image(url.strip())
            except Exception as e:
                logger.warning("Tech pack job %s: could not fetch %s: %s", job.id, key, e)
    b64raw = d.get("image_base64")
    if isinstance(b64raw, str) and b64raw.strip():
        try:
            return _decode_inline_base64(b64raw)
        except Exception as e:
            logger.warning("Tech pack job %s: bad image_base64: %s", job.id, e)
    return None


def _image_part(job: AIJob) -> dict[str, Any] | None:
    raw = _source_image_bytes(job)
    if raw is None:
        return None
    data, mime = raw
    b64 = base64.b64encode(data).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}


def _user_text(job: AIJob) -> str:
    d = job.input_data or {}
    parts: list[str] = [
        "Produce a first-draft tech pack. Sample body baseline is fixed: height 170 cm, "
        "bust 84 cm, waist 64 cm, hip 90 cm (EU 36 / US 4). "
        "Finished garment measurements should include ease appropriate to the silhouette."
    ]
    notes = d.get("notes")
    if isinstance(notes, str) and notes.strip():
        parts.append(f"Designer notes:\n{notes.strip()}")
    fabric = d.get("fabric")
    if isinstance(fabric, str) and fabric.strip():
        parts.append(f"Primary fabric direction: {fabric.strip()}.")
    color = d.get("color")
    if isinstance(color, str) and color.strip():
        parts.append(f"Color direction: {color.strip()}.")
    pairs = d.get("material_pairs")
    if isinstance(pairs, str) and pairs.strip():
        parts.append(f"Color→fabric map from studio: {pairs.strip()}")
    elif isinstance(pairs, list) and pairs:
        parts.append(f"Color→fabric map from studio: {json.dumps(pairs)}")
    if (d.get("polished_image_url") or "").strip():
        parts.append("Attached image is the polished look — derive flats and pattern from it.")
    return "\n\n".join(parts)


def stub_tech_pack(job: AIJob | None = None) -> dict[str, Any]:
    """Rich demo tech pack so Unity UI can develop without OpenAI."""
    d = (job.input_data if job else None) or {}
    fabric = d.get("fabric") if isinstance(d.get("fabric"), str) and d.get("fabric") else "mid-weight cotton twill"
    color = d.get("color") if isinstance(d.get("color"), str) and d.get("color") else "studio neutrals"
    notes = d.get("notes") if isinstance(d.get("notes"), str) else ""
    garment_hint = "dress" if "dress" in (notes or "").lower() else "blouse and skirt set"
    summary = (
        f"Demo tech pack for a {garment_hint} in {fabric} ({color}) — "
        "first production draft for UI development."
    )
    return {
        "message": "stub",
        "pipeline": (job.job_type if job else "tech_pack"),
        "summary": summary,
        "disclaimer": DISCLAIMER,
        "garment": {
            "type": garment_hint,
            "construction_description": (
                "Princess-seam bodice with set-in sleeves, invisible CB zipper, "
                "and a gently flared skirt/hem with 3 cm blind hem."
            ),
            "silhouette": "semi-fitted A-line",
            "neckline": "soft V or jewel (from sketch)",
            "sleeves": "set-in short or 3/4 length",
            "closure": "invisible zipper at center back",
        },
        "measurements": {
            "body": {
                "height_cm": 170,
                "bust_cm": 84,
                "waist_cm": 64,
                "hip_cm": 90,
                "shoulder_cm": 12.5,
                "back_length_cm": 40,
            },
            "finished": {
                "bust_cm": 92,
                "waist_cm": 72,
                "hip_cm": 98,
                "length_cm": 95,
                "sleeve_length_cm": 45,
                "hem_circumference_cm": 140,
            },
            "sample_size": "EU 36 / US 4",
        },
        "materials": [
            {
                "name": fabric if isinstance(fabric, str) else "cotton twill",
                "role": "shell",
                "recommendation": "150 cm wide mid-weight woven with slight body",
                "quantity_m": 1.8,
                "notes": "Allow extra for nap/print matching if needed",
            },
            {
                "name": "lightweight lining",
                "role": "lining",
                "recommendation": "acetate or soft polyester lining",
                "quantity_m": 1.4,
                "notes": "Bodice and skirt lining as design requires",
            },
            {
                "name": "fusible interfacing",
                "role": "interfacing",
                "recommendation": "light fusible woven",
                "quantity_m": 0.4,
                "notes": "Facings, collar, zipper shield",
            },
            {
                "name": "invisible zipper",
                "role": "notion",
                "recommendation": "55–60 cm invisible zipper matching shell",
                "quantity_m": None,
                "notes": "Center back",
            },
            {
                "name": "hooks / thread",
                "role": "notion",
                "recommendation": "matching polyester thread; optional neck hook",
                "quantity_m": None,
                "notes": "Standard notions kit",
            },
        ],
        "pattern_pieces": [
            {
                "name": "Front bodice",
                "qty": 1,
                "approx_w_cm": 28,
                "approx_h_cm": 42,
                "seam_allowance_cm": 1.5,
                "grainline": "parallel to CF",
                "on_fold": True,
                "notches": ["bust", "side seam", "waist"],
            },
            {
                "name": "Back bodice",
                "qty": 2,
                "approx_w_cm": 24,
                "approx_h_cm": 42,
                "seam_allowance_cm": 1.5,
                "grainline": "parallel to CB",
                "on_fold": False,
                "notches": ["shoulder", "side seam", "waist", "zipper"],
            },
            {
                "name": "Sleeve",
                "qty": 2,
                "approx_w_cm": 36,
                "approx_h_cm": 48,
                "seam_allowance_cm": 1.5,
                "grainline": "center grain",
                "on_fold": False,
                "notches": ["front sleeve", "back sleeve", "underarm"],
            },
            {
                "name": "Skirt front",
                "qty": 1,
                "approx_w_cm": 50,
                "approx_h_cm": 58,
                "seam_allowance_cm": 1.5,
                "grainline": "parallel to CF",
                "on_fold": True,
                "notches": ["waist", "side seam", "hem"],
            },
            {
                "name": "Skirt back",
                "qty": 2,
                "approx_w_cm": 40,
                "approx_h_cm": 58,
                "seam_allowance_cm": 1.5,
                "grainline": "parallel to CB",
                "on_fold": False,
                "notches": ["waist", "side seam", "hem", "zipper"],
            },
            {
                "name": "Neck facing",
                "qty": 1,
                "approx_w_cm": 32,
                "approx_h_cm": 8,
                "seam_allowance_cm": 1.0,
                "grainline": "as marked",
                "on_fold": True,
                "notches": ["shoulder", "CF"],
            },
        ],
        "construction_steps": [
            "Staystitch neckline and apply fusible interfacing to facings.",
            "Sew darts/princess seams on front and back bodice; press toward CF/CB.",
            "Join shoulder seams; set sleeves into armscyes; sew side and underarm seams.",
            "Assemble skirt panels; insert invisible zipper at center back through bodice and skirt.",
            "Attach skirt to bodice at waist; finish with lining or facing as designed.",
            "Hem sleeves and skirt (blind hem ~3 cm); press and final clean.",
        ],
        "cutting_layout": {
            "notes": (
                "Lay shell fabric single or folded as piece on_fold flags require. "
                "Align grainlines to selvage; keep nap consistent. Cut notions separately."
            ),
            "fabric_width_cm": 150,
            "efficiency_tip": "Nest large skirt panels first, then bodice and sleeves in remaining bays.",
        },
        "special_instructions": [
            "Clip curves at neckline; understitch facing.",
            "Use invisible zipper foot; grade CB seam allowances.",
            "Measurements are a first production draft — edit later for fit.",
        ],
        "image_url": None,
        "back_image_url": None,
        "pattern_image_url": None,
        "sections": list(SECTIONS),
        "input_echo": d if job else {},
    }


def _normalize_result(structured: dict[str, Any], *, pipeline: str, model: str | None) -> dict[str, Any]:
    garment = structured.get("garment") if isinstance(structured.get("garment"), dict) else {}
    measurements = structured.get("measurements") if isinstance(structured.get("measurements"), dict) else {}
    body = measurements.get("body") if isinstance(measurements.get("body"), dict) else {}
    finished = measurements.get("finished") if isinstance(measurements.get("finished"), dict) else {}
    # Ensure sample baseline is present even if the model omitted it.
    body = {
        "height_cm": body.get("height_cm", 170),
        "bust_cm": body.get("bust_cm", 84),
        "waist_cm": body.get("waist_cm", 64),
        "hip_cm": body.get("hip_cm", 90),
        **{k: v for k, v in body.items() if k not in {"height_cm", "bust_cm", "waist_cm", "hip_cm"}},
    }
    materials = structured.get("materials") if isinstance(structured.get("materials"), list) else []
    pieces = structured.get("pattern_pieces") if isinstance(structured.get("pattern_pieces"), list) else []
    steps = structured.get("construction_steps") if isinstance(structured.get("construction_steps"), list) else []
    special = structured.get("special_instructions") if isinstance(structured.get("special_instructions"), list) else []
    if special:
        steps = list(steps) + [f"Special: {s}" for s in special if str(s).strip()]
    cutting = structured.get("cutting_layout") if isinstance(structured.get("cutting_layout"), dict) else {}
    summary = str(structured.get("summary") or "").strip() or "Tech pack draft generated from look/sketch."

    out: dict[str, Any] = {
        "message": "openai" if model else "stub",
        "pipeline": pipeline,
        "summary": summary,
        "disclaimer": DISCLAIMER,
        "garment": garment,
        "measurements": {
            "body": body,
            "finished": finished,
            "sample_size": str(measurements.get("sample_size") or "EU 36 / US 4"),
        },
        "materials": materials,
        "pattern_pieces": pieces,
        "construction_steps": steps,
        "cutting_layout": cutting,
        "image_url": None,
        "back_image_url": None,
        "pattern_image_url": None,
        "sections": list(SECTIONS),
        "front_flat_prompt": str(structured.get("front_flat_prompt") or "").strip() or None,
        "back_flat_prompt": str(structured.get("back_flat_prompt") or "").strip() or None,
        "pattern_overview_prompt": str(structured.get("pattern_overview_prompt") or "").strip() or None,
    }
    if model:
        out["model"] = model
    return out


def _store_png(job: AIJob, raw: bytes, label: str) -> str:
    key = (
        f"ai/{job.id.hex if hasattr(job.id, 'hex') else str(job.id).replace('-', '')}"
        f"_techpack_{label}_{uuid.uuid4().hex[:8]}.png"
    )
    storage = LocalStorageBackend()
    return storage.save_file(key=key, data=BytesIO(raw), content_type="image/png")


def _extract_image_bytes(item: Any) -> bytes | None:
    url = getattr(item, "url", None)
    b64 = getattr(item, "b64_json", None)
    if url:
        raw, _ = _fetch_image(url)
        return raw
    if b64:
        return base64.b64decode(b64)
    return None


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
        add(preferred, size if size in {"1024x1024", "1024x1536", "1536x1024", "auto"} else "1024x1024")
    elif preferred == "dall-e-3":
        add(preferred, size if size in {"1024x1024", "1024x1792", "1792x1024"} else "1024x1024", with_quality=True)
    elif preferred == "dall-e-2":
        add(preferred, "1024x1024")
    else:
        add(preferred, size or "1024x1024")

    add("gpt-image-1", "1024x1024")
    add("gpt-image-1-mini", "1024x1024")
    add("dall-e-2", "1024x1024")
    return attempts


def _try_edit_blueprint(
    client: OpenAI,
    job: AIJob,
    prompt: str,
    model: str,
) -> bytes | None:
    source = _source_image_bytes(job)
    if source is None:
        return None
    sketch_bytes, mime = source
    ext = "png"
    if "jpeg" in mime or "jpg" in mime:
        ext = "jpg"
    elif "webp" in mime:
        ext = "webp"
    models: list[str] = []
    for m in (model, "gpt-image-1", "gpt-image-1-mini"):
        if m and m not in models and m.startswith("gpt-image"):
            models.append(m)
    for m in models:
        try:
            img = (f"look.{ext}", BytesIO(sketch_bytes), mime or f"image/{ext}")
            kwargs: dict[str, Any] = {
                "model": m,
                "image": img,
                "prompt": prompt,
                "size": "1024x1024",
                "n": 1,
            }
            if m == "gpt-image-1" or m.startswith("gpt-image-1.") or m in {"gpt-image-1.5", "gpt-image-2"}:
                kwargs["input_fidelity"] = "high"
            result = client.images.edit(**kwargs)
            raw = _extract_image_bytes(result.data[0])
            if raw:
                return raw
        except Exception as e:
            logger.warning("Tech pack job %s: blueprint edit via %s failed: %s", job.id, m, e)
    return None


def _generate_and_store_blueprint(client: OpenAI, job: AIJob, prompt: str, label: str) -> str | None:
    settings = get_settings()
    model = (settings.openai_image_model or "").strip()
    if model.lower() in {"", "none", "off", "false", "0"}:
        return None
    if not (prompt or "").strip():
        return None

    full_prompt = (
        "Technical fashion blueprint / tech-pack flat. Clean black line art on pure white background. "
        "No photo realism, no model figure, no shadows, no text watermarks, no collage. "
        f"{prompt.strip()}"
    )[:3800]

    size = (settings.openai_image_size or "1024x1024").strip()
    quality = (settings.openai_image_quality or "standard").strip()

    raw = _try_edit_blueprint(client, job, full_prompt, model)
    if not raw:
        for attempt in _image_gen_attempts(model, size, quality):
            attempt = dict(attempt)
            attempt["prompt"] = full_prompt
            try:
                result = client.images.generate(**attempt)
                raw = _extract_image_bytes(result.data[0])
                if raw:
                    break
            except Exception as e:
                logger.warning(
                    "Tech pack job %s: image generate %s failed: %s",
                    job.id,
                    attempt["model"],
                    e,
                )

    if not raw:
        return None
    url = _store_png(job, raw, label)
    logger.info("Tech pack job %s: stored %s blueprint → %s", job.id, label, url)
    return url


def _default_flat_prompts(garment: dict[str, Any]) -> tuple[str, str, str]:
    gtype = str(garment.get("type") or "garment")
    neck = str(garment.get("neckline") or "clean neckline")
    sleeves = str(garment.get("sleeves") or "set-in sleeves")
    front = (
        f"Front technical flat of a {gtype}, {neck}, {sleeves}, symmetrical, "
        "fashion tech-pack style line drawing, centered, full garment visible."
    )
    back = (
        f"Back technical flat of the same {gtype}, show center-back seam and zipper placement, "
        "fashion tech-pack style line drawing, centered, full garment visible."
    )
    pattern = (
        f"Pattern piece overview for a {gtype}: labeled front, back, sleeve, facing pieces "
        "with grainline arrows, fold lines, and notches, arranged neatly on a blank page."
    )
    return front, back, pattern


def _complete_with_openai(job: AIJob) -> dict[str, Any]:
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
    user_text = _user_text(job)
    img = _image_part(job)
    user_content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
    if img:
        user_content.append(img)

    completion = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        max_completion_tokens=3500,
    )

    raw = (completion.choices[0].message.content or "").strip()
    try:
        structured: Any = json.loads(raw)
    except json.JSONDecodeError:
        structured = {"summary": raw[:800], "parse_error": True}

    if not isinstance(structured, dict):
        structured = {"summary": str(structured)[:800]}

    result = _normalize_result(structured, pipeline=job.job_type, model=model)

    front_p = result.pop("front_flat_prompt", None) or ""
    back_p = result.pop("back_flat_prompt", None) or ""
    pattern_p = result.pop("pattern_overview_prompt", None) or ""
    if not front_p or not back_p or not pattern_p:
        df, db, dp = _default_flat_prompts(result.get("garment") or {})
        front_p = front_p or df
        back_p = back_p or db
        pattern_p = pattern_p or dp

    result["image_url"] = _generate_and_store_blueprint(client, job, front_p, "front")
    result["back_image_url"] = _generate_and_store_blueprint(client, job, back_p, "back")
    result["pattern_image_url"] = _generate_and_store_blueprint(client, job, pattern_p, "pattern")
    return result


def complete_tech_pack_job(job: AIJob) -> dict[str, Any]:
    if job.job_type not in TECH_PACK_JOB_TYPES:
        raise ValueError(f"unsupported job_type {job.job_type!r}")
    if not is_configured():
        return stub_tech_pack(job)
    return _complete_with_openai(job)
