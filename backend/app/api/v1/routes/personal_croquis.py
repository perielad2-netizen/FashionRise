"""Create My Croquis authenticated routes (Stage A storage + Stage C generate).

Gates default OFF. Generate requires MY_CROQUIS_AI_ENABLED + spend ceiling > 0.
Ownership enforced on all reads. No paid provider calls under default config.
"""

import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.schemas.personal_croquis import (
    AdultsAttestationRead,
    AdultsAttestationRequest,
    AiConsentAcknowledgeRequest,
    ConsentAcknowledgeRequest,
    ConsentEventRead,
    GenerateVersionRequest,
    PersonalCroquisRead,
    PersonalCroquisVersionRead,
    consent_to_read,
    croquis_to_read,
    version_to_read,
)
from app.services import personal_croquis_generate as pcg
from app.services import personal_croquis_service as pcs

router = APIRouter()


@router.post("/attestations/adults", response_model=AdultsAttestationRead)
@limiter.limit("30/minute")
def attest_adults(
    request: Request,
    body: AdultsAttestationRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> AdultsAttestationRead:
    """Record adults-only beta self-attestation (not independent age verification)."""
    _ = request.url
    row = pcs.record_adults_attestation(
        db,
        user,
        adults_attested=body.adults_attested,
        notice_version=body.notice_version,
        notice_text_hash=body.notice_text_hash,
    )
    return AdultsAttestationRead(
        id=row.id,
        purpose=row.purpose,
        consent_version=row.consent_version,
        adults_attested=row.adults_attested,
        created_at=row.created_at,
    )


@router.post("/consent/storage", response_model=ConsentEventRead)
@limiter.limit("30/minute")
def consent_storage(
    request: Request,
    body: ConsentAcknowledgeRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> ConsentEventRead:
    _ = request.url
    row = pcs.record_storage_consent(
        db,
        user,
        acknowledged=body.acknowledged,
        adults_attested=body.adults_attested,
        notice_version=body.notice_version,
        notice_text_hash=body.notice_text_hash,
    )
    return consent_to_read(row)


@router.post("/consent/ai", response_model=ConsentEventRead)
@limiter.limit("30/minute")
def consent_ai(
    request: Request,
    body: AiConsentAcknowledgeRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> ConsentEventRead:
    """AI-provider consent bound to an exact croquis source (no provider call)."""
    _ = request.url
    row = pcs.record_ai_consent(
        db,
        user,
        acknowledged=body.acknowledged,
        adults_attested=body.adults_attested,
        notice_version=body.notice_version,
        notice_text_hash=body.notice_text_hash,
        croquis_id=body.croquis_id,
    )
    return consent_to_read(row)


@router.post("/photos", response_model=PersonalCroquisRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
def upload_photo(
    request: Request,
    user: CurrentUser,
    file: UploadFile = File(...),
    storage_consent_id: uuid.UUID = Form(...),
    display_name: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> PersonalCroquisRead:
    """Gated source-photo upload. Requires storage consent + MY_CROQUIS_UPLOAD_ENABLED."""
    _ = request.url
    settings = get_settings()
    # Never trust client filename as identity or prompt content.
    _ = file.filename
    raw = pcs.read_croquis_upload_bytes(file.file, settings.max_croquis_upload_bytes)
    croquis = pcs.upload_source_photo(
        db,
        user,
        raw=raw,
        declared_content_type=file.content_type,
        storage_consent_id=storage_consent_id,
        display_name=display_name,
    )
    latest = pcs.latest_accepted_version(db, user, croquis.id)
    open_version = pcs.latest_open_version(db, user, croquis.id)
    return croquis_to_read(croquis, latest=latest, open_version=open_version)


@router.get("", response_model=list[PersonalCroquisRead])
@limiter.limit("120/minute")
def list_croquis(
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> list[PersonalCroquisRead]:
    _ = request.url
    rows = pcs.list_personal_croquis(db, user)
    out: list[PersonalCroquisRead] = []
    for row in rows:
        latest = pcs.latest_accepted_version(db, user, row.id)
        open_version = pcs.latest_open_version(db, user, row.id)
        out.append(croquis_to_read(row, latest=latest, open_version=open_version))
    return out


@router.get("/assets/{asset_id}/image")
@limiter.limit("240/minute")
def get_asset_image(
    request: Request,
    asset_id: uuid.UUID,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> FileResponse:
    """Owner-only private bytes. Never under /static/uploads. Cache-Control: private, no-store."""
    _ = request.url
    path = pcs.resolve_croquis_asset_file(db, user, asset_id)
    return FileResponse(
        path,
        media_type="image/png",
        filename=f"fashionrise-croquis-{asset_id.hex[:12]}.png",
        content_disposition_type="inline",
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/{croquis_id}", response_model=PersonalCroquisRead)
@limiter.limit("120/minute")
def get_croquis(
    request: Request,
    croquis_id: uuid.UUID,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> PersonalCroquisRead:
    _ = request.url
    row = pcs.get_owned_croquis(db, user, croquis_id, include_archived=True)
    latest = pcs.latest_accepted_version(db, user, row.id)
    open_version = pcs.latest_open_version(db, user, row.id)
    return croquis_to_read(row, latest=latest, open_version=open_version)


@router.post(
    "/{croquis_id}/versions/generate",
    response_model=PersonalCroquisVersionRead,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("10/minute")
def generate_croquis_version(
    request: Request,
    croquis_id: uuid.UUID,
    body: GenerateVersionRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> PersonalCroquisVersionRead:
    """Stage C enqueue — AI consent + AI gate + spend reservation + idempotency.

    Returns a generating version. Worker settles to awaiting_review.
    Defaults fail closed. Live paid providers are not activated in this build.
    """
    _ = request.url
    row = pcg.enqueue_personal_croquis_generate(
        db,
        user,
        croquis_id,
        ai_consent_id=body.ai_consent_id,
        idempotency_key=body.idempotency_key,
    )
    code, msg = pcg.enrich_version_failure_fields(db, row)
    return version_to_read(row, failure_code=code, failure_message=msg)


@router.get("/{croquis_id}/versions/{version}", response_model=PersonalCroquisVersionRead)
@limiter.limit("120/minute")
def get_croquis_version(
    request: Request,
    croquis_id: uuid.UUID,
    version: int,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> PersonalCroquisVersionRead:
    """Durable progress/status for a version (generating → awaiting_review → accepted)."""
    _ = request.url
    row = pcs.get_exact_version(db, user, croquis_id, version)
    code, msg = pcg.enrich_version_failure_fields(db, row)
    return version_to_read(row, failure_code=code, failure_message=msg)


@router.post(
    "/{croquis_id}/versions/{version}/accept",
    response_model=PersonalCroquisVersionRead,
)
@limiter.limit("30/minute")
def accept_croquis_version(
    request: Request,
    croquis_id: uuid.UUID,
    version: int,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> PersonalCroquisVersionRead:
    _ = request.url
    row = pcg.accept_personal_croquis_version(db, user, croquis_id, version)
    code, msg = pcg.enrich_version_failure_fields(db, row)
    return version_to_read(row, failure_code=code, failure_message=msg)


@router.post(
    "/{croquis_id}/versions/{version}/reject",
    response_model=PersonalCroquisVersionRead,
)
@limiter.limit("30/minute")
def reject_croquis_version(
    request: Request,
    croquis_id: uuid.UUID,
    version: int,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> PersonalCroquisVersionRead:
    _ = request.url
    row = pcg.reject_personal_croquis_version(db, user, croquis_id, version)
    code, msg = pcg.enrich_version_failure_fields(db, row)
    return version_to_read(row, failure_code=code, failure_message=msg)


@router.post("/{croquis_id}/archive", response_model=PersonalCroquisRead)
@limiter.limit("60/minute")
def archive_croquis(
    request: Request,
    croquis_id: uuid.UUID,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> PersonalCroquisRead:
    _ = request.url
    row = pcs.archive_croquis(db, user, croquis_id)
    latest = pcs.latest_accepted_version(db, user, row.id)
    open_version = pcs.latest_open_version(db, user, row.id)
    return croquis_to_read(row, latest=latest, open_version=open_version)


@router.delete("/{croquis_id}", response_model=PersonalCroquisRead)
@limiter.limit("60/minute")
def erase_croquis(
    request: Request,
    croquis_id: uuid.UUID,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> PersonalCroquisRead:
    """Permanent erase request — bytes become unavailable; pins are not remapped."""
    _ = request.url
    row = pcs.request_permanent_erase(db, user, croquis_id)
    return croquis_to_read(row, latest=None)
