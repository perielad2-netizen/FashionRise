"""Issue #39 Magic pose fidelity: offline/mocked prompt tests.

Never call the live OpenAI API. No paid images.edit / images.generate.
Prompt unit tests assert brief language only — they do NOT prove geometric image fidelity.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services import sketch_openai


def _pose_structured(
    *,
    pose: str,
    pose_lock: dict[str, Any],
    image_prompt: str,
    asymmetry_notes: str | None = None,
    fabric_patterns: str | None = None,
) -> dict[str, Any]:
    identity: dict[str, Any] = {
        "garment_category": "dress",
        "silhouette": "fitted fashion silhouette",
        "pose": pose,
        "main_colors": "pink",
        "pose_lock": pose_lock,
    }
    if asymmetry_notes:
        identity["asymmetry_notes"] = asymmetry_notes
    if fabric_patterns:
        identity["fabric_patterns"] = fabric_patterns
    return {
        "summary": "Pose-sensitive fashion look",
        "polish_bullets": ["Keep the croquis stance", "Refine garment rendering"],
        "design_identity": identity,
        "refine_ok": ["wobbly outlines"],
        "image_prompt": image_prompt,
    }


def _bent_leg_structured() -> dict[str, Any]:
    return _pose_structured(
        pose="dynamic asymmetric stance with one bent leg",
        pose_lock={
            "torso_orientation": "torso follows hip shift, not upright square",
            "shoulder_alignment": "shoulders tilt with the stance",
            "hip_alignment": "hips angled toward the supporting side",
            "supporting_leg": "viewer's-left leg planted and weight-bearing",
            "bent_or_lifted_leg": "viewer's-right leg bent at the knee and angled away/back",
            "knee_positions": "bent free knee outward; supporting knee straighter",
            "foot_placement": "supporting boot planted; free boot heel/angle not both-flat",
            "arm_and_hand_positions": "arms follow original sketch positions",
            "body_asymmetry_and_perspective": "clear left/right asymmetry preserved",
        },
        image_prompt=(
            "Pink outfit on a croquis with one supporting planted leg and the other "
            "leg bent and angled away — not a straight upright stance."
        ),
        asymmetry_notes="asymmetric skirt hem",
        fabric_patterns="checked textile",
    )


def _crossed_legs_structured() -> dict[str, Any]:
    return _pose_structured(
        pose="crossed-leg fashion croquis stance",
        pose_lock={
            "torso_orientation": "slight fashion lean",
            "shoulder_alignment": "soft shoulder tilt",
            "hip_alignment": "hips rotated with the crossed stance",
            "supporting_leg": "front leg bears weight",
            "bent_or_lifted_leg": "rear leg crosses behind at the calves",
            "knee_positions": "rear knee bent; front knee straighter",
            "foot_placement": "rear foot on toe behind the supporting foot",
            "arm_and_hand_positions": "arms at sides as drawn",
            "body_asymmetry_and_perspective": "crossed calves create asymmetric silhouette",
        },
        image_prompt="Figure with one leg crossed behind the other at the calves.",
    )


def _hand_on_hip_structured() -> dict[str, Any]:
    return _pose_structured(
        pose="hand-on-hip fashion stance",
        pose_lock={
            "torso_orientation": "front-facing with fashion tilt",
            "shoulder_alignment": "shoulder raised slightly on the hand-on-hip side",
            "hip_alignment": "hip pushed out under the resting hand",
            "supporting_leg": "opposite leg planted",
            "bent_or_lifted_leg": "same-side leg may be soft-kneed as drawn",
            "knee_positions": "match visible knee bend",
            "foot_placement": "preserve planted vs angled feet",
            "arm_and_hand_positions": "one hand firmly on the hip; other arm as drawn",
            "body_asymmetry_and_perspective": "hand-on-hip creates clear left/right asymmetry",
        },
        image_prompt="Model with one hand resting on the hip in an asymmetric fashion pose.",
    )


def test_polish_system_prompt_requires_pose_lock_schema():
    prompt = sketch_openai._system_prompt("sketch_polish")
    lower = prompt.lower()
    assert "pose_lock" in lower
    for field in (
        "torso_orientation",
        "shoulder_alignment",
        "hip_alignment",
        "supporting_leg",
        "bent_or_lifted_leg",
        "knee_positions",
        "foot_placement",
        "arm_and_hand_positions",
        "body_asymmetry_and_perspective",
    ):
        assert field in lower
    assert "generic runway" in lower or "standing front view" in lower
    assert "never invent" in lower or "invent nothing" in lower


def test_build_image_prompt_forbids_pose_rewrite():
    prompt = sketch_openai._build_image_prompt(_bent_leg_structured(), "summary")
    lower = prompt.lower()
    assert "critical pose rules" in lower
    assert "do not straighten bent" in lower
    assert "do not lower a lifted foot" in lower or "plant both boots" in lower
    assert "generic upright runway pose" in lower
    assert "professional refinement is not a pose rewrite" in lower
    # WEB-V4E polish language must remain.
    assert "professionally refine" in lower
    assert "source of truth" in lower
    assert "do not apply only a faint watercolor or light color wash" in lower


@pytest.mark.parametrize(
    "factory,must_include",
    [
        (
            _bent_leg_structured,
            (
                "bent",
                "supporting",
                "angled",
                "pose lock",
                "checked",
                "asymmetric skirt",
            ),
        ),
        (
            _crossed_legs_structured,
            ("cross", "behind", "pose lock", "calves"),
        ),
        (
            _hand_on_hip_structured,
            ("hand", "hip", "pose lock", "asymmetry"),
        ),
    ],
)
def test_build_image_prompt_includes_concrete_pose_relationships(factory, must_include):
    structured = factory()
    prompt = sketch_openai._build_image_prompt(structured, structured["summary"])
    lower = prompt.lower()
    for token in must_include:
        assert token in lower, f"missing {token!r} in prompt"
    # Must not collapse to the weak generic summary that enabled the bug.
    assert "pose: standing front view" not in lower


def test_design_identity_skips_generic_pose_when_pose_lock_present():
    structured = _pose_structured(
        pose="standing front view",
        pose_lock={
            "supporting_leg": "left leg planted",
            "bent_or_lifted_leg": "right leg bent and lifted at the heel",
            "foot_placement": "only one boot fully planted",
            "arm_and_hand_positions": "left hand on hip",
            "body_asymmetry_and_perspective": "contrapposto asymmetry",
        },
        image_prompt="Asymmetric bent-leg stance with hand on hip.",
    )
    clause = sketch_openai._design_identity_clause(structured)
    lower = clause.lower()
    assert "standing front view" not in lower
    assert "pose lock" in lower
    assert "right leg bent" in lower
    assert "left hand on hip" in lower


def test_pose_lock_null_fields_omitted():
    structured = {
        "design_identity": {
            "pose_lock": {
                "supporting_leg": "planted right leg",
                "bent_or_lifted_leg": None,
                "foot_placement": "unknown",
                "arm_and_hand_positions": "n/a",
            }
        }
    }
    clause = sketch_openai._pose_lock_clause(structured["design_identity"])
    lower = clause.lower()
    assert "supporting leg: planted right leg" in lower
    assert "bent or lifted" not in lower
    assert "foot placement" not in lower
    assert "arm and hand" not in lower


def test_edit_prompt_still_preserves_garment_and_textile_with_pose_lock():
    structured = _bent_leg_structured()
    prompt = sketch_openai._build_image_prompt(structured, structured["summary"])
    lower = prompt.lower()
    assert "checked" in lower or "textile" in lower
    assert "silhouette" in lower
    assert "faithful colors" in lower or "richer but faithful" in lower
    assert "generic fashion outfit" in lower


def test_build_sketch_chat_request_advertises_pose_lock(monkeypatch):
    from app.core.config import Settings

    s = Settings.model_construct(
        testing=True,
        environment="development",
        openai_api_key="sk-test",
        openai_model="gpt-6-luna",
        openai_reasoning_effort="none",
        openai_max_completion_tokens=1400,
        openai_image_model="gpt-image-1",
        openai_image_size="1024x1536",
        openai_timeout_seconds=180.0,
        openai_http_timeout_seconds=60.0,
        openai_base_url=None,
    )
    monkeypatch.setattr(sketch_openai, "get_settings", lambda: s)
    job = type("J", (), {"id": "x", "job_type": "sketch_polish", "input_data": {"notes": "pose"}})()
    req = sketch_openai.build_sketch_chat_request(
        job,
        model="gpt-6-luna",
        reasoning_effort="none",
        max_completion_tokens=1400,
    )
    system = req["messages"][0]["content"]
    assert "pose_lock" in system
    assert "supporting_leg" in system
