"""Validate and normalize AI fabric creation prompts (fabric-only, color required)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from fastapi import HTTPException, status

_PROMPT_MAX = 400
_SHORT_MAX = 120
_HEX_RE = re.compile(r"^#?[0-9A-Fa-f]{6}$")
_CONTROL = re.compile(r"[\u0000-\u001F\u007F-\u009F\u2028\u2029]")

# Must look like textile / surface / print / construction language.
# Keep this broad enough for natural designer wording (e.g. "jeans" + "stitches").
_FABRIC_TERMS = re.compile(
    r"\b("
    r"fabric|textile|pattern|print|weave|woven|knit|mesh|satin|silk|chiffon|"
    r"velvet|velour|lace|tulle|organza|brocade|jacquard|tweed|wool|cotton|"
    r"linen|denim|jeans?|jean\s*material|twill|corduroy|canvas|flannel|jersey|"
    r"fleece|nylon|polyester|rayon|viscose|cashmere|mohair|angora|ripstop|"
    r"leather|suede|sequin|sequins|glitter|sparkle|sparkles|"
    r"diamond|diamonds|metallic|metal|foil|lam[eé]|shimmer|shiny|gloss|"
    r"sheen|pearl|pearls|bead|beads|embroidery|embroidered|floral|paisley|"
    r"stripe|stripes|polka|check|checker|plaid|animal\s*print|camouflage|"
    r"camo|houndstooth|damask|moire|moire|texture|swatch|tile|repeating|"
    r"stitch|stitches|stitching|sewn|seam|seams|seamwork|patchwork|patched|"
    r"patch|patches|panel|panels|quilted|quilting|herringbone|distressed|"
    r"washed|raw\s*denim|indigo|rivet|rivets|thread|threads|yarn|woven\s*look|"
    r"gold|silver|bronze|crystal|crystals|rhinestone|rhinestones|"
    r"stocking|stockings|hosiery|tights|pantyhose|glove|gloves|sheer|knitwear"
    r")\b",
    re.I,
)

# Hard refuse — not a fabric request.
_BLOCKED = re.compile(
    r"\b("
    r"nude|nsfw|porn|sexual|gore|blood|weapon|gun|kill|hate|racist|"
    r"selfie|portrait|face\b|person|people|woman|man|girl|boy|child|"
    r"celebrity|politician|logo|trademark|nike|adidas|gucci|chanel|"
    r"disney|marvel|hello\s*kitty|generate\s+me|make\s+me\s+into|"
    r"wear\s+this|try\s*on|outfit\s+on\s+me|full\s+body|photoreal\s+model"
    r")\b",
    re.I,
)

# Color words → hex (aligned with Studio fashion palette + common metals).
_COLOR_WORDS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"\b(ivory|cream|off[-\s]?white)\b", re.I), "#F5F0E6", "ivory"),
    (re.compile(r"\b(blush|rose\s*pink|pink)\b", re.I), "#E8A0A8", "blush"),
    (re.compile(r"\b(crimson|wine|burgundy|maroon)\b", re.I), "#B91C1C", "crimson"),
    (re.compile(r"\b(coral|orange)\b", re.I), "#F97316", "coral"),
    (re.compile(r"\b(gold|golden|gilt)\b", re.I), "#D4A017", "gold"),
    (re.compile(r"\b(olive)\b", re.I), "#6B8E23", "olive"),
    (re.compile(r"\b(forest|emerald|green)\b", re.I), "#166534", "forest"),
    (re.compile(r"\b(teal|turquoise)\b", re.I), "#0F766E", "teal"),
    (re.compile(r"\b(sky|cyan|aqua)\b", re.I), "#38BDF8", "sky"),
    (re.compile(r"\b(royal|navy|blue)\b", re.I), "#1D4ED8", "royal"),
    (re.compile(r"\b(indigo)\b", re.I), "#2F4A6E", "indigo"),
    (re.compile(r"\b(lilac|lavender|purple|violet)\b", re.I), "#A78BFA", "lilac"),
    (re.compile(r"\b(black|onyx|ebony)\b", re.I), "#111111", "black"),
    (re.compile(r"\b(white|snow)\b", re.I), "#F8F8F8", "white"),
    (re.compile(r"\b(silver|chrome|platinum)\b", re.I), "#C0C0C0", "silver"),
    (re.compile(r"\b(bronze|copper)\b", re.I), "#B87333", "bronze"),
    (re.compile(r"\b(red)\b", re.I), "#B91C1C", "red"),
    (re.compile(r"\b(yellow)\b", re.I), "#EAB308", "yellow"),
    (re.compile(r"\b(brown|tan|beige)\b", re.I), "#8B5E3C", "brown"),
]


@dataclass(frozen=True)
class FabricPromptPlan:
    prompt_raw: str
    prompt_short: str
    color_hex: str
    color_label: str
    generate_prompt: str
    name: str


def normalize_hex(raw: str | None) -> str | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    if not _HEX_RE.match(text):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Color must be a hex like #D4A017.",
        )
    if not text.startswith("#"):
        text = f"#{text}"
    return text.upper()


_DENIM_IMPLIED = re.compile(r"\b(jeans?|denim)\b", re.I)


def _extract_color_from_prompt(prompt: str) -> tuple[str, str] | None:
    for pattern, hex_color, label in _COLOR_WORDS:
        if pattern.search(prompt):
            return hex_color, label
    # Natural denim wording with no explicit color → indigo wash.
    if _DENIM_IMPLIED.search(prompt):
        return "#2F4A6E", "indigo"
    return None


def _label_for_hex(hex_color: str) -> str:
    target = hex_color.upper()
    for _, hx, label in _COLOR_WORDS:
        if hx.upper() == target:
            return label
    return target


def _missing(*, missing: list[str], message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "code": "missing_fields",
            "missing": missing,
            "message": message,
        },
    )


def validate_ai_fabric_prompt(
    *,
    prompt: str,
    color_hex: str | None = None,
    name: str | None = None,
) -> FabricPromptPlan:
    text = (prompt or "").replace("\t", " ").replace("\n", " ").replace("\r", " ")
    if _CONTROL.search(text):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prompt contains characters that are not allowed.",
        )
    text = " ".join(text.split()).strip()
    if not text:
        raise _missing(
            missing=["prompt"],
            message="Describe the fabric or pattern you want (for example: gold shiny with diamond glitter).",
        )
    if len(text) > _PROMPT_MAX:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Keep the fabric prompt to {_PROMPT_MAX} characters or fewer.",
        )

    if _BLOCKED.search(text):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unrelated prompt — describe a fabric or textile pattern only "
            "(no people, logos, brands, or outfits).",
        )
    if not _FABRIC_TERMS.search(text):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unrelated prompt — describe a fabric or textile pattern only "
            "(material, weave, print, finish, glitter, etc.).",
        )

    chosen = normalize_hex(color_hex)
    if chosen:
        color_label = _label_for_hex(chosen)
    else:
        extracted = _extract_color_from_prompt(text)
        if not extracted:
            raise _missing(
                missing=["color"],
                message="Add a color in the prompt, or pick one from the palette.",
            )
        chosen, color_label = extracted

    # Fashion-safe short hint for Magic/Try On — avoid sheer/see-through wording that
    # trips OpenAI sexual input moderation when used as design evidence.
    short_body = text
    short_body = re.sub(r"\bsee[\s-]*thr(?:ough|o+gh|u)\b", "fine-knit", short_body, flags=re.I)
    short_body = re.sub(r"\bsheer\b", "fine-knit", short_body, flags=re.I)
    short_body = re.sub(r"\btransparent\b", "fine-knit", short_body, flags=re.I)
    short = f"{color_label} {short_body}"
    short = " ".join(short.split())
    if len(short) > _SHORT_MAX:
        short = short[: _SHORT_MAX - 1].rstrip() + "…"

    display_name = (name or "").strip() or short[:80]
    display_name = " ".join(display_name.split())[:80]

    generate_prompt = (
        "Seamless repeating fashion textile swatch, top-down flat fabric tile, "
        f"dominant color {chosen} ({color_label}). "
        f"Exact designer request: {text}. "
        "Photoreal fabric surface only — no garment silhouette, no mannequin, no person, "
        "no logo, no text, no border, edge-to-edge tileable pattern suitable for fill tiling. "
        "Luxury fashion textile quality, crisp detail, even lighting."
    )

    return FabricPromptPlan(
        prompt_raw=text,
        prompt_short=short,
        color_hex=chosen,
        color_label=color_label,
        generate_prompt=generate_prompt,
        name=display_name,
    )
