"""Canonical push destination contract — keep parity with FE/SW sanitizers."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from app.services import push_destinations as dest
from app.services import push_service


ITEM = uuid.UUID("11111111-1111-4111-8111-111111111111")
COMMENT = uuid.UUID("22222222-2222-4222-8222-222222222222")
FRIENDSHIP = uuid.UUID("33333333-3333-4333-8333-333333333333")

_FIXTURES = Path(__file__).parent / "fixtures" / "push_destination_contract_cases.json"


def test_builders_and_sanitize_roundtrip():
    item_url = dest.build_social_item_url(ITEM)
    assert item_url == f"/studio/fashionrise?item={ITEM}"
    assert dest.sanitize_push_url(item_url) == item_url

    comment_url = dest.build_social_comment_url(ITEM, COMMENT)
    assert "comments=1" in comment_url
    assert dest.sanitize_push_url(comment_url) == comment_url

    req = dest.build_friend_request_url(FRIENDSHIP)
    assert dest.sanitize_push_url(req) == req
    acc = dest.build_friend_accepted_url(FRIENDSHIP)
    assert dest.sanitize_push_url(acc) == acc


def test_shared_contract_fixtures():
    cases = json.loads(_FIXTURES.read_text())
    for row in cases:
        assert dest.sanitize_push_url(row["input"]) == row["expected"], row["id"]


def test_sanitize_rejects_unsafe_and_preserves_legacy_paths():
    assert dest.sanitize_push_url("/studio/runway") == "/studio/runway"
    assert dest.sanitize_push_url("/studio/fashionrise?friends=1") == "/studio/fashionrise?friends=1"
    assert dest.sanitize_push_url("/reset-password#token=abc") == "/studio/fashionrise"
    assert dest.sanitize_push_url("/studio/fashionrise?item=not-a-uuid") == "/studio/fashionrise"
    assert (
        dest.sanitize_push_url(f"/studio/fashionrise?item={ITEM}&friends=1")
        == "/studio/fashionrise"
    )
    assert (
        dest.sanitize_push_url(f"/studio/runway?item={ITEM}") == "/studio/runway"
    )
    assert dest.sanitize_push_url("https://evil.example/studio/fashionrise") == "/studio/fashionrise"
    assert (
        dest.sanitize_push_url(f"https://www.fashionrise.app/studio/fashionrise?item={ITEM}")
        == f"/studio/fashionrise?item={ITEM}"
    )
    # Hostname must be parsed — not string-prefix matching alone.
    assert (
        dest.sanitize_push_url("https://fashionrise.app.evil.example/studio/fashionrise")
        == "/studio/fashionrise"
    )


def test_push_service_reexports_sanitize():
    assert push_service.sanitize_push_url("/studio/fashionrise?friends=1") == (
        "/studio/fashionrise?friends=1"
    )


def test_native_url_for_contract_v1_preserves_friends_falls_back_item():
    friends = f"/studio/fashionrise?friends=1&section=requests&friendship={FRIENDSHIP}"
    assert push_service.native_url_for_contract(friends, contract_version=1) == friends
    assert push_service.native_url_for_contract(
        "/studio/fashionrise?friends=1", contract_version=1
    ) == "/studio/fashionrise?friends=1"

    item = f"/studio/fashionrise?item={ITEM}"
    assert push_service.native_url_for_contract(item, contract_version=1) == (
        "/studio/fashionrise"
    )
    comment = f"/studio/fashionrise?item={ITEM}&comments=1&comment={COMMENT}"
    assert push_service.native_url_for_contract(comment, contract_version=1) == (
        "/studio/fashionrise"
    )
    assert push_service.native_url_for_contract("/studio/runway", contract_version=1) == (
        "/studio/runway"
    )
    assert push_service.native_url_for_contract("/privacy", contract_version=1) == "/privacy"


def test_native_url_for_contract_v2_keeps_full_destination():
    item = f"/studio/fashionrise?item={ITEM}"
    comment = f"/studio/fashionrise?item={ITEM}&comments=1&comment={COMMENT}"
    friends = f"/studio/fashionrise?friends=1&section=accepted&friendship={FRIENDSHIP}"
    assert push_service.native_url_for_contract(item, contract_version=2) == item
    assert push_service.native_url_for_contract(comment, contract_version=2) == comment
    assert push_service.native_url_for_contract(friends, contract_version=2) == friends
