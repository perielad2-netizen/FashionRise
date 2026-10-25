"""Trusted selected croquis / reference-model identity for Magic polish.

The frontend sends ``reference_model_id`` with sketch_polish. Built-in and legacy
IDs carry an authoritative fashion-croquis family (male/female). Custom and blank
do not invent a gender. Missing metadata stays backward-compatible (no failure,
no female default injected into prompts).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.core.errors import ValidationAppError

CroquisFamily = Literal["female", "male"]
ReferenceKind = Literal["builtin", "legacy", "utility"]

# Exact allowlist — must stay aligned with web-ui/src/assets/modelLibrary.ts.
SELECTABLE_FEMALE_IDS = frozenset(
    {
        "female-straight",
        "female-hand-hip",
        "female-contrapposto",
        "female-cross-ankle",
        "female-atelier",
        "female-cross-leg",
    }
)
SELECTABLE_MALE_IDS = frozenset(
    {
        "male-straight",
        "male-step",
        "male-walk",
        "male-contrapposto",
    }
)
LEGACY_IDS = frozenset({"female", "male"})
UTILITY_IDS = frozenset({"custom", "blank"})
ALLOWED_REFERENCE_MODEL_IDS = (
    SELECTABLE_FEMALE_IDS | SELECTABLE_MALE_IDS | LEGACY_IDS | UTILITY_IDS
)


@dataclass(frozen=True)
class ReferenceCroquis:
    """Validated selected-reference metadata for a Magic polish job."""

    model_id: str
    kind: ReferenceKind
    family: CroquisFamily | None  # None for custom/blank — do not invent


def parse_reference_model_id(raw: Any) -> ReferenceCroquis | None:
    """Return validated reference metadata, or None when the field is absent.

    Raises ValidationAppError for present-but-invalid values.
    """
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValidationAppError("reference_model_id must be a string")
    model_id = raw.strip()
    if not model_id:
        return None
    if model_id not in ALLOWED_REFERENCE_MODEL_IDS:
        raise ValidationAppError("reference_model_id is not a recognized Studio model")
    if model_id in UTILITY_IDS:
        return ReferenceCroquis(model_id=model_id, kind="utility", family=None)
    if model_id in LEGACY_IDS:
        family: CroquisFamily = "male" if model_id == "male" else "female"
        return ReferenceCroquis(model_id=model_id, kind="legacy", family=family)
    family = "male" if model_id in SELECTABLE_MALE_IDS else "female"
    return ReferenceCroquis(model_id=model_id, kind="builtin", family=family)


def reference_from_job_input(input_data: dict[str, Any] | None) -> ReferenceCroquis | None:
    """Read ``reference_model_id`` from job input_data (snake or camel)."""
    if not isinstance(input_data, dict):
        return None
    if "reference_model_id" in input_data:
        return parse_reference_model_id(input_data.get("reference_model_id"))
    if "referenceModelId" in input_data:
        return parse_reference_model_id(input_data.get("referenceModelId"))
    return None


def vision_reference_instructions(ref: ReferenceCroquis | None) -> str:
    """Authoritative instructions for Chat Completions (vision) analysis."""
    if ref is None:
        return (
            "SELECTED STUDIO REFERENCE: not provided by this client. "
            "Infer the croquis presentation only from the attached sketch. "
            "Do not invent or force a female fashion figure when evidence is ambiguous."
        )
    if ref.kind == "utility":
        return (
            f"SELECTED STUDIO REFERENCE: `{ref.model_id}` (no explicit male/female library selection). "
            "Preserve the figure as drawn in the sketch. "
            "Do NOT invent an explicit male or female fashion-model family the designer did not select. "
            "Do NOT default to a female-presenting runway figure."
        )
    assert ref.family is not None
    opposite = "female" if ref.family == "male" else "male"
    return (
        f"SELECTED STUDIO REFERENCE (authoritative): `{ref.model_id}` — "
        f"{ref.family} fashion-croquis family ({ref.kind}). "
        f"The designer explicitly selected this {ref.family} croquis. "
        f"Extract design_identity for THIS {ref.family} figure only. "
        f"Do NOT reinterpret the croquis as a {opposite}-presenting fashion model. "
        "Do NOT invent feminine facial/hair/body styling for a male croquis, or masculine "
        "restyling for a female croquis, merely because a garment silhouette resembles clothing "
        "commonly worn by another presentation. "
        "Preserve body proportions, visible anatomy, pose, stance, arms, and legs from the sketch. "
        "If your initial impression conflicts with the selected reference, the selected reference wins."
    )


def edit_reference_instructions(ref: ReferenceCroquis | None) -> str:
    """Authoritative instructions reserved in the images.edit brief."""
    if ref is None:
        return (
            "SELECTED STUDIO REFERENCE: not provided. Preserve the figure presentation visible "
            "in the uploaded sketch; do not invent a different fashion-model family."
        )
    if ref.kind == "utility":
        return (
            f"SELECTED STUDIO REFERENCE: `{ref.model_id}` (custom/blank — no explicit gender selection). "
            "Preserve the figure as drawn. Do not invent a male or female library croquis identity. "
            "Do not default to a female-presenting fashion figure."
        )
    assert ref.family is not None
    opposite = "female" if ref.family == "male" else "male"
    return (
        f"SELECTED STUDIO REFERENCE (authoritative; overrides conflicting vision text): "
        f"`{ref.model_id}` — preserve this {ref.family} fashion-croquis presentation, "
        f"original body proportions, visible anatomy, pose, stance, arms, and legs. "
        f"Do NOT replace the croquis with a {opposite}-presenting fashion figure. "
        f"Do NOT invent {opposite} facial features, hair styling, or body styling. "
        "Professionally refine the garment construction, textiles, colors, and presentation only."
    )
