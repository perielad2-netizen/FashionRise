"""Create Real Design V3 — image-aware professional AI (vision + technical illustrations).

Paid provider calls are injectable for tests. Production uses OpenAI Chat Completions
(vision via gpt-6-luna) and Images API edits (gpt-image-2.5-sunburst) with the Magic
look bytes as visual input — never text-only enrichment.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from app.core.config import get_settings
from app.services.sketch_openai import (
    build_image_edit_kwargs,
    chat_completion_kwargs,
)

logger = logging.getLogger(__name__)

ANALYSIS_SCHEMA_VERSION = "techpack_analysis_v3"
# Dense tailor JSON regularly exceeds 3k completion tokens; under-budget truncates mid-object.
PROFESSIONAL_ANALYZE_MIN_TOKENS = 4096
PROFESSIONAL_ANALYZE_MAX_TOKENS = 8192


def _parse_analysis_json(content: str) -> dict[str, Any]:
    """Parse vision JSON; tolerate fenced markdown and leading/trailing junk."""
    text = (content or "").strip()
    if not text:
        return {"confidence": "low", "assumptions": ["Empty vision analysis content"]}
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        return {"confidence": "low", "assumptions": ["Non-object analysis"]}
    except json.JSONDecodeError:
        pass
    # Strip ```json fences if present.
    if "```" in text:
        start = text.find("```")
        chunk = text[start + 3 :]
        if chunk.lstrip().lower().startswith("json"):
            chunk = chunk.lstrip()[4:]
        end = chunk.find("```")
        if end >= 0:
            chunk = chunk[:end]
        chunk = chunk.strip()
        try:
            parsed = json.loads(chunk)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            text = chunk
    # First { … last } salvage.
    lo = text.find("{")
    hi = text.rfind("}")
    if lo >= 0 and hi > lo:
        try:
            parsed = json.loads(text[lo : hi + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return {
        "raw": text[:4000],
        "confidence": "low",
        "assumptions": ["JSON parse failed"],
    }


@dataclass
class ProviderUsage:
    cost_usd_cents: int = 0
    vision_model: str | None = None
    image_model: str | None = None
    vision_calls: int = 0
    image_calls: int = 0
    notes: list[str] = field(default_factory=list)


class ProfessionalAIProvider(Protocol):
    def classify_outfit(
        self,
        *,
        image_bytes: bytes,
        mime: str,
        look_notes: str,
    ) -> tuple[dict[str, Any], ProviderUsage]:
        """Return JSON outfit structure ``{pieces:[{category,label,color_hint}], confidence}``."""
        ...

    def analyze_garment(
        self,
        *,
        image_bytes: bytes,
        mime: str,
        piece: dict[str, Any],
        look_notes: str,
        body_context: str = "",
    ) -> tuple[dict[str, Any], ProviderUsage]: ...

    def generate_technical_flat(
        self,
        *,
        source_image: bytes,
        mime: str,
        analysis: dict[str, Any],
        view: str,
        piece: dict[str, Any],
    ) -> tuple[bytes, ProviderUsage]: ...

    def generate_detail_or_pattern(
        self,
        *,
        source_image: bytes,
        mime: str,
        analysis: dict[str, Any],
        kind: str,
        piece: dict[str, Any],
    ) -> tuple[bytes, ProviderUsage]: ...


def estimate_professional_cents(
    *,
    piece_count: int,
    propose_back: bool,
    has_back_image: bool,
) -> tuple[int, int]:
    """Return (min_cents, max_cents) based on configured conservative estimators."""
    settings = get_settings()
    base = int(settings.techpack_ai_estimate_professional_cents_base or 250)
    per = int(settings.techpack_ai_estimate_professional_cents_per_piece or 180)
    back = int(settings.techpack_ai_estimate_professional_cents_propose_back or 80)
    n = max(1, piece_count)
    # Per piece: vision + front flat + detail + pattern sheet ≈ covered by base+per
    mid = base + per * (n - 1)
    if propose_back and not has_back_image:
        mid += back * n
    elif has_back_image:
        mid += back * n  # real back reference still costs an illustration
    lo = max(100, int(mid * 0.7))
    hi = int(mid * 1.35)
    max_run = int(round(float(settings.techpack_ai_max_usd_per_run or 8) * 100))
    if max_run > 0:
        hi = min(hi, max_run)
        lo = min(lo, hi)
    return lo, hi


def _image_data_url(image_bytes: bytes, mime: str) -> str:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime or 'image/png'};base64,{b64}"


def _usage_cents_from_chat(result: Any, *, fallback: int = 5) -> int:
    """Best-effort cost from usage if present; else conservative fallback cents."""
    usage = getattr(result, "usage", None)
    if usage is None:
        return fallback
    # gpt-6-luna: $0.10/M in, $0.50/M out — image tokens may appear in prompt_tokens.
    prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion = int(getattr(usage, "completion_tokens", 0) or 0)
    cents = int(round((prompt * 0.10 + completion * 0.50) / 10_000))
    return max(fallback, cents)


def _usage_cents_from_image(*, fallback: int = 40) -> int:
    """Conservative per-image estimate when provider omits token billing on Images API."""
    # gpt-image-2.5-sunburst image output is expensive; budget ~$0.40/image for high 1024x1536.
    return fallback


class OpenAIProfessionalProvider:
    """Live OpenAI provider — only invoked after spend gates in techpack_ai."""

    def classify_outfit(
        self,
        *,
        image_bytes: bytes,
        mime: str,
        look_notes: str,
    ) -> tuple[dict[str, Any], ProviderUsage]:
        """Paid vision pass: identify apparel piece count + categories from the Magic look."""
        from openai import OpenAI

        settings = get_settings()
        client = OpenAI(
            api_key=(settings.openai_api_key or "").strip(),
            base_url=settings.openai_base_url or None,
            timeout=settings.openai_timeout_seconds,
        )
        system = (
            "You are a fashion technical designer identifying garment structure for a factory tech pack. "
            "Return JSON only with keys: pieces (array), confidence (high|medium|low), notes (string). "
            "Each piece must have: category, label, color_hint. "
            "category MUST be one of: dress, shirt, top, jacket, skirt, trousers, shorts, jumpsuit, set. "
            "List every distinct apparel piece the designer clearly drew or photographed "
            "(e.g. shirt+trousers = 2 pieces; dress alone = 1; matching two-piece set = set or two pieces). "
            "Do NOT list hosiery, stockings, tights, gloves, shoes, jewelry, bags, or hair as pieces — "
            "fold them into notes instead. Prefer concrete apparel categories; never return category other. "
            "Use the image as ground truth; look notes are optional hints only."
        )
        user_text = (
            f"Look notes (optional): {(look_notes or '')[:500] or '(none)'}. "
            "Identify the apparel garment structure for a technical pack."
        )
        kwargs = chat_completion_kwargs(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {
                            "type": "image_url",
                            "image_url": {"url": _image_data_url(image_bytes, mime)},
                        },
                    ],
                },
            ],
            max_completion_tokens=min(900, int(settings.openai_max_completion_tokens or 1400)),
            reasoning_effort=settings.openai_reasoning_effort,
        )
        kwargs["response_format"] = {"type": "json_object"}
        result = client.chat.completions.create(**kwargs)
        content = (result.choices[0].message.content or "").strip() if result.choices else ""
        try:
            parsed = json.loads(content) if content else {}
        except json.JSONDecodeError:
            parsed = {"pieces": [], "confidence": "low", "notes": "JSON parse failed"}
        if not isinstance(parsed, dict):
            parsed = {"pieces": [], "confidence": "low", "notes": "Non-object response"}
        usage = ProviderUsage(
            cost_usd_cents=_usage_cents_from_chat(result, fallback=8),
            vision_model=settings.openai_model,
            vision_calls=1,
            notes=["outfit_structure_classify"],
        )
        return parsed, usage

    def analyze_garment(
        self,
        *,
        image_bytes: bytes,
        mime: str,
        piece: dict[str, Any],
        look_notes: str,
        body_context: str = "",
    ) -> tuple[dict[str, Any], ProviderUsage]:
        from openai import OpenAI

        settings = get_settings()
        client = OpenAI(
            api_key=(settings.openai_api_key or "").strip(),
            base_url=settings.openai_base_url or None,
            timeout=settings.openai_timeout_seconds,
        )
        cat = str(piece.get("category") or "other")
        label = str(piece.get("label") or cat)
        system = (
            "You are a senior fashion technical designer writing a SAMPLE-DEVELOPMENT "
            "tech pack a tailor/patternmaker can work from. "
            "Return ONE compact JSON object only (no markdown). Keys: schema_version, category, "
            "silhouette, length, neckline, sleeves, fit, closure_visible, fabric_pattern, "
            "stripe_direction, colors, panels_seams, distinctive_features (array of short strings), "
            "pattern_pieces_suggested (array of {id,name,cut_qty,notes,grainline}), "
            "construction_notes (array of short strings), "
            "construction_operations (array of "
            "{operation,stitch_type,spi,seam_allowance_cm,notes} — 8 to 14 sew-order steps), "
            "finished_pom_estimates (object with NUMBERS in cm or null: "
            "chest_bust, waist, hip = FULL garment circumferences ≈ body+ease — NEVER flat half; "
            "garment_length, sleeve_length, shoulder_width, armhole, hem_sweep=full hem circ; "
            "neckline_depth=DEPTH not circ; wrap_overlap; slit_start_from_waist; overlay_length; "
            "sash_width; sash_length; hem_high; hem_low; "
            "finished_pom_methods as a short string stating FULL circ vs depth/length), "
            "fabric_estimate (object: hand, likely_fiber, gsm_range, drape, opacity, "
            "lining_recommended bool, notes), "
            "callout_points (array of {n,label,region} — 10 to 16 factory callouts for flats), "
            "hardware (array of {item,spec,placement,qty,unit,color} — zip/hooks/buttons/tape), "
            "pantone_estimate (short string — closest textile color guess, mark as proposed), "
            "care_recommendation (object: wash, bleach, dry, iron, dry_clean — ISO 3758 style text), "
            "back_construction_proposal (string — invent a coherent rear when back is unseen), "
            "confidence (low|medium|high), assumptions (array of strings). "
            "Keep every string field under 160 characters. "
            "construction_operations MUST be specific to THIS look "
            "(wrap/drape/slit/sash/zip/lining as applicable) — never generic dress boilerplate. "
            "Use body measurements to propose proportional finished POMs when the photo "
            "supports length/sleeve proportion; mark assumptions clearly. "
            "Prefer useful sample-room estimates over leaving critical fields empty. "
            "callout_points and hardware must be garment-specific for a tailor/sample room. "
            f"schema_version must be '{ANALYSIS_SCHEMA_VERSION}'."
        )
        user_text = (
            f"Garment tab: category={cat}, label={label}. "
            f"Body measurements: {(body_context or 'not provided')[:400]}. "
            f"Look notes: {(look_notes or '')[:400]}. "
            "Write a tailor-ready analysis: design-specific sew ops, cut inventory, "
            "fabric estimate, numeric POM estimates (cm), numbered flat callouts, "
            "hardware list, care proposal, Pantone-style color guess, and a coherent "
            "proposed back if the rear is not visible."
        )
        # Dense technical JSON needs headroom — 3.2k truncated mid-object on real looks.
        configured = int(settings.openai_max_completion_tokens or 1400)
        token_budget = max(PROFESSIONAL_ANALYZE_MIN_TOKENS, configured)
        token_budget = min(token_budget, PROFESSIONAL_ANALYZE_MAX_TOKENS)
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {
                        "type": "image_url",
                        "image_url": {"url": _image_data_url(image_bytes, mime)},
                    },
                ],
            },
        ]

        def _once(budget: int):
            kwargs = chat_completion_kwargs(
                model=settings.openai_model,
                messages=messages,
                max_completion_tokens=budget,
                reasoning_effort=settings.openai_reasoning_effort,
            )
            kwargs["response_format"] = {"type": "json_object"}
            result = client.chat.completions.create(**kwargs)
            choice = result.choices[0] if result.choices else None
            content = ((choice.message.content if choice else None) or "").strip()
            finish = getattr(choice, "finish_reason", None) if choice else None
            return result, content, finish

        result, content, finish = _once(token_budget)
        parsed = _parse_analysis_json(content)
        # Retry once at max budget if truncated or unusable.
        needs_retry = (
            finish == "length"
            or "JSON parse failed" in (parsed.get("assumptions") or [])
            or (
                not str(parsed.get("silhouette") or "").strip()
                and not parsed.get("construction_operations")
            )
        )
        total_cents = _usage_cents_from_chat(result)
        vision_calls = 1
        if needs_retry and token_budget < PROFESSIONAL_ANALYZE_MAX_TOKENS:
            result2, content2, finish2 = _once(PROFESSIONAL_ANALYZE_MAX_TOKENS)
            parsed2 = _parse_analysis_json(content2)
            total_cents += _usage_cents_from_chat(result2)
            vision_calls += 1
            better = (
                "JSON parse failed" not in (parsed2.get("assumptions") or [])
                and (
                    str(parsed2.get("silhouette") or "").strip()
                    or parsed2.get("construction_operations")
                )
            )
            if better:
                parsed = parsed2
                finish = finish2
            elif finish2:
                parsed.setdefault("assumptions", [])
                if isinstance(parsed["assumptions"], list):
                    parsed["assumptions"].append(f"retry_finish={finish2}")
        if not isinstance(parsed, dict):
            parsed = {"confidence": "low", "assumptions": ["Non-object analysis"]}
        if finish == "length":
            parsed.setdefault("assumptions", [])
            if isinstance(parsed["assumptions"], list):
                parsed["assumptions"].append("Vision JSON may be truncated (finish_reason=length)")
        parsed["schema_version"] = ANALYSIS_SCHEMA_VERSION
        usage = ProviderUsage(
            cost_usd_cents=total_cents,
            vision_model=settings.openai_model,
            vision_calls=vision_calls,
        )
        return parsed, usage

    def generate_technical_flat(
        self,
        *,
        source_image: bytes,
        mime: str,
        analysis: dict[str, Any],
        view: str,
        piece: dict[str, Any],
    ) -> tuple[bytes, ProviderUsage]:
        return self._edit(
            source_image=source_image,
            mime=mime,
            prompt=self._flat_prompt(analysis, view=view, piece=piece),
        )

    def generate_detail_or_pattern(
        self,
        *,
        source_image: bytes,
        mime: str,
        analysis: dict[str, Any],
        kind: str,
        piece: dict[str, Any],
    ) -> tuple[bytes, ProviderUsage]:
        if kind.startswith("pattern"):
            prompt = self._pattern_prompt(analysis, piece=piece)
        else:
            prompt = self._detail_prompt(analysis, piece=piece)
        return self._edit(source_image=source_image, mime=mime, prompt=prompt)

    def _edit(self, *, source_image: bytes, mime: str, prompt: str) -> tuple[bytes, ProviderUsage]:
        from openai import OpenAI

        settings = get_settings()
        client = OpenAI(
            api_key=(settings.openai_api_key or "").strip(),
            base_url=settings.openai_base_url or None,
            timeout=settings.openai_timeout_seconds,
        )
        model = (settings.openai_image_model or "gpt-image-2.5-sunburst").strip()
        kwargs = build_image_edit_kwargs(
            model=model,
            prompt=prompt[:3800],
            sketch=(source_image, mime or "image/png"),
            size=settings.openai_image_size or "1024x1536",
            quality=settings.openai_image_quality or "high",
        )
        result = client.with_options(max_retries=0).images.edit(**kwargs)
        data = getattr(result, "data", None) or []
        if not data:
            raise RuntimeError("Image edit returned no data")
        item = data[0]
        b64 = getattr(item, "b64_json", None)
        if not b64 and isinstance(item, dict):
            b64 = item.get("b64_json")
        if not b64:
            raise RuntimeError("Image edit missing b64_json")
        raw = base64.b64decode(b64)
        usage = ProviderUsage(
            cost_usd_cents=_usage_cents_from_image(),
            image_model=model,
            image_calls=1,
        )
        return raw, usage

    @staticmethod
    def _flat_prompt(analysis: dict[str, Any], *, view: str, piece: dict[str, Any]) -> str:
        features = ", ".join(str(x) for x in (analysis.get("distinctive_features") or [])[:12])
        unverified = ""
        if view == "back_proposed":
            unverified = (
                " Label clearly as PROPOSED BACK — UNVERIFIED. Do not claim this is a photographed back."
            )
        return (
            "Create a professional fashion TECHNICAL FLAT illustration of THIS exact garment from the "
            f"reference photo. View: {view.replace('_', ' ')}.{unverified} "
            "Isolate the garment only — no model, no body, no mannequin, no face. "
            "Clean white technical background. Preserve source-faithful outline and design features: "
            f"silhouette={analysis.get('silhouette')}, length={analysis.get('length')}, "
            f"neckline={analysis.get('neckline')}, sleeves={analysis.get('sleeves')}, "
            f"fit={analysis.get('fit')}, fabric_pattern={analysis.get('fabric_pattern')}, "
            f"stripe_direction={analysis.get('stripe_direction')}, colors={analysis.get('colors')}, "
            f"features={features}. "
            f"Category hint: {piece.get('category')}. "
            "Do NOT draw a generic A-line dress if the source is fitted/bodycon with long sleeves or a deep V. "
            "Output a clean vector-like technical fashion flat suitable for a manufacturing tech pack. "
            "Add small RED NUMBERED CALLOUT DOTS (1–12) with short leader lines at key construction "
            "points (neckline, waist, sleeve set, hem, slit/zip) — factory annotation style like a "
            "Michael Kors / GarmentSpec sheet. Keep numbers legible; do not cover critical seams."
        )

    @staticmethod
    def _detail_prompt(analysis: dict[str, Any], *, piece: dict[str, Any]) -> str:
        cat = str(piece.get("category") or "garment")
        label = str(piece.get("label") or cat)
        return (
            "Create a professional fashion technical DETAIL callout sheet for ONE garment only: "
            f"category={cat}, label={label}. "
            "Do NOT include construction details from any other garment in the outfit "
            "(e.g. never put hoodie zippers/hood/drawcord on a shorts detail sheet, and never put "
            "waistband/inseam/leg-opening callouts on a top detail sheet). "
            "White background. Show close-up construction callouts that belong to THIS category "
            "(neckline/sleeve/cuff/hem/zipper for tops; waistband/pockets/hem/fly for bottoms). "
            f"Neckline={analysis.get('neckline')}; sleeves={analysis.get('sleeves')}; "
            f"pattern={analysis.get('fabric_pattern')} {analysis.get('stripe_direction')}; "
            f"silhouette={analysis.get('silhouette')}. "
            "If a detail is not visible on this garment, omit it rather than inventing another garment's parts. "
            "No model body. Label callouts briefly. Not a photo — a technical illustration. "
            "If you cannot produce category-correct details, leave callouts blank rather than borrowing "
            "from a different garment — failures require designer review, not silent approval."
        )

    @staticmethod
    def _pattern_prompt(analysis: dict[str, Any], *, piece: dict[str, Any]) -> str:
        pieces = analysis.get("pattern_pieces_suggested") or []
        names = ", ".join(
            str(p.get("name") or p.get("id")) for p in pieces if isinstance(p, dict)
        )[:300]
        return (
            "Create a PATTERN DEVELOPMENT SCHEMATIC sheet (NOT TO SCALE) for THIS garment. "
            "Show named pattern pieces with illustrative shapes matching the garment "
            f"(e.g. {names or 'front, back, sleeves'}), grainline arrows, fold marks, and cut quantities. "
            "White background. Do NOT use generic unlabeled rectangles labeled only Piece A/B/C. "
            "Include banner text: NOT TO SCALE — PATTERNMAKER VALIDATION REQUIRED. "
            f"Silhouette={analysis.get('silhouette')}; sleeves={analysis.get('sleeves')}."
        )


def _mock_analysis_for_piece(piece: dict[str, Any], look_notes: str) -> dict[str, Any]:
    """Category-aware mock vision — supports shirt+trousers regression without paid AI."""
    cat = str(piece.get("category") or "other").lower()
    notes = (look_notes or "").lower()
    color_hint = str(piece.get("color_hint") or "").lower()

    if cat in ("shirt", "top", "blouse"):
        neckline = "V-slit neckline"
        if "v-slit" in notes or "v slit" in notes or "v-neck" in notes or "v neck" in notes:
            neckline = "V-slit neckline"
        sleeves = "three-quarter sleeves"
        if "three-quarter" in notes or "3/4" in notes or "three quarter" in notes:
            sleeves = "three-quarter sleeves"
        elif "long sleeve" in notes:
            sleeves = "long sleeves"
        elif "short sleeve" in notes:
            sleeves = "short sleeves"
        colors = ["black"] if "black" in notes or "black" in color_hint else (
            [color_hint] if color_hint else ["dark"]
        )
        return {
            "schema_version": ANALYSIS_SCHEMA_VERSION,
            "category": "shirt" if cat != "top" else cat,
            "silhouette": "relaxed straight shirt",
            "length": "hip length",
            "neckline": neckline,
            "sleeves": sleeves,
            "fit": "relaxed",
            "closure_visible": "none clearly verified — confirm placket/buttons",
            "fabric_pattern": "solid" if "black" in colors else "solid tonal",
            "stripe_direction": None,
            "colors": colors,
            "panels_seams": "shoulder seams; side seams; set-in sleeves",
            "distinctive_features": [neckline, sleeves, f"{colors[0]} shell"],
            "pattern_pieces_suggested": [
                {"id": "SH-F", "name": "Front", "cut_qty": 1},
                {"id": "SH-B", "name": "Back", "cut_qty": 1},
                {"id": "SH-SL", "name": "Sleeve", "cut_qty": 2},
            ],
            "construction_notes": [
                f"Finish {neckline} cleanly before setting sleeves.",
                f"Set {sleeves}; confirm finished sleeve length with designer.",
            ],
            "confidence": "high",
            "assumptions": [
                "Mock shirt analysis from look notes — measurements not fabricated",
                "Back view not verified unless a Magic back image exists",
            ],
        }

    if cat in ("trousers", "pants", "shorts"):
        colors = ["beige"] if "beige" in notes or "beige" in color_hint else (
            [color_hint] if color_hint else ["neutral"]
        )
        length = "full length" if cat != "shorts" else "short"
        return {
            "schema_version": ANALYSIS_SCHEMA_VERSION,
            "category": "trousers" if cat != "shorts" else "shorts",
            "silhouette": "straight leg" if cat != "shorts" else "relaxed short",
            "length": length,
            "neckline": None,
            "sleeves": None,
            "fit": "regular",
            "closure_visible": "waistband — closure not verified from front alone",
            "fabric_pattern": "solid woven appearance",
            "stripe_direction": None,
            "colors": colors,
            "panels_seams": "side seams; inseam; waistband",
            "distinctive_features": [f"{colors[0]} trousers", "straight leg", length],
            "pattern_pieces_suggested": [
                {"id": "TR-F", "name": "Front leg", "cut_qty": 2},
                {"id": "TR-B", "name": "Back leg", "cut_qty": 2},
                {"id": "TR-WB", "name": "Waistband", "cut_qty": 1},
            ],
            "construction_notes": [
                "Assemble front/back legs at outseam and inseam.",
                "Attach waistband; confirm rise and inseam with designer — not measured from image.",
            ],
            "confidence": "high",
            "assumptions": [
                "Mock trousers analysis from look notes — no fabricated inseam cm",
                "Back pockets/closure unverified without back view",
            ],
        }

    if cat == "skirt":
        return {
            "schema_version": ANALYSIS_SCHEMA_VERSION,
            "category": "skirt",
            "silhouette": "straight",
            "length": "midi",
            "neckline": None,
            "sleeves": None,
            "fit": "regular",
            "closure_visible": "not verified",
            "fabric_pattern": "solid",
            "stripe_direction": None,
            "colors": [color_hint] if color_hint else ["unknown"],
            "panels_seams": "side seams",
            "distinctive_features": ["skirt"],
            "pattern_pieces_suggested": [
                {"id": "SK-F", "name": "Front", "cut_qty": 1},
                {"id": "SK-B", "name": "Back", "cut_qty": 1},
            ],
            "construction_notes": ["Assemble side seams; finish waist."],
            "confidence": "medium",
            "assumptions": ["Mock skirt analysis"],
        }

    # Default: FR-7182-style pink striped dress (legacy tests).
    return {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "category": piece.get("category") or "dress",
        "silhouette": "fitted bodycon mini",
        "length": "mini",
        "neckline": "deep plunging V-neckline",
        "sleeves": "long sleeves",
        "fit": "fitted",
        "closure_visible": "none visible — pull-on assumed",
        "fabric_pattern": "bright pink and white diagonal stripes",
        "stripe_direction": "diagonal",
        "colors": ["bright pink", "white"],
        "panels_seams": "side seams; set-in sleeves",
        "distinctive_features": [
            "deep plunging V-neckline",
            "long sleeves",
            "fitted mini length",
            "diagonal pink/white stripes",
        ],
        "pattern_pieces_suggested": [
            {"id": "DR-F", "name": "Front bodice", "cut_qty": 1},
            {"id": "DR-B", "name": "Back bodice", "cut_qty": 1},
            {"id": "DR-SL", "name": "Sleeve", "cut_qty": 2},
        ],
        "construction_notes": [
            "Stabilize deep V neckline before setting sleeves.",
            "Match diagonal stripe continuity at side seams.",
        ],
        "construction_operations": [
            {
                "operation": "Staystitch deep V neckline",
                "stitch_type": "301 lockstitch",
                "spi": "3.5–4 /cm",
                "seam_allowance_cm": 1.0,
                "notes": "Stabilize bias plunge before any shaping.",
            },
            {
                "operation": "Join side seams matching diagonal stripes",
                "stitch_type": "301 + 504 overlock",
                "spi": "3.5–4 /cm",
                "seam_allowance_cm": 1.0,
                "notes": "Keep stripe continuity across CF/SS.",
            },
            {
                "operation": "Set long sleeves",
                "stitch_type": "301 + 504",
                "spi": "3.5–4 /cm",
                "seam_allowance_cm": 1.0,
                "notes": "Ease sleeve head; press seam toward sleeve.",
            },
            {
                "operation": "Hem mini skirt",
                "stitch_type": "Blind hem / 301",
                "spi": "per fabric",
                "seam_allowance_cm": 2.5,
                "notes": "Even hem on form; match stripe at CF if applicable.",
            },
        ],
        "finished_pom_estimates": {
            "garment_length": 92.0,
            "sleeve_length": 60.0,
            "neckline_depth": 28.0,
            "hem_sweep": 48.0,
            "finished_pom_methods": {
                "garment_length": "Proportion from body height + mini silhouette",
                "sleeve_length": "Long sleeve to wrist from shoulder proportion",
            },
        },
        "fabric_estimate": {
            "hand": "smooth light stretch knit look",
            "likely_fiber": "polyester / elastane jersey",
            "gsm_range": "180–220",
            "drape": "fluid",
            "opacity": "opaque",
            "lining_recommended": False,
            "notes": "Mock fabric estimate for striped mini dress",
        },
        "back_construction_proposal": "Center-back invisible zip with self-fabric facing; back neck sits higher than front V.",
        "confidence": "high",
        "assumptions": ["Mock analysis for FR-7182-style pink striped dress"],
    }


class MockProfessionalProvider:
    """Deterministic fixture provider for tests — incurs $0 real spend."""

    def __init__(
        self,
        analysis_override: dict[str, Any] | None = None,
        *,
        outfit_override: dict[str, Any] | None = None,
    ) -> None:
        self.analysis_override = analysis_override
        self.outfit_override = outfit_override
        self.calls: list[str] = []

    def classify_outfit(
        self,
        *,
        image_bytes: bytes,
        mime: str,
        look_notes: str,
    ) -> tuple[dict[str, Any], ProviderUsage]:
        self.calls.append(f"classify:{len(image_bytes)}:{mime}")
        if self.outfit_override:
            data = dict(self.outfit_override)
        else:
            text = (look_notes or "").lower()
            pieces: list[dict[str, Any]] = []
            if "shirt" in text and ("trouser" in text or "pant" in text):
                pieces = [
                    {"category": "shirt", "label": "Shirt", "color_hint": ""},
                    {"category": "trousers", "label": "Trousers", "color_hint": ""},
                ]
            elif "jumpsuit" in text or "romper" in text:
                pieces = [{"category": "jumpsuit", "label": "Jumpsuit", "color_hint": ""}]
            elif "skirt" in text:
                pieces = [{"category": "skirt", "label": "Skirt", "color_hint": ""}]
            elif "trouser" in text or "pant" in text or "jeans" in text:
                pieces = [{"category": "trousers", "label": "Trousers", "color_hint": ""}]
            elif "jacket" in text or "coat" in text:
                pieces = [{"category": "jacket", "label": "Jacket", "color_hint": ""}]
            elif "top" in text or "blouse" in text or "tee" in text:
                pieces = [{"category": "top", "label": "Top", "color_hint": ""}]
            else:
                pieces = [{"category": "dress", "label": "Dress", "color_hint": ""}]
            data = {"pieces": pieces, "confidence": "high", "notes": "mock_classify"}
        return data, ProviderUsage(
            cost_usd_cents=2,
            vision_model="mock-vision",
            vision_calls=1,
            notes=["outfit_structure_classify"],
        )

    def analyze_garment(
        self,
        *,
        image_bytes: bytes,
        mime: str,
        piece: dict[str, Any],
        look_notes: str,
        body_context: str = "",
    ) -> tuple[dict[str, Any], ProviderUsage]:
        self.calls.append(f"analyze:{len(image_bytes)}:{mime}:{len(body_context or '')}")
        if self.analysis_override:
            data = dict(self.analysis_override)
            # Keep override but stamp category from piece when absent so multi-piece tests work.
            data.setdefault("category", piece.get("category") or "dress")
            data.setdefault("schema_version", ANALYSIS_SCHEMA_VERSION)
        else:
            data = _mock_analysis_for_piece(piece, look_notes)
        return data, ProviderUsage(cost_usd_cents=3, vision_model="mock-vision", vision_calls=1)

    def generate_technical_flat(
        self,
        *,
        source_image: bytes,
        mime: str,
        analysis: dict[str, Any],
        view: str,
        piece: dict[str, Any],
    ) -> tuple[bytes, ProviderUsage]:
        self.calls.append(f"flat:{view}:{len(source_image)}")
        # Distinct non-generic PNG encoding analysis keywords into pixels via text PNG is hard;
        # produce a unique PNG with embedded comment-like payload in IHDR-sized canvas.
        png = _mock_png_with_label(
            f"FLAT-{view}|{analysis.get('neckline')}|{analysis.get('sleeves')}|{analysis.get('fabric_pattern')}"
        )
        return png, ProviderUsage(cost_usd_cents=12, image_model="mock-image", image_calls=1)

    def generate_detail_or_pattern(
        self,
        *,
        source_image: bytes,
        mime: str,
        analysis: dict[str, Any],
        kind: str,
        piece: dict[str, Any],
    ) -> tuple[bytes, ProviderUsage]:
        self.calls.append(f"{kind}:{len(source_image)}")
        png = _mock_png_with_label(
            f"{kind}|{analysis.get('neckline')}|stripes={analysis.get('stripe_direction')}"
        )
        return png, ProviderUsage(cost_usd_cents=12, image_model="mock-image", image_calls=1)


def _mock_png_with_label(label: str) -> bytes:
    """RGB PNG with a fitted striped long-sleeve mini silhouette (not a generic A-line)."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (512, 768), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    # Fitted mini dress silhouette (not A-line triangle)
    draw.polygon(
        [(220, 80), (292, 80), (310, 140), (340, 520), (172, 520), (200, 140)],
        outline=(30, 30, 40),
        fill=(255, 105, 180),
    )
    # Deep V
    draw.polygon([(220, 80), (256, 200), (292, 80)], outline=(30, 30, 40), fill=(255, 255, 255))
    # Long sleeves
    draw.polygon([(200, 140), (120, 160), (130, 420), (200, 400)], outline=(30, 30, 40), fill=(255, 105, 180))
    draw.polygon([(310, 140), (390, 160), (380, 420), (310, 400)], outline=(30, 30, 40), fill=(255, 105, 180))
    # Diagonal stripes
    for i in range(-200, 600, 28):
        draw.line([(i, 120), (i + 180, 520)], fill=(255, 255, 255), width=4)
    # Avoid font-dependent text; encode label as colored barcode strips for uniqueness.
    digest = abs(hash(label)) % 10_000
    draw.rectangle([(24, 20), (24 + (digest % 200), 36)], fill=(20, 20, 30))
    draw.rectangle([(24, 700), (480, 730)], fill=(180, 40, 90))
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def default_provider() -> ProfessionalAIProvider:
    return OpenAIProfessionalProvider()


ProgressCallback = Callable[[dict[str, Any]], None]


def run_professional_pipeline(
    *,
    provider: ProfessionalAIProvider,
    pieces: list[dict[str, Any]],
    front_image: tuple[bytes, str] | None,
    back_image: tuple[bytes, str] | None,
    look_notes: str,
    propose_back: bool,
    max_images: int,
    on_progress: ProgressCallback | None = None,
    image_plan: dict[str, Any] | None = None,
    body_context: str = "",
) -> dict[str, Any]:
    """Analyze source Magic image and produce per-piece analysis + illustration bytes.

    Returns structured result with `piece_results` and aggregated `usage`.
    `on_progress` receives named phase dicts (never fake percentages).

    Image budget: required ``flat_front`` for every garment is allocated first; optional
    backs/details/patterns are fair-shared via ``image_plan`` (or planned here).
    """
    from app.services.techpack_structure import plan_professional_image_kinds

    if front_image is None and back_image is None:
        raise ValueError("Professional AI requires at least one Magic look image")
    primary = front_image or back_image
    assert primary is not None
    total_usage = ProviderUsage()
    piece_results: list[dict[str, Any]] = []
    images_used = 0
    failed: list[str] = []
    work_pieces = [p for p in pieces if isinstance(p, dict)]
    if not work_pieces:
        raise ValueError("Professional AI requires at least one validated garment piece")
    total_pieces = len(work_pieces)
    plan = image_plan or plan_professional_image_kinds(
        work_pieces,
        propose_back=propose_back,
        has_back_image=back_image is not None,
        max_images=max_images,
    )
    per_piece_plan = plan.get("per_piece") if isinstance(plan.get("per_piece"), dict) else {}
    failed.extend(str(x) for x in (plan.get("skipped_optional") or []) if x)

    def _progress(
        phase: str,
        *,
        piece_id: str | None = None,
        detail: str | None = None,
        provider_in_flight: dict[str, Any] | None = None,
        clear_in_flight: bool = False,
    ) -> None:
        if on_progress is None:
            return
        payload: dict[str, Any] = {
            "phase": phase,
            "piece_id": piece_id,
            "detail": detail,
            "pieces_done": len(piece_results),
            "pieces_total": total_pieces,
            "cost_usd_cents": total_usage.cost_usd_cents,
            "message": {
                "preparing": "Preparing your design",
                "analyzing": "Analyzing the garment",
                "flat_front": "Creating technical illustrations",
                "flat_back": "Creating technical illustrations",
                "flat_back_proposed": "Creating technical illustrations",
                "detail_callouts": "Creating technical illustrations",
                "pattern_sheet": "Preparing pattern-development drawings",
                "assembling": "Assembling your PDF",
                "ready": "Your AI Technical Pack is ready",
            }.get(phase, "Preparing your design"),
        }
        if provider_in_flight is not None:
            payload["provider_in_flight"] = provider_in_flight
        if clear_in_flight:
            payload["clear_in_flight"] = True
        on_progress(payload)

    _progress("preparing")

    for piece in work_pieces:
        pid = str(piece.get("id") or "").strip()
        if not pid:
            raise ValueError("Professional piece missing stable id")
        allowed = set((per_piece_plan.get(pid) or {}).get("all") or ["flat_front"])
        # Prefer front Magic; fall back to back.
        src_bytes, src_mime = primary
        _progress(
            "analyzing",
            piece_id=pid,
            provider_in_flight={"kind": "vision", "piece_id": pid},
        )
        analysis, u = provider.analyze_garment(
            image_bytes=src_bytes,
            mime=src_mime,
            piece=piece,
            look_notes=look_notes,
            body_context=body_context or "",
        )
        total_usage.cost_usd_cents += u.cost_usd_cents
        total_usage.vision_calls += u.vision_calls
        total_usage.vision_model = u.vision_model or total_usage.vision_model
        _progress("analyzing", piece_id=pid, clear_in_flight=True)

        arts: list[dict[str, Any]] = []

        def _add_image(kind: str, gen) -> None:
            nonlocal images_used
            if kind not in allowed:
                return
            if images_used >= max_images:
                failed.append(f"{pid}:{kind}:max_images")
                return
            _progress(
                kind,
                piece_id=pid,
                provider_in_flight={"kind": kind, "piece_id": pid},
            )
            try:
                raw, uu = gen()
                images_used += 1
                total_usage.cost_usd_cents += uu.cost_usd_cents
                total_usage.image_calls += uu.image_calls
                total_usage.image_model = uu.image_model or total_usage.image_model
                arts.append({"kind": kind, "bytes": raw, "mime": "image/png", "model": uu.image_model})
                _progress(kind, piece_id=pid, clear_in_flight=True)
            except Exception as exc:  # noqa: BLE001
                logger.warning("professional illustration failed piece=%s kind=%s: %s", pid, kind, exc)
                failed.append(f"{pid}:{kind}:{type(exc).__name__}")
                _progress(kind, piece_id=pid, clear_in_flight=True)

        _add_image(
            "flat_front",
            lambda: provider.generate_technical_flat(
                source_image=src_bytes,
                mime=src_mime,
                analysis=analysis,
                view="front",
                piece=piece,
            ),
        )
        if back_image is not None:
            b_bytes, b_mime = back_image
            _add_image(
                "flat_back",
                lambda bb=b_bytes, bm=b_mime: provider.generate_technical_flat(
                    source_image=bb,
                    mime=bm,
                    analysis=analysis,
                    view="back",
                    piece=piece,
                ),
            )
        elif propose_back:
            _add_image(
                "flat_back_proposed",
                lambda: provider.generate_technical_flat(
                    source_image=src_bytes,
                    mime=src_mime,
                    analysis=analysis,
                    view="back_proposed",
                    piece=piece,
                ),
            )
        _add_image(
            "detail_callouts",
            lambda: provider.generate_detail_or_pattern(
                source_image=src_bytes,
                mime=src_mime,
                analysis=analysis,
                kind="detail_callouts",
                piece=piece,
            ),
        )
        _add_image(
            "pattern_sheet",
            lambda: provider.generate_detail_or_pattern(
                source_image=src_bytes,
                mime=src_mime,
                analysis=analysis,
                kind="pattern_sheet",
                piece=piece,
            ),
        )

        piece_results.append(
            {
                "piece_id": pid,
                "analysis": analysis,
                "artifacts": arts,
            }
        )

    summary_bits = []
    for pr in piece_results:
        a = pr.get("analysis") or {}
        summary_bits.append(
            f"{pr.get('piece_id')}: {a.get('silhouette') or ''} / {a.get('neckline') or ''} / {a.get('sleeves') or ''} / {a.get('fabric_pattern') or ''}"
        )
    return {
        "piece_results": piece_results,
        "usage": {
            "cost_usd_cents": total_usage.cost_usd_cents,
            "vision_model": total_usage.vision_model,
            "image_model": total_usage.image_model,
            "vision_calls": total_usage.vision_calls,
            "image_calls": total_usage.image_calls,
        },
        "analysis_summary": "; ".join(summary_bits)[:800],
        "failed_sections": failed,
        "image_plan": plan,
        "schema_version": ANALYSIS_SCHEMA_VERSION,
    }
