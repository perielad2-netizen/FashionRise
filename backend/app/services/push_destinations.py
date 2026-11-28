"""Canonical push notification destination contract (BE).

Stable GalleryItem / comment / friendship UUIDs only — never MagicLook IDs,
titles, timestamps, or feed ranks. Shared allowlist semantics must stay in
lockstep with:

- ``web-ui/src/services/native/pushDestination.ts``
- ``web-ui/public/push-sw-handlers.js``

Paths
-----
- ``/studio/fashionrise`` — FashionRise Social (immersive feed)
- ``/studio/runway`` — rankings board (legacy / operator; no item query)
- ``/privacy`` — privacy policy

FashionRise query keys (typed)
------------------------------
- ``item=<uuid>`` — public GalleryItem id
- ``comments=1`` — open comments panel (requires ``item``)
- ``comment=<uuid>`` — focus comment (requires ``item``; implies comments)
- ``friends=1`` — Manage friends
- ``section=requests|accepted`` — friends subsection (requires ``friends=1``)
- ``friendship=<uuid>`` — highlight relationship (requires ``friends=1``)

Fallback for unsafe input: ``/studio/fashionrise``.
"""

from __future__ import annotations

import re
import uuid
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlparse

_FALLBACK = "/studio/fashionrise"
_ALLOWED_PATH_PREFIXES = ("/studio", "/privacy")
_BLOCKED_PATH_PREFIXES = (
    "/reset-password",
    "/verify-email",
    "/forgot-password",
    "/auth/google",
    "/auth/cf-access",
    "/api/",
)
_TOKENISH = re.compile(
    r"(?:^|[?#&])(?:token|code|access_token|refresh_token|id_token|handoff)=",
    re.I,
)
_ALLOWED_HOSTS = frozenset({"fashionrise.app", "www.fashionrise.app"})
_FRIENDS_SECTIONS = frozenset({"requests", "accepted"})
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.I,
)


def _is_uuid(value: str) -> bool:
    return bool(_UUID_RE.match((value or "").strip()))


def _path_allowed(path: str) -> bool:
    if any(path == p or path.startswith(p) for p in _BLOCKED_PATH_PREFIXES):
        return False
    if path == "/":
        return False
    return any(path == p or path.startswith(f"{p}/") for p in _ALLOWED_PATH_PREFIXES)


def build_social_item_url(gallery_item_id: uuid.UUID | str) -> str:
    return f"/studio/fashionrise?item={uuid.UUID(str(gallery_item_id))}"


def build_social_comment_url(
    gallery_item_id: uuid.UUID | str, comment_id: uuid.UUID | str
) -> str:
    item = uuid.UUID(str(gallery_item_id))
    comment = uuid.UUID(str(comment_id))
    return f"/studio/fashionrise?item={item}&comments=1&comment={comment}"


def build_friend_request_url(friendship_id: uuid.UUID | str) -> str:
    fid = uuid.UUID(str(friendship_id))
    return f"/studio/fashionrise?friends=1&section=requests&friendship={fid}"


def build_friend_accepted_url(friendship_id: uuid.UUID | str) -> str:
    fid = uuid.UUID(str(friendship_id))
    return f"/studio/fashionrise?friends=1&section=accepted&friendship={fid}"


FriendsSection = Literal["requests", "accepted"]


def _sanitize_fashionrise_query(pairs: list[tuple[str, str]]) -> str | None:
    """Return a canonical query string or None if invalid/empty."""
    if not pairs:
        return ""
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        return None

    values = {k: v for k, v in pairs}
    allowed = {"item", "comments", "comment", "friends", "section", "friendship"}
    if any(k not in allowed for k in values):
        return None

    has_item = "item" in values
    has_friends = "friends" in values
    if has_item and has_friends:
        return None
    if not has_item and not has_friends:
        return None

    out: list[tuple[str, str]] = []

    if has_item:
        item = values["item"].strip()
        if not _is_uuid(item):
            return None
        out.append(("item", str(uuid.UUID(item))))
        comments = values.get("comments")
        comment = values.get("comment")
        if comment is not None:
            c = comment.strip()
            if not _is_uuid(c):
                return None
            out.append(("comments", "1"))
            out.append(("comment", str(uuid.UUID(c))))
        elif comments is not None:
            if comments.strip() != "1":
                return None
            out.append(("comments", "1"))
        if "section" in values or "friendship" in values:
            return None
        return urlencode(out)

    # friends mode
    if values.get("friends", "").strip() != "1":
        return None
    out.append(("friends", "1"))
    section = values.get("section")
    friendship = values.get("friendship")
    if section is not None:
        s = section.strip().lower()
        if s not in _FRIENDS_SECTIONS:
            return None
        out.append(("section", s))
    if friendship is not None:
        f = friendship.strip()
        if not _is_uuid(f):
            return None
        out.append(("friendship", str(uuid.UUID(f))))
    if "item" in values or "comments" in values or "comment" in values:
        return None
    return urlencode(out)


def sanitize_push_url(url: str | None, *, fallback: str | None = None) -> str:
    """Allow only non-credential Studio/privacy paths with typed query params."""
    fb = fallback or _FALLBACK
    raw = (url or "").strip() or fb

    if "://" in raw or raw.startswith("//"):
        try:
            parsed = urlparse(raw if "://" in raw else f"https:{raw}")
        except Exception:  # noqa: BLE001
            return fb
        host = (parsed.hostname or "").lower()
        if host not in _ALLOWED_HOSTS:
            return fb
        raw = f"{parsed.path or '/'}{('?' + parsed.query) if parsed.query else ''}"

    if not raw.startswith("/") or raw.startswith("//"):
        return fb
    if _TOKENISH.search(raw):
        return fb

    path = raw.split("?", 1)[0].split("#", 1)[0] or "/"
    query_raw = ""
    if "?" in raw:
        query_raw = raw.split("?", 1)[1].split("#", 1)[0]

    if not _path_allowed(path):
        return fb

    if not query_raw:
        return path

    try:
        pairs = parse_qsl(query_raw, keep_blank_values=True)
    except Exception:  # noqa: BLE001
        return path

    if path == "/studio/fashionrise":
        safe_q = _sanitize_fashionrise_query(pairs)
        if safe_q is None:
            return path
        return f"{path}?{safe_q}" if safe_q else path

    # Other studio/privacy paths: strip all query (no free-form params).
    return path
