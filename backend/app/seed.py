"""Idempotent catalog seed (materials, templates, palettes)."""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.color_palette import ColorPalette
from app.models.garment_template import GarmentTemplate
from app.models.material_definition import MaterialDefinition


def _uid(key: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"fashionrise:{key}")


def _ensure_material(
    db: Session,
    *,
    key: str,
    name: str,
    family: str,
    description: str,
    **kwargs: Any,
) -> None:
    mid = _uid(f"material:{key}")
    if db.get(MaterialDefinition, mid):
        return
    db.add(
        MaterialDefinition(
            id=mid,
            name=name,
            family=family,
            description=description,
            **kwargs,
        )
    )


def _ensure_template(
    db: Session,
    *,
    key: str,
    name: str,
    category: str,
    description: str,
    template_data: dict[str, Any],
) -> None:
    tid = _uid(f"template:{key}")
    if db.get(GarmentTemplate, tid):
        return
    db.add(
        GarmentTemplate(
            id=tid,
            name=name,
            category=category,
            description=description,
            template_data=template_data,
        )
    )


def _ensure_palette(
    db: Session,
    *,
    key: str,
    name: str,
    colors: list[Any],
    tags: list[str],
) -> None:
    pid = _uid(f"palette:{key}")
    if db.get(ColorPalette, pid):
        return
    db.add(ColorPalette(id=pid, name=name, colors=colors, tags=tags))


def run_seed() -> None:
    db = SessionLocal()
    try:
        catalog: list[tuple[str, str, str, str, dict[str, Any]]] = [
            (
                "satin",
                "Satin",
                "woven",
                "High-sheen woven face with fluid drape.",
                {
                    "sheen_level": 0.92,
                    "softness_level": 0.78,
                    "weight_class": "light",
                    "drape_character": "fluid",
                    "stretch_level": 0.05,
                    "luxury_score": 9,
                    "season_tags": ["spring", "summer"],
                    "recommended_categories": ["dress", "top"],
                },
            ),
            (
                "silk",
                "Silk",
                "natural",
                "Luxurious natural protein fiber.",
                {
                    "sheen_level": 0.85,
                    "softness_level": 0.95,
                    "weight_class": "light",
                    "drape_character": "fluid",
                    "stretch_level": 0.08,
                    "luxury_score": 10,
                    "season_tags": ["spring", "summer", "fall"],
                    "recommended_categories": ["dress", "skirt"],
                    "v2_profile": {
                        "premium_tier": 3,
                        "real_world_usage": "Evening blouses, bias dresses, lingerie-facing layers.",
                        "drape_tags": ["liquid", "bias-friendly"],
                        "seasonal_suitability": ["spring", "summer", "fall"],
                        "occasion_suitability": ["evening", "bridal", "resort"],
                        "material_role": "primary",
                        "pairing_recommendations": ["chiffon", "lace trim", "matte crepe"],
                        "care_complexity": "specialist_clean",
                        "texture_set_refs": ["silk_face_hi", "silk_face_lo"],
                        "render_parameter_group": "natural_fiber_sheen",
                        "supplier_metadata": {"placeholder": True},
                    },
                },
            ),
            (
                "cotton",
                "Cotton",
                "staple",
                "Breathable staple fiber.",
                {
                    "sheen_level": 0.15,
                    "softness_level": 0.72,
                    "weight_class": "medium",
                    "drape_character": "soft-tailored",
                    "stretch_level": 0.12,
                    "luxury_score": 5,
                    "season_tags": ["spring", "summer", "fall"],
                    "recommended_categories": ["top", "dress"],
                },
            ),
            (
                "linen",
                "Linen",
                "plant",
                "Cool, textured plant fiber.",
                {
                    "sheen_level": 0.12,
                    "softness_level": 0.55,
                    "weight_class": "medium",
                    "drape_character": "structured-relaxed",
                    "stretch_level": 0.04,
                    "luxury_score": 6,
                    "season_tags": ["spring", "summer"],
                    "recommended_categories": ["dress", "skirt"],
                },
            ),
            (
                "denim",
                "Denim",
                "twill",
                "Sturdy twill — casual utility.",
                {
                    "sheen_level": 0.08,
                    "softness_level": 0.45,
                    "weight_class": "heavy",
                    "drape_character": "firm",
                    "stretch_level": 0.18,
                    "luxury_score": 4,
                    "season_tags": ["fall", "winter", "spring"],
                    "recommended_categories": ["skirt", "top"],
                },
            ),
            (
                "wool",
                "Wool",
                "animal",
                "Warm, resilient animal fiber.",
                {
                    "sheen_level": 0.22,
                    "softness_level": 0.68,
                    "weight_class": "medium-heavy",
                    "drape_character": "tailored",
                    "stretch_level": 0.15,
                    "luxury_score": 8,
                    "season_tags": ["fall", "winter"],
                    "recommended_categories": ["dress", "top"],
                },
            ),
            (
                "chiffon",
                "Chiffon",
                "sheer",
                "Sheer, lightweight weave.",
                {
                    "sheen_level": 0.35,
                    "softness_level": 0.82,
                    "weight_class": "light",
                    "drape_character": "airy",
                    "stretch_level": 0.06,
                    "luxury_score": 7,
                    "season_tags": ["spring", "summer"],
                    "recommended_categories": ["dress", "top"],
                },
            ),
            (
                "tulle",
                "Tulle",
                "net",
                "Open net structure — volume.",
                {
                    "sheen_level": 0.28,
                    "softness_level": 0.35,
                    "weight_class": "light",
                    "drape_character": "voluminous",
                    "stretch_level": 0.25,
                    "luxury_score": 7,
                    "season_tags": ["spring", "summer"],
                    "recommended_categories": ["dress", "skirt"],
                },
            ),
            (
                "velvet",
                "Velvet",
                "pile",
                "Dense pile surface.",
                {
                    "sheen_level": 0.55,
                    "softness_level": 0.9,
                    "weight_class": "medium-heavy",
                    "drape_character": "sculptural",
                    "stretch_level": 0.1,
                    "luxury_score": 9,
                    "season_tags": ["fall", "winter"],
                    "recommended_categories": ["dress", "top"],
                },
            ),
            (
                "leather",
                "Leather",
                "hide",
                "Structured hide or alternative.",
                {
                    "sheen_level": 0.4,
                    "softness_level": 0.4,
                    "weight_class": "heavy",
                    "drape_character": "firm",
                    "stretch_level": 0.02,
                    "luxury_score": 9,
                    "season_tags": ["fall", "winter"],
                    "recommended_categories": ["top", "skirt"],
                },
            ),
            (
                "knit",
                "Knit",
                "knit",
                "Loop-constructed textile.",
                {
                    "sheen_level": 0.18,
                    "softness_level": 0.88,
                    "weight_class": "light-medium",
                    "drape_character": "soft-drape",
                    "stretch_level": 0.45,
                    "luxury_score": 5,
                    "season_tags": ["spring", "fall", "winter"],
                    "recommended_categories": ["top", "dress"],
                },
            ),
        ]
        for key, name, family, desc, extra in catalog:
            meta: dict[str, Any] = {}
            if v2 := extra.get("v2_profile"):
                meta["v2"] = v2
            _ensure_material(
                db,
                key=key,
                name=name,
                family=family,
                description=desc,
                sheen_level=extra.get("sheen_level"),
                softness_level=extra.get("softness_level"),
                weight_class=extra.get("weight_class"),
                drape_character=extra.get("drape_character"),
                stretch_level=extra.get("stretch_level"),
                luxury_score=extra.get("luxury_score"),
                season_tags=extra.get("season_tags", []),
                recommended_categories=extra.get("recommended_categories", []),
                metadata_=meta,
            )

        for key, name, cat, desc, data in [
            ("bias_slip", "Bias Slip", "dress", "Clean bias-cut silhouette.", {"silhouette": "slip"}),
            ("wrap_blouse", "Wrap Blouse", "top", "Adjustable wrap closure.", {"closure": "wrap"}),
            ("a_line_skirt", "A-Line Skirt", "skirt", "Classic flattering sweep.", {"hem": "a_line"}),
            ("tailored_coord", "Tailored Coord", "two_piece", "Matched jacket + skirt set.", {"set": True}),
            ("evening_column", "Evening Column", "evening_gown", "Formal floor-length column.", {"formality": "evening"}),
            ("cocktail_wrap", "Cocktail Wrap", "cocktail_dress", "Structured cocktail wrap.", {"hem": "cocktail"}),
            ("casual_shirt_dress", "Shirt Dress", "casual_dress", "Relaxed day dress.", {"ease": "casual"}),
            ("silk_blouse", "Fluid Blouse", "blouse", "Bias-cut blouse body.", {"drape": "fluid"}),
            ("tailored_jacket", "Tailored Jacket", "jacket", "Single-breasted jacket block.", {"structure": "tailored"}),
            ("wide_leg_pant", "Wide-Leg Pant", "pants", "High-rise wide leg.", {"leg": "wide"}),
            ("coord_set_v2", "Evening Coord", "coordinated_set", "Matched evening set.", {"set": True}),
        ]:
            _ensure_template(db, key=key, name=name, category=cat, description=desc, template_data=data)

        for key, name, colors, tags in [
            (
                "ivory_noir",
                "Ivory & Noir",
                [
                    {"role": "primary", "hex": "#f7f2ea"},
                    {"role": "secondary", "hex": "#1c1a18"},
                    {"role": "accent", "hex": "#5c524a"},
                ],
                ["neutral", "evening"],
            ),
            (
                "dust_rose",
                "Dust Rose",
                [
                    {"role": "primary", "hex": "#e8d2d0"},
                    {"role": "secondary", "hex": "#9e787a"},
                    {"role": "accent", "hex": "#5e3a3e"},
                ],
                ["feminine", "soft"],
            ),
        ]:
            _ensure_palette(db, key=key, name=name, colors=colors, tags=tags)

        db.commit()
    finally:
        db.close()


def run_seed_if_configured() -> None:
    from app.core.config import get_settings

    s = get_settings()
    if s.testing or s.environment != "development":
        return
    run_seed()


if __name__ == "__main__":
    """One-off catalog seed: cd backend && .venv/bin/python -m app.seed"""
    run_seed()
