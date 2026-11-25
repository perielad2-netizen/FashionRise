"""OpenAI + FASHN Admin financial intelligence — mocked providers only."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.main import app
from app.models.ai_cost_accounting import (
    CREDITS_KIND_ACTUAL,
    CREDITS_KIND_UNAVAILABLE,
    FashnPredictionCost,
    OpenAiCostDaily,
    OperatorExpenseRecord,
)
from app.models.user import User
from app.services.ai_cost_accounting import (
    build_ai_financial_section,
    build_income_vs_expenses,
    record_fashn_prediction,
)
from app.services.fashn_credit_sync import parse_credits_payload, set_fashn_credit_http_override, sync_fashn_credits
from app.services.openai_cost_sync import (
    parse_costs_page,
    set_openai_cost_http_override,
    sync_openai_costs,
)


@pytest.fixture()
def client(db_session: Session):
    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


def _user(db: Session, *, username: str, is_admin: bool = False, classification: str = "CUSTOMER") -> User:
    u = User(
        id=uuid.uuid4(),
        email=f"{username}@example.com",
        username=username,
        hashed_password=hash_password("Password123!"),
        is_active=True,
        is_admin=is_admin,
        ai_stars=10,
        account_classification=classification,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def test_parse_openai_costs_project_isolation():
    payload = {
        "object": "page",
        "data": [
            {
                "object": "bucket",
                "start_time": 1730419200,
                "end_time": 1730505600,
                "results": [
                    {
                        "object": "organization.costs.result",
                        "amount": {"value": 1.25, "currency": "usd"},
                        "line_item": "images",
                        "project_id": "proj_fr",
                    },
                    {
                        "object": "organization.costs.result",
                        "amount": {"value": 9.99, "currency": "usd"},
                        "line_item": "other",
                        "project_id": "proj_other",
                    },
                    {
                        "object": "organization.costs.result",
                        "amount": {"value": 0.5, "currency": "usd"},
                        "line_item": None,
                        "project_id": None,
                    },
                ],
            }
        ],
        "has_more": False,
        "next_page": None,
    }
    rows = parse_costs_page(payload, fashionrise_project_id="proj_fr")
    assert len(rows) == 3
    by_proj = {r["project_id"]: r for r in rows}
    assert by_proj["proj_fr"]["attribution"] == "project"
    assert by_proj["proj_fr"]["amount"] == Decimal("1.25")
    assert by_proj["proj_other"]["attribution"] == "organization_unattributed"
    assert by_proj[None]["attribution"] == "organization_unattributed"


def test_openai_sync_disabled_by_default(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_COST_SYNC_ENABLED", "false")
    monkeypatch.setenv("OPENAI_ADMIN_API_KEY", "sk-admin-test")
    from app.core.config import get_settings

    get_settings.cache_clear()
    called = {"n": 0}

    def _boom(*_a, **_k):
        called["n"] += 1
        raise AssertionError("must not call OpenAI when disabled")

    set_openai_cost_http_override(_boom)
    try:
        run = sync_openai_costs(db_session)
        assert run.status == "skipped_disabled"
        assert called["n"] == 0
    finally:
        set_openai_cost_http_override(None)
        get_settings.cache_clear()


def test_openai_sync_pagination_and_idempotent(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("OPENAI_COST_SYNC_ENABLED", "true")
    monkeypatch.setenv("OPENAI_ADMIN_API_KEY", "sk-admin-test")
    monkeypatch.setenv("OPENAI_BILLING_PROJECT_ID", "proj_fr")
    from app.core.config import get_settings

    get_settings.cache_clear()
    pages = [
        {
            "object": "page",
            "has_more": True,
            "next_page": "p2",
            "data": [
                {
                    "object": "bucket",
                    "start_time": 1730419200,
                    "end_time": 1730505600,
                    "results": [
                        {
                            "object": "organization.costs.result",
                            "amount": {"value": 2.0, "currency": "usd"},
                            "line_item": "images",
                            "project_id": "proj_fr",
                        }
                    ],
                }
            ],
        },
        {
            "object": "page",
            "has_more": False,
            "next_page": None,
            "data": [
                {
                    "object": "bucket",
                    "start_time": 1730505600,
                    "end_time": 1730592000,
                    "results": [
                        {
                            "object": "organization.costs.result",
                            "amount": {"value": 3.5, "currency": "usd"},
                            "line_item": "images",
                            "project_id": "proj_fr",
                        }
                    ],
                }
            ],
        },
    ]
    idx = {"i": 0}

    def _fake(method, url, params=None, headers=None, **_k):
        assert "Authorization" in (headers or {})
        assert "sk-admin-test" in headers["Authorization"]
        body = pages[idx["i"]]
        idx["i"] += 1
        return httpx.Response(200, json=body)

    set_openai_cost_http_override(_fake)
    try:
        run = sync_openai_costs(db_session, force=True)
        assert run.status == "success"
        assert run.rows_upserted == 2
        db_session.commit()
        # Second sync idempotent
        idx["i"] = 0
        run2 = sync_openai_costs(db_session, force=True)
        assert run2.status == "success"
        from sqlalchemy import func, select

        count = int(
            db_session.scalar(select(func.count()).select_from(OpenAiCostDaily)) or 0
        )
        assert count == 2
    finally:
        set_openai_cost_http_override(None)
        get_settings.cache_clear()


def test_fashn_credits_parse_and_sync(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    parsed = parse_credits_payload(
        {"credits": {"total": 234, "subscription": 100, "on_demand": 134}}
    )
    assert parsed["credits_total"] == 234

    monkeypatch.setenv("FASHN_CREDIT_SYNC_ENABLED", "true")
    monkeypatch.setenv("FASHN_API_KEY", "fashn-test-key")
    from app.core.config import get_settings

    get_settings.cache_clear()

    def _fake(method, url, headers=None, **_k):
        assert "fashn-test-key" in (headers or {}).get("Authorization", "")
        return httpx.Response(
            200, json={"credits": {"total": 50, "subscription": 10, "on_demand": 40}}
        )

    set_fashn_credit_http_override(_fake)
    try:
        run = sync_fashn_credits(db_session, force=True)
        assert run.status == "success"
        assert run.rows_upserted == 1
    finally:
        set_fashn_credit_http_override(None)
        get_settings.cache_clear()


def test_fashn_prediction_idempotent_and_missing_header(db_session: Session):
    user = _user(db_session, username="cust_fin")
    row = record_fashn_prediction(
        db_session,
        prediction_id="pred-1",
        feature="virtual_try_on",
        final_status="completed",
        user_id=user.id,
        credits_consumed=2,
        credits_header_present=True,
    )
    db_session.commit()
    assert row is not None
    assert row.credits_kind == CREDITS_KIND_ACTUAL
    assert row.credits_consumed == 2
    assert row.estimated_cost_usd is not None
    assert Decimal(row.estimated_cost_usd) > 0

    again = record_fashn_prediction(
        db_session,
        prediction_id="pred-1",
        feature="virtual_try_on",
        final_status="completed",
        user_id=user.id,
        credits_consumed=99,
        credits_header_present=True,
    )
    assert again is not None
    assert again.id == row.id
    assert again.credits_consumed == 2

    missing = record_fashn_prediction(
        db_session,
        prediction_id="pred-2",
        feature="fitting_room",
        final_status="completed",
        user_id=user.id,
        credits_consumed=None,
        credits_header_present=False,
    )
    db_session.commit()
    assert missing is not None
    assert missing.credits_kind == CREDITS_KIND_UNAVAILABLE
    assert missing.credits_consumed is None


def test_unlimited_wallet_costs_included(db_session: Session):
    owner = _user(db_session, username="owner_fin", classification="OWNER")
    owner.ai_stars_unlimited = True
    db_session.commit()
    record_fashn_prediction(
        db_session,
        prediction_id="pred-ul",
        feature="virtual_try_on",
        final_status="completed",
        user_id=owner.id,
        credits_consumed=4,
        credits_header_present=True,
    )
    db_session.commit()
    end = datetime.now(timezone.utc) + timedelta(days=1)
    section = build_ai_financial_section(
        db_session, start=None, end=end, audience_filter=None
    )
    assert section["fashn"]["credits_consumed_actual"]["value"] == 4


def test_income_vs_expenses_labels_and_no_double_count():
    ai = {
        "openai": {"project_costs": {"kind": "actual", "amount_usd": 10.0}},
        "fashn": {"estimated_consumption_usd": {"kind": "estimated", "amount_usd": 5.0}},
        "operator_expenses_actual_usd": {"kind": "unavailable"},
        "by_feature": [
            {"provider": "openai", "feature": "magic", "estimated_cost_usd": 8.0},
        ],
    }
    block = build_income_vs_expenses(
        revenue_gross=20.0,
        revenue_refunds=0.0,
        revenue_net=20.0,
        ai_financial=ai,
        stars_purchased_net=100,
        successful_generations=10,
        paying_customers=2,
    )
    # Actual OpenAI preferred — do not also add the 8.0 estimate into expenses.
    assert block["summary"]["openai_expenses_usd"]["amount_usd"] == 10.0
    assert block["summary"]["total_expenses_usd"]["amount_usd"] == 15.0
    assert block["summary"]["net_earnings_usd"]["amount_usd"] == 5.0
    assert block["summary"]["avg_cost_per_generation_usd"]["amount_usd"] == 1.5
    assert block["summary"]["reconciliation_openai"]["difference_usd"] == 2.0
    op = block["modes"]["operating_consumption"]
    assert op["expenses"]["total_operating_usd"]["amount_usd"] == 15.0
    cash = block["modes"]["documented_cash"]
    assert "fashn_estimated_consumption_usd" not in cash["expenses"]


def test_admin_overview_includes_ai_financial(client: TestClient, db_session: Session):
    admin = _user(db_session, username="shilatperi", is_admin=True, classification="OWNER")
    r = client.get(
        "/api/v1/admin/overview",
        params={"audience": "all", "range": "last_30d"},
        headers=_auth(admin),
    )
    assert r.status_code == 200
    body = r.json()
    assert "ai_financial" in body
    assert "income_vs_expenses" in body
    assert body["ai_financial"]["sync"]["openai_cost_sync_enabled"] is False
    assert body["ai_financial"]["sync"]["fashn_credit_sync_enabled"] is False
    assert body["charts"]["ai_cost_trend"]["kind"] in ("unavailable", "actual")


def test_admin_overview_rejects_unauth(client: TestClient):
    r = client.get("/api/v1/admin/overview")
    assert r.status_code in (401, 403)


def test_secret_redaction_in_sync_error(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_COST_SYNC_ENABLED", "true")
    monkeypatch.setenv("OPENAI_ADMIN_API_KEY", "sk-secret-should-not-leak")
    from app.core.config import get_settings

    get_settings.cache_clear()

    def _fake(*_a, **_k):
        return httpx.Response(401, text="unauthorized sk-secret-should-not-leak")

    set_openai_cost_http_override(_fake)
    try:
        run = sync_openai_costs(db_session, force=True)
        assert run.status == "failed"
        assert "sk-secret-should-not-leak" not in (run.error_detail or "")
        assert "[REDACTED]" in (run.error_detail or "") or "401" in (run.error_detail or "")
    finally:
        set_openai_cost_http_override(None)
        get_settings.cache_clear()


def test_operator_expense_not_mixed_as_fashn_cash(db_session: Session):
    db_session.add(
        OperatorExpenseRecord(
            id=uuid.uuid4(),
            category="hosting",
            currency="usd",
            amount=Decimal("40.00"),
            kind="actual",
            occurred_on=date.today(),
            note="vps",
        )
    )
    db_session.commit()
    end = datetime.now(timezone.utc) + timedelta(days=1)
    section = build_ai_financial_section(
        db_session, start=None, end=end, audience_filter=None
    )
    assert section["fashn"]["actual_cash_expenditure"]["kind"] == "unavailable"
    assert section["operator_expenses_actual_usd"]["kind"] == "actual"
    assert section["operator_expenses_actual_usd"]["amount_usd"] == 40.0
