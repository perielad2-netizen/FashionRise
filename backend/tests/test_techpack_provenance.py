"""Truthful Basic vs AI Professional PDF provenance (no paid calls)."""

from __future__ import annotations

from app.services.techpack_pdf import resolve_generation_provenance


def test_provenance_none_without_generate():
    prov = resolve_generation_provenance(
        {
            "schema_version": "2.0",
            "outfit": {"pieces": [{"id": "p1", "category": "dress", "label": "Dress"}]},
            "ai": {"last_run_id": None, "paid_sections": []},
        }
    )
    assert prov["is_professional"] is False
    assert prov["mode"] == "none"
    assert "No AI" in prov["label"]
    assert prov["paid_sections"] == []


def test_provenance_heuristic_is_basic_not_professional():
    prov = resolve_generation_provenance(
        {
            "schema_version": "2.0",
            "outfit": {
                "pieces": [
                    {
                        "id": "p1",
                        "category": "dress",
                        "illustrations": {"mode": "heuristic", "artifacts": {}},
                    }
                ]
            },
            "ai": {
                "last_mode": "heuristic",
                "paid_sections": [],
                "actual_cost_usd_cents": 0,
            },
        }
    )
    assert prov["is_professional"] is False
    assert prov["mode"] == "heuristic"
    assert "Basic" in prov["label"]
    assert "Professional" in prov["label"]


def test_provenance_requires_artifacts_for_professional_claim():
    # Claiming professional without artifacts must not pass.
    prov = resolve_generation_provenance(
        {
            "schema_version": "2.0",
            "outfit": {
                "pieces": [
                    {
                        "id": "p1",
                        "category": "dress",
                        "illustrations": {"mode": "professional", "artifacts": {}},
                    }
                ]
            },
            "ai": {
                "last_mode": "professional",
                "last_run_id": "run-1",
                "paid_sections": ["flat_front"],
            },
        }
    )
    assert prov["is_professional"] is False


def test_provenance_professional_with_artifacts():
    prov = resolve_generation_provenance(
        {
            "schema_version": "2.0",
            "outfit": {
                "pieces": [
                    {
                        "id": "p1",
                        "category": "dress",
                        "illustrations": {
                            "mode": "professional",
                            "artifacts": {
                                "flat_front": {
                                    "storage_key": "u/d/a.png",
                                    "id": "art-1",
                                }
                            },
                        },
                    }
                ]
            },
            "ai": {
                "last_mode": "professional",
                "last_run_id": "run-pro",
                "vision_model": "gpt-6-luna",
                "image_model": "gpt-image-2.5-sunburst",
                "actual_cost_usd_cents": 210,
                "paid_sections": ["vision_analysis", "technical_flats"],
            },
        }
    )
    assert prov["is_professional"] is True
    assert prov["mode"] == "professional"
    assert prov["run_id"] == "run-pro"
    assert prov["vision_model"] == "gpt-6-luna"
    assert prov["actual_cost_usd_cents"] == 210
    assert "flat_front" in prov["artifact_kinds"]
