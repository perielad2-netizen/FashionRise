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


def _weak_payloads() -> dict[str, dict[str, Any]]:
    return {
        "sketch_clean": {
            "summary": "Make it nicer.",
            "cleanup_bullets": ["Make it better.", "Improve it.", "Great job overall."],
        },
        "sketch_polish": {
            "summary": "Nice drawing.",
            "polish_bullets": ["Make it better.", "Improve it.", "Awesome finish."],
            "image_prompt": "a dress on paper",
        },
        "style_suggest": {
            "summary": "Nice looks.",
            "suggestions": [
                {"title": f"Look {i}", "description": "Make it better."} for i in range(1, 6)
            ],
        },
    }


def _job_type_from_kwargs(kwargs: dict[str, Any]) -> str:
    blob = json.dumps(kwargs["messages"]).lower()
    if "portfolio" in blob:
        return "sketch_polish"
    if "coastal" in blob:
        return "style_suggest"
    return "sketch_clean"


def _completion(
    payload: dict[str, Any] | str,
    *,
    model: str | None = "gpt-6-luna",
    finish_reason: str = "stop",
    prompt_tokens: int | None = 200,
    completion_tokens: int | None = 80,
    usage: bool = True,
    refusal: str | None = None,
):
    content = payload if isinstance(payload, str) else json.dumps(payload)
    usage_obj = None
    if usage:
        usage_obj = SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=(prompt_tokens or 0) + (completion_tokens or 0),
            completion_tokens_details=SimpleNamespace(reasoning_tokens=0),
        )
    return SimpleNamespace(
        model=model,
        usage=usage_obj,
        choices=[SimpleNamespace(message=SimpleNamespace(content=content, refusal=refusal), finish_reason=finish_reason)],
    )


def _live_env() -> dict[str, str]:
    return {"OPENAI_API_KEY": "sk-test-not-a-real-key"}


def test_dry_run_makes_zero_network_calls(ev, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("OpenAI client must not be constructed in dry-run")

    monkeypatch.setattr(ev, "open_chat_only_client", boom)
    report = ev.run_eval(execute=False, acknowledge=False, skip_git=True)
    assert report["mode"] == "dry-run"
    assert report["outcome"] == "DRY_RUN"
    assert report["live_requests_made"] == 0
    assert report["safety"]["planned_chat_completions"] == 3
    assert report["safety"]["planned_image_edits"] == 0
    assert report["safety"]["planned_image_generations"] == 0
    assert report["safety"]["estimated_total_usd"] <= ev.BUDGET_USD
    assert report["safety"]["not_a_billing_guarantee"] is True
    assert "not an absolute billing guarantee" in report["safety"]["billing_disclaimer"]
    assert report["safety"]["official_base_url"] == "https://api.openai.com/v1"
    assert report["safety"]["vision_attached"] == [True, True, False]
    assert all(r["status"] == "NOT RUN" for r in report["results"])
    assert report["human_quality_review_required"] is True
    blob = json.dumps(report)
    assert "sk-" not in blob
    assert "base64," not in blob


def test_execute_without_ack_is_refused(ev, monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr(ev, "open_chat_only_client", lambda *a, **k: opened.append("client"))
    with pytest.raises(ev.EvalGuardError, match="acknowledge-paid-test"):
        ev.run_eval(execute=True, acknowledge=False, skip_git=True, environ=_live_env())
    assert opened == []
    assert ev.main(["--execute"]) == 2


def test_missing_api_key_makes_zero_network_calls(ev, monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr(ev, "open_chat_only_client", lambda *a, **k: opened.append("client"))
    with pytest.raises(ev.EvalGuardError, match="OPENAI_API_KEY"):
        ev.run_eval(execute=True, acknowledge=True, skip_git=True, environ={})
    assert opened == []


def test_unexpected_base_url_makes_zero_network_calls(ev):
    calls: list[str] = []

    def create(**kwargs):
        calls.append("create")
        raise AssertionError("must not call the provider")

    with pytest.raises(ev.EvalGuardError, match="official"):
        ev.run_eval(
            execute=True,
            acknowledge=True,
            skip_git=True,
            chat_create=create,
            environ={
                "OPENAI_API_KEY": "sk-test-not-a-real-key",
                "OPENAI_BASE_URL": "https://example.openai.azure.com/openai/v1",
            },
        )
    assert calls == []


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
        calls.append(_job_type_from_kwargs(kwargs))
        assert kwargs["model"] == "gpt-6-luna"
        assert kwargs["reasoning_effort"] == "none"
        return _completion(payloads[_job_type_from_kwargs(kwargs)])

    report = ev.run_eval(
        execute=True,
        acknowledge=True,
        skip_git=True,
        chat_create=create,
        environ=_live_env(),
    )
    assert report["live_requests_made"] == 3
    assert report["outcome"] == "PASS"
    assert report["api_compatibility"] == "PASS"
    assert report["json_contract"] == "PASS"
    assert report["automated_quality"] == "PASS"
    assert report["human_quality_review_required"] is True
    assert report["live_image_calls"] == 0
    assert len(calls) == 3
    blob = json.dumps(report)
    assert "sk-test-not-a-real-key" not in blob


def test_returned_model_mismatch_stops_after_one_call(ev):
    calls: list[str] = []

    def create(**kwargs):
        calls.append("create")
        return _completion(_valid_payloads()["sketch_clean"], model="gpt-4o-mini")

    report = ev.run_eval(
        execute=True,
        acknowledge=True,
        skip_git=True,
        chat_create=create,
        environ=_live_env(),
    )
    assert calls == ["create"]
    assert report["live_requests_made"] == 1
    assert report["outcome"] == "FAIL"
    assert report["results"][0]["status"] == "FAIL"
    assert report["results"][1]["status"] == "NOT RUN"
    assert report["results"][2]["status"] == "NOT RUN"
    assert "gpt-6-luna" in report["stopped_reason"]


def test_missing_usage_stops_after_one_call(ev):
    calls: list[str] = []

    def create(**kwargs):
        calls.append("create")
        return _completion(_valid_payloads()["sketch_clean"], usage=False)

    report = ev.run_eval(
        execute=True,
        acknowledge=True,
        skip_git=True,
        chat_create=create,
        environ=_live_env(),
    )
    assert calls == ["create"]
    assert report["live_requests_made"] == 1
    assert report["outcome"] == "FAIL"
    assert report["results"][1]["status"] == "NOT RUN"
    assert "usage" in report["stopped_reason"]
    assert report["estimated_spend_usd"] is None
    assert report["results"][0].get("review_output") is None


def test_invalid_json_stops_after_one_call(ev):
    calls: list[str] = []

    def create(**kwargs):
        calls.append("create")
        return _completion("not-json")

    report = ev.run_eval(
        execute=True,
        acknowledge=True,
        skip_git=True,
        chat_create=create,
        environ=_live_env(),
    )
    assert calls == ["create"]
    assert report["live_requests_made"] == 1
    assert report["outcome"] == "FAIL"
    assert report["results"][0]["json_contract"] == "FAIL"
    assert report["results"][1]["status"] == "NOT RUN"
    assert report["pass"] is False
    assert "invalid JSON" in report["stopped_reason"]


def test_provider_exception_is_sanitized_and_not_retried(ev):
    class FakeRateLimit(Exception):
        status_code = 429

    calls: list[str] = []

    def create(**kwargs):
        calls.append("create")
        raise FakeRateLimit("sk-secret leaked body with image bytes")

    report = ev.run_eval(
        execute=True,
        acknowledge=True,
        skip_git=True,
        chat_create=create,
        environ=_live_env(),
    )
    assert calls == ["create"]
    assert report["live_requests_made"] == 1
    assert report["outcome"] == "FAIL"
    assert report["failure"]["class"] == "rate_limit"
    blob = json.dumps(report)
    assert "sk-secret" not in blob
    assert "image bytes" not in blob
    assert report["results"][1]["status"] == "NOT RUN"
    assert report["pass"] is False


def test_budget_exhaustion_stops_before_next_request(ev):
    calls: list[str] = []

    def create(**kwargs):
        calls.append(_job_type_from_kwargs(kwargs))
        return _completion(
            _valid_payloads()["sketch_clean"],
            prompt_tokens=490_000,
            completion_tokens=1400,
        )

    report = ev.run_eval(
        execute=True,
        acknowledge=True,
        skip_git=True,
        chat_create=create,
        environ=_live_env(),
    )
    assert calls == ["sketch_clean"]
    assert report["live_requests_made"] == 1
    assert report["outcome"] == "FAIL"
    assert report["results"][0]["status"] == "PASS"
    assert report["results"][1]["status"] == "NOT RUN"
    assert "exceed" in report["stopped_reason"]
    assert report["estimated_spend_usd"] > 0


def test_quality_warnings_are_conditional(ev):
    weak = _weak_payloads()

    def create(**kwargs):
        return _completion(weak[_job_type_from_kwargs(kwargs)])

    report = ev.run_eval(
        execute=True,
        acknowledge=True,
        skip_git=True,
        chat_create=create,
        environ=_live_env(),
    )
    assert report["live_requests_made"] == 3
    assert report["json_contract"] == "PASS"
    assert report["api_compatibility"] == "PASS"
    assert report["automated_quality"] == "CONDITIONAL"
    assert report["outcome"] == "CONDITIONAL"
    assert report["pass"] is False
    assert report["human_quality_review_required"] is True
    assert any(r["status"] == "CONDITIONAL" for r in report["results"])


def test_unreviewed_integration_changes_block_live(ev, monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr(
        ev,
        "verify_integration_baseline",
        lambda: (_ for _ in ()).throw(ev.EvalGuardError("reviewed integration files differ from baseline")),
    )
    monkeypatch.setattr(ev, "open_chat_only_client", lambda *a, **k: opened.append("client"))

    def create(**kwargs):
        opened.append("create")
        raise AssertionError("must not call the provider")

    with pytest.raises(ev.EvalGuardError, match="reviewed integration files"):
        ev.run_eval(
            execute=True,
            acknowledge=True,
            skip_git=True,
            skip_integration_check=False,
            chat_create=create,
            environ=_live_env(),
        )
    assert opened == []


def test_cli_default_is_dry_run(ev, capsys, monkeypatch):
    # Dry-run CLI still calls verify_repo_state; stub it so feature branches can run the suite.
    monkeypatch.setattr(
        ev,
        "verify_repo_state",
        lambda: {"branch": "test-branch", "head": "0" * 40, "baseline_ancestor": True},
    )
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


def test_review_output_present_for_all_three_successes(ev):
    payloads = _valid_payloads()
    payloads["sketch_clean"]["summary"] = "Nettoie la silhouette A-line et égalise l’ourlet."
    calls: list[str] = []

    def create(**kwargs):
        calls.append(_job_type_from_kwargs(kwargs))
        return _completion(payloads[_job_type_from_kwargs(kwargs)])

    report = ev.run_eval(
        execute=True,
        acknowledge=True,
        skip_git=True,
        chat_create=create,
        environ=_live_env(),
    )
    assert calls == ["sketch_clean", "sketch_polish", "style_suggest"]
    assert report["live_requests_made"] == 3
    assert report["live_image_calls"] == 0
    clean, polish, style = (r["review_output"] for r in report["results"])
    assert set(clean) == {"summary", "cleanup_bullets"}
    assert clean["summary"] == payloads["sketch_clean"]["summary"]
    assert "ourlet" in clean["summary"]
    assert clean["cleanup_bullets"] == payloads["sketch_clean"]["cleanup_bullets"]
    assert set(polish) == {"summary", "polish_bullets", "image_prompt"}
    assert polish["image_prompt"] == payloads["sketch_polish"]["image_prompt"]
    assert set(style) == {"summary", "suggestions"}
    assert len(style["suggestions"]) == 5
    assert all(set(s) == {"title", "description"} for s in style["suggestions"])
    blob = json.dumps(report, ensure_ascii=False)
    assert "sk-test-not-a-real-key" not in blob
    assert "base64," not in blob
    assert "data:image" not in blob


def test_review_output_is_length_bounded(ev):
    huge = "α" * 5000
    out = ev.review_output(
        "sketch_clean",
        {"summary": huge, "cleanup_bullets": [huge] * 12},
    )
    assert out["summary"] == "α" * ev.REVIEW_SUMMARY_CHARS
    assert len(out["cleanup_bullets"]) == ev.REVIEW_CLEANUP_MAX
    assert all(item == "α" * ev.REVIEW_BULLET_CHARS for item in out["cleanup_bullets"])
    polish = ev.review_output(
        "sketch_polish",
        {"summary": huge, "polish_bullets": [huge] * 9, "image_prompt": huge},
    )
    assert polish["image_prompt"] == "α" * ev.REVIEW_PROMPT_CHARS
    assert len(polish["polish_bullets"]) == ev.REVIEW_POLISH_MAX
    style = ev.review_output(
        "style_suggest",
        {"summary": huge, "suggestions": [{"title": huge, "description": huge, "extra": "drop"}] * 9},
    )
    assert len(style["suggestions"]) == ev.REVIEW_SUGGESTIONS_MAX
    assert all(set(s) == {"title", "description"} for s in style["suggestions"])
    assert all(len(s["title"]) == ev.REVIEW_TITLE_CHARS for s in style["suggestions"])


def test_failure_report_omits_raw_provider_content_and_review_output(ev):
    class FakeAuth(Exception):
        status_code = 401

    def create(**kwargs):
        raise FakeAuth('{"error":"sk-secret","image":"data:image/png;base64,AAAA"}')

    report = ev.run_eval(
        execute=True,
        acknowledge=True,
        skip_git=True,
        chat_create=create,
        environ=_live_env(),
    )
    assert report["live_requests_made"] == 1
    assert report["live_image_calls"] == 0
    assert report["estimated_spend_usd"] is None
    failed = report["results"][0]
    assert failed.get("review_output") is None
    assert "summary" not in failed
    blob = json.dumps(report)
    assert "sk-secret" not in blob
    assert "base64" not in blob
    assert "AAAA" not in blob
    assert report["failure"]["class"] == "authentication"
