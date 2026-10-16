"""Offline tests for the bounded gpt-6-luna eval harness. Never call the live API."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.services import sketch_openai

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "eval_gpt6_luna_live.py"


def _load_eval():
    spec = importlib.util.spec_from_file_location("eval_gpt6_luna_live", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ev():
    return _load_eval()


def _valid_payloads() -> dict[str, dict[str, Any]]:
    return {
        "sketch_clean": {
            "summary": "Clean the A-line dress silhouette and even the hem.",
            "cleanup_bullets": [
                "Redraw the boat neck as a single confident line.",
                "True the shoulder slope so both sides match.",
                "Lengthen the torso so head-to-hem proportions read as a croquis.",
                "Smooth the A-line flare from waist to knee hem.",
            ],
        },
        "sketch_polish": {
            "summary": "Portfolio-ready A-line day dress with a cleaner boat neck.",
            "polish_bullets": [
                "Add light even hatching on the bodice.",
                "Keep short sleeves and the knee hem; refine the armhole.",
                "Present the croquis on white paper with a stronger silhouette.",
            ],
            "image_prompt": "A-line dress, boat neck, short sleeves, knee hem, straw hat brim, fashion croquis.",
        },
        "style_suggest": {
            "summary": "Five coastal-summer looks around an A-line day dress.",
            "suggestions": [
                {"title": "Seafoam linen", "description": "Soft A-line dress in washable linen, boat neck."},
                {"title": "Straw hat pair", "description": "Knee hem dress with a small straw hat."},
                {"title": "Pastel stripe", "description": "Short sleeves, pale stripe, no logos."},
                {"title": "Cotton-linen mix", "description": "Breathable drape, ages 10-14, not costume."},
                {"title": "Sand walk", "description": "Coastal palette, same silhouette, easy wash."},
            ],
        },
    }


def test_dry_run_makes_zero_network_calls(ev, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("OpenAI client must not be constructed in dry-run")

    monkeypatch.setattr(ev, "open_chat_only_client", boom)
    report = ev.run_eval(execute=False, acknowledge=False, skip_git=True)
    assert report["mode"] == "dry-run"
    assert report["live_requests_made"] == 0
    assert report["safety"]["planned_chat_completions"] == 3
    assert report["safety"]["planned_image_edits"] == 0
    assert report["safety"]["planned_image_generations"] == 0
    assert report["safety"]["estimated_total_usd"] <= ev.BUDGET_USD
    assert report["safety"]["not_a_billing_guarantee"] is True
    assert report["safety"]["vision_attached"] == [True, True, False]
    assert report["planned_requests"][0]["model"] == "gpt-6-luna"
    assert report["planned_requests"][0]["reasoning_effort"] == "none"
    assert report["planned_requests"][0]["max_completion_tokens"] == 1400
    assert report["planned_requests"][0]["vision_attached"] is True
    assert report["planned_requests"][2]["vision_attached"] is False
    blob = json.dumps(report)
    assert "sk-" not in blob
    assert "base64," not in blob


def test_execute_without_ack_is_refused(ev):
    with pytest.raises(ev.EvalGuardError, match="acknowledge-paid-test"):
        ev.run_eval(execute=True, acknowledge=False, skip_git=True)
    assert ev.main(["--execute"]) == 2


def test_image_guard_blocks_edit_and_generate(ev):
    images = ev._ForbiddenImages()
    with pytest.raises(ev.EvalGuardError, match="images.edit"):
        images.edit(model="gpt-image-1", prompt="x")
    with pytest.raises(ev.EvalGuardError, match="images.generate"):
        images.generate(model="gpt-image-1", prompt="x")


def test_contracts_accept_valid_and_reject_bad(ev):
    payloads = _valid_payloads()
    for job_type, payload in payloads.items():
        assert ev.validate_contract(job_type, payload) == []
    assert ev.validate_contract("sketch_clean", {"summary": "x", "cleanup_bullets": ["a"]})
    assert ev.validate_contract(
        "sketch_polish",
        {
            "summary": "x",
            "polish_bullets": ["a", "b", "c"],
            "image_prompt": "a red sports car on a racetrack",
        },
    )
    assert ev.validate_contract(
        "style_suggest",
        {"summary": "x", "suggestions": [{"title": "A", "description": ""}] * 5},
    )


def test_mocked_live_path_never_calls_images(ev):
    payloads = _valid_payloads()
    calls: list[str] = []

    def create(**kwargs):
        calls.append(kwargs["messages"][0]["content"][:40])
        assert kwargs["model"] == "gpt-6-luna"
        assert kwargs["reasoning_effort"] == "none"
        job_type = "sketch_clean"
        if "portfolio" in json.dumps(kwargs["messages"]).lower():
            job_type = "sketch_polish"
        elif "coastal" in json.dumps(kwargs["messages"]).lower():
            job_type = "style_suggest"
        content = json.dumps(payloads[job_type])
        usage = SimpleNamespace(
            prompt_tokens=200,
            completion_tokens=80,
            total_tokens=280,
            completion_tokens_details=SimpleNamespace(reasoning_tokens=0),
        )
        return SimpleNamespace(
            model="gpt-6-luna",
            usage=usage,
            choices=[SimpleNamespace(message=SimpleNamespace(content=content, refusal=None), finish_reason="stop")],
        )

    report = ev.run_eval(
        execute=True,
        acknowledge=True,
        skip_git=True,
        chat_create=create,
        environ={"OPENAI_API_KEY": "sk-test-not-a-real-key"},
    )
    assert report["live_requests_made"] == 3
    assert report["pass"] is True
    assert all(r["pass"] for r in report["results"])
    assert len(calls) == 3
    blob = json.dumps(report)
    assert "sk-test-not-a-real-key" not in blob


def test_mocked_live_stops_on_invalid_json(ev):
    def create(**kwargs):
        return SimpleNamespace(
            model="gpt-6-luna",
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content="not-json", refusal=None), finish_reason="stop")],
        )

    with pytest.raises(sketch_openai.SketchCompletionError, match="invalid JSON"):
        ev.run_eval(
            execute=True,
            acknowledge=True,
            skip_git=True,
            chat_create=create,
            environ={"OPENAI_API_KEY": "sk-test-not-a-real-key"},
        )


def test_cli_default_is_dry_run(ev, capsys):
    code = ev.main([])
    assert code == 0
    out = capsys.readouterr().out
    assert "dry-run" in out
    assert "live_requests_made: 0" in out
    assert "sk-" not in out


def test_build_sketch_chat_request_is_production_builder(ev):
    scenarios = ev.synthetic_scenarios()
    kwargs = ev.build_scenario_request(scenarios[0])
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["messages"][0]["role"] == "system"
    assert "cleanup_bullets" in kwargs["messages"][0]["content"]
    user = kwargs["messages"][1]["content"]
    assert user[0]["type"] == "text"
    assert user[1]["type"] == "image_url"
    assert user[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_production_complete_job_still_uses_shared_builder(monkeypatch):
    captured: list[dict] = []

    def wrap(job, **kw):
        captured.append(kw)
        return sketch_openai.chat_completion_kwargs(
            model=kw["model"],
            messages=[{"role": "system", "content": "x"}, {"role": "user", "content": "y"}],
            max_completion_tokens=kw["max_completion_tokens"],
            reasoning_effort=kw["reasoning_effort"],
        )

    monkeypatch.setattr(sketch_openai, "build_sketch_chat_request", wrap)
    monkeypatch.setattr(
        sketch_openai,
        "get_settings",
        lambda: SimpleNamespace(
            openai_api_key="sk-test-not-a-real-key",
            openai_model="gpt-6-luna",
            openai_reasoning_effort="none",
            openai_max_completion_tokens=1400,
            openai_timeout_seconds=180.0,
            openai_base_url=None,
        ),
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **k: SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content='{"summary":"ok","cleanup_bullets":["a","b","c"]}', refusal=None),
                            finish_reason="stop",
                        )
                    ]
                )
            )
        )
    )
    monkeypatch.setattr(sketch_openai, "OpenAI", lambda **kw: client)
    result = sketch_openai.complete_sketch_job(SimpleNamespace(id=1, job_type="sketch_clean", input_data={"notes": "x"}))
    assert captured and captured[0]["model"] == "gpt-6-luna"
    assert result["summary"] == "ok"
