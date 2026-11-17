"""Token-gated HTML endpoints for FashionRise Social report decisions (email links)."""

import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.services import content_report_moderation as mod

router = APIRouter()


def _handle(exc: Exception) -> HTMLResponse:
    if isinstance(exc, AppError):
        return mod.render_error(exc.message, status_code=exc.status_code)
    return mod.render_error("Something went wrong with this moderation link.", status_code=500)


@router.get("/reports/{report_id}/view", response_class=HTMLResponse)
@limiter.limit("60/minute")
def view_reported_look(
    request: Request,
    report_id: uuid.UUID,
    t: str = Query(..., min_length=20),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    _ = request.url
    try:
        data = mod.parse_moderation_token(t, expected_action="view")
        report = mod.get_report_for_moderation(db, report_id)
        mod.assert_token_matches_report(data, report)
        item = mod.get_gallery_item_for_moderation(db, report.gallery_item_id)
        return mod.render_view_page(db, report=report, item=item)
    except Exception as exc:  # noqa: BLE001 — HTML error page for email clicks
        return _handle(exc)


@router.get("/reports/{report_id}/image")
@limiter.limit("120/minute")
def reported_look_image(
    request: Request,
    report_id: uuid.UUID,
    t: str = Query(..., min_length=20),
    db: Session = Depends(get_db),
):
    _ = request.url
    try:
        data = mod.parse_moderation_token(t, expected_action="image")
        report = mod.get_report_for_moderation(db, report_id)
        mod.assert_token_matches_report(data, report)
        item = mod.get_gallery_item_for_moderation(db, report.gallery_item_id)
        path = mod.resolve_moderation_image_path(db, item)
        suffix = path.suffix.lower()
        media = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(suffix, "application/octet-stream")
        return FileResponse(
            path,
            media_type=media,
            filename=f"fashionrise-report-{report_id.hex[:12]}{suffix or '.png'}",
            content_disposition_type="inline",
            headers={"Cache-Control": "private, max-age=120"},
        )
    except AppError as exc:
        return mod.render_error(exc.message, status_code=exc.status_code)
    except Exception:  # noqa: BLE001
        return mod.render_error("Look image not available.", status_code=404)


@router.get("/reports/{report_id}/keep", response_class=HTMLResponse)
@limiter.limit("30/minute")
def keep_reported_look(
    request: Request,
    report_id: uuid.UUID,
    t: str = Query(..., min_length=20),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    _ = request.url
    try:
        data = mod.parse_moderation_token(t, expected_action="keep")
        report = mod.get_report_for_moderation(db, report_id)
        mod.assert_token_matches_report(data, report)
        report = mod.keep_reported_look(db, report)
        item = mod.get_gallery_item_for_moderation(db, report.gallery_item_id)
        return mod.render_keep_result(report, item)
    except Exception as exc:  # noqa: BLE001
        return _handle(exc)


@router.get("/reports/{report_id}/discard", response_class=HTMLResponse)
@limiter.limit("30/minute")
def discard_reported_look(
    request: Request,
    report_id: uuid.UUID,
    t: str = Query(..., min_length=20),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    _ = request.url
    try:
        data = mod.parse_moderation_token(t, expected_action="discard")
        report = mod.get_report_for_moderation(db, report_id)
        mod.assert_token_matches_report(data, report)
        report = mod.discard_reported_look(db, report)
        item = mod.get_gallery_item_for_moderation(db, report.gallery_item_id)
        return mod.render_discard_result(report, item)
    except Exception as exc:  # noqa: BLE001
        return _handle(exc)
