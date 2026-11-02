import uuid

from fastapi import APIRouter, Body, Depends, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.schemas.ai import (
    AcceptedGarmentRealismJobRead,
    AIJobCreate,
    AIJobRead,
    MagicOperationJobsRead,
    PersonalGarmentRealismBody,
    PersonalTryOnBody,
    PersonalTryOnFashnPrepareBody,
    PersonalTryOnFashnPrepareRead,
    PersonalTryOnPreflightRead,
    SketchPipelineBody,
    SketchPolishDualBody,
    SketchPolishDualRead,
    TryOnExperimentVerdictBody,
)
from app.services import ai_service
from app.services import personal_try_on as try_on_service

router = APIRouter()


def _sketch_enqueue(
    db: Session, user, job_type: str, body: SketchPipelineBody | None
) -> AIJobRead:
    b = body if body is not None else SketchPipelineBody()
    job = ai_service.enqueue_job(
        db,
        user,
        AIJobCreate(design_id=b.design_id, job_type=job_type, input_data=b.input_data),
    )
    return AIJobRead.from_job(job)


@router.post("/sketch/clean", response_model=AIJobRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("40/minute")
def sketch_clean(
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
    body: SketchPipelineBody | None = Body(None),
) -> AIJobRead:
    _ = request.url
    return _sketch_enqueue(db, user, "sketch_clean", body)


@router.post("/sketch/polish", response_model=AIJobRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("40/minute")
def sketch_polish(
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
    body: SketchPipelineBody | None = Body(None),
) -> AIJobRead:
    _ = request.url
    return _sketch_enqueue(db, user, "sketch_polish", body)


@router.post(
    "/sketch/polish-dual",
    response_model=SketchPolishDualRead,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("20/minute")
def sketch_polish_dual(
    request: Request,
    user: CurrentUser,
    body: SketchPolishDualBody,
    db: Session = Depends(get_db),
) -> SketchPolishDualRead:
    _ = request.url
    front_job, back_job, operation_id = ai_service.enqueue_dual_sketch_polish(db, user, body)
    return SketchPolishDualRead(
        magic_operation_id=operation_id,
        front_job=AIJobRead.from_job(front_job),
        back_job=AIJobRead.from_job(back_job),
    )


@router.get(
    "/magic-operations/{operation_id}/jobs",
    response_model=MagicOperationJobsRead,
)
@limiter.limit("120/minute")
def list_magic_operation_jobs(
    request: Request,
    operation_id: uuid.UUID,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> MagicOperationJobsRead:
    """Recover front/back sketch_polish jobs for one coordinated Magic operation."""
    _ = request.url
    jobs = ai_service.list_jobs_for_magic_operation(db, user, operation_id)
    return MagicOperationJobsRead(
        magic_operation_id=operation_id,
        jobs=[AIJobRead.from_job(j) for j in jobs],
    )


@router.post("/style/suggest", response_model=AIJobRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("40/minute")
def style_suggest(
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
    body: SketchPipelineBody | None = Body(None),
) -> AIJobRead:
    _ = request.url
    return _sketch_enqueue(db, user, "style_suggest", body)


@router.get("/personal-try-on/preflight", response_model=PersonalTryOnPreflightRead)
@limiter.limit("60/minute")
def personal_try_on_preflight(request: Request, user: CurrentUser) -> PersonalTryOnPreflightRead:
    """Consent notice + budget envelope for Try On Person (no billable work)."""
    _ = request.url
    return PersonalTryOnPreflightRead(**try_on_service.try_on_preflight_public(user=user))


@router.post(
    "/personal-try-on/fashn/prepare",
    response_model=PersonalTryOnFashnPrepareRead,
)
@limiter.limit("30/minute")
def personal_try_on_fashn_prepare(
    request: Request,
    user: CurrentUser,
    body: PersonalTryOnFashnPrepareBody,
) -> PersonalTryOnFashnPrepareRead:
    """Offline FASHN garment flat-lay prep preview — no paid provider call."""
    _ = request.url
    _ = user
    return PersonalTryOnFashnPrepareRead(
        **try_on_service.prepare_fashn_garment_public(body.garment_image_base64)
    )


@router.post(
    "/personal-try-on/fashn/garment-realism",
    response_model=AIJobRead,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("20/minute")
def personal_try_on_garment_realism(
    request: Request,
    user: CurrentUser,
    body: PersonalGarmentRealismBody,
    db: Session = Depends(get_db),
) -> AIJobRead:
    """Enqueue OpenAI realistic garment product images (owner review before FASHN)."""
    _ = request.url
    job = try_on_service.enqueue_garment_realism(
        db,
        user,
        croquis_id=body.croquis_id,
        croquis_version=body.croquis_version,
        garment_image_base64=body.garment_image_base64,
        plate_pieces=[p.model_dump() for p in body.plate_pieces],
        garment_fingerprint=body.garment_fingerprint,
        idempotency_key=body.idempotency_key,
        design_id=body.design_id,
        consent_acknowledged=body.consent_acknowledged,
        consent_version=body.consent_version,
    )
    return AIJobRead.from_job(job)


@router.post(
    "/personal-try-on/fashn/garment-realism/{job_id}/accept",
    response_model=AIJobRead,
)
@limiter.limit("30/minute")
def personal_try_on_garment_realism_accept(
    request: Request,
    job_id: uuid.UUID,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> AIJobRead:
    """Owner accepts OpenAI product images — required before FASHN credits (#169)."""
    _ = request.url
    job = try_on_service.accept_garment_realism_job(db, user, job_id)
    return AIJobRead.from_job(job)


@router.get(
    "/personal-try-on/fashn/garment-realism/accepted",
    response_model=list[AcceptedGarmentRealismJobRead],
)
@limiter.limit("60/minute")
def personal_try_on_list_accepted_realism(
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> list[AcceptedGarmentRealismJobRead]:
    """Owner catalog of accepted realistic garments for reuse without OpenAI regen (#176)."""
    _ = request.url
    rows = try_on_service.list_accepted_garment_realism_jobs(db, user)
    return [AcceptedGarmentRealismJobRead(**row) for row in rows]


@router.post(
    "/personal-try-on/{job_id}/experiment-verdict",
    response_model=AIJobRead,
)
@limiter.limit("60/minute")
def personal_try_on_experiment_verdict(
    request: Request,
    job_id: uuid.UUID,
    user: CurrentUser,
    body: TryOnExperimentVerdictBody,
    db: Session = Depends(get_db),
) -> AIJobRead:
    """Owner Accepted / Rejected / Unreviewed mark for FASHN comparison results (#176)."""
    _ = request.url
    job = try_on_service.set_try_on_experiment_verdict(
        db, user, job_id, verdict=body.verdict
    )
    return AIJobRead.from_job(job)


@router.post(
    "/personal-try-on",
    response_model=AIJobRead,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("20/minute")
def personal_try_on(
    request: Request,
    user: CurrentUser,
    body: PersonalTryOnBody,
    db: Session = Depends(get_db),
) -> AIJobRead:
    """Enqueue photorealistic Try On Person using the owner's original croquis photo."""
    _ = request.url
    job = try_on_service.enqueue_personal_try_on(
        db,
        user,
        croquis_id=body.croquis_id,
        croquis_version=body.croquis_version,
        garment_image_base64=body.garment_image_base64,
        idempotency_key=body.idempotency_key,
        design_id=body.design_id,
        source_revision=body.source_revision,
        content_fingerprint=body.content_fingerprint,
        consent_acknowledged=body.consent_acknowledged,
        consent_version=body.consent_version,
        design_hints=body.design_hints,
        provider=body.provider,
        approved_garment_pieces=(
            [p.model_dump() for p in body.approved_garment_pieces]
            if body.approved_garment_pieces
            else None
        ),
        garment_realism_job_id=body.garment_realism_job_id,
        fashn_max_generation_mode=body.fashn_max_generation_mode,
        fashn_max_resolution=body.fashn_max_resolution,
        fashn_max_prompt=body.fashn_max_prompt,
        fashn_max_seed=body.fashn_max_seed,
        fashn_v16_category=body.fashn_v16_category,
        fashn_v16_segmentation_free=body.fashn_v16_segmentation_free,
        fashn_v16_mode=body.fashn_v16_mode,
        fashn_v16_seed=body.fashn_v16_seed,
        smart_fallback=bool(body.smart_fallback),
        smart_operation_id=body.smart_operation_id,
        smart_fallback_reason=body.smart_fallback_reason,
    )
    return AIJobRead.from_job(job)


@router.post("/jobs", response_model=AIJobRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("40/minute")
def create_job(
    request: Request, data: AIJobCreate, user: CurrentUser, db: Session = Depends(get_db)
) -> AIJobRead:
    _ = request.url
    job = ai_service.enqueue_job(db, user, data)
    return AIJobRead.from_job(job)


@router.get("/jobs/{job_id}", response_model=AIJobRead)
@limiter.limit("400/minute")
def get_job(
    request: Request, job_id: uuid.UUID, user: CurrentUser, db: Session = Depends(get_db)
) -> AIJobRead:
    _ = request.url
    job = ai_service.get_job(db, user, job_id)
    return AIJobRead.from_job(job)


@router.get("/jobs/{job_id}/image")
@limiter.limit("120/minute")
def get_job_image(
    request: Request, job_id: uuid.UUID, user: CurrentUser, db: Session = Depends(get_db)
) -> FileResponse:
    """Serve a completed look image only to the owning authenticated user.

    Prefer this over public `/static/uploads` so production Nginx can keep
    static uploads denied while Magic still retrieves private results.
    """
    _ = request.url
    path = ai_service.resolve_job_image_file(db, user, job_id)
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
        filename=f"fashionrise-look-{job_id.hex[:12]}{suffix or '.png'}",
        content_disposition_type="inline",
        headers={"Cache-Control": "private, no-store"},
    )
