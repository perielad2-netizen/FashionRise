import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AdultsAttestationRequest(BaseModel):
    """Explicit adults-only self-attestation (NOT independent age verification)."""

    adults_attested: Literal[True] = Field(
        description="Must be explicitly true; empty/omitted requests are rejected.",
    )
    notice_version: str = Field(min_length=1, max_length=64)
    notice_text_hash: str = Field(
        min_length=64,
        max_length=64,
        description="SHA-256 hex of the approved notice text shown to the user.",
    )


class ConsentAcknowledgeRequest(BaseModel):
    """Explicit storage or AI-provider consent acknowledgment."""

    acknowledged: Literal[True] = Field(
        description="Must be explicitly true; empty/omitted requests are rejected.",
    )
    adults_attested: Literal[True] = Field(
        description="Must reaffirm adults-only attestation on this consent record.",
    )
    notice_version: str = Field(min_length=1, max_length=64)
    notice_text_hash: str = Field(min_length=64, max_length=64)


class AdultsAttestationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    purpose: str
    consent_version: str
    adults_attested: bool
    created_at: datetime


class ConsentEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    purpose: str
    consent_version: str
    adults_attested: bool
    created_at: datetime


class PersonalCroquisVersionSummary(BaseModel):
    version: int
    status: str
    generated_asset_id: uuid.UUID | None = None
    geometry_profile: str | None = None
    accepted_at: datetime | None = None


class PersonalCroquisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    status: str
    source_asset_id: uuid.UUID | None = None
    storage_consent_id: uuid.UUID | None = None
    adults_attestation_at: datetime | None = None
    archived: bool = False
    erased: bool = False
    created_at: datetime
    updated_at: datetime
    latest_accepted_version: PersonalCroquisVersionSummary | None = None


class PersonalCroquisVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    croquis_id: uuid.UUID
    version: int
    status: str
    generated_asset_id: uuid.UUID | None = None
    geometry_profile: str | None = None
    prompt_version: str | None = None
    created_at: datetime
    accepted_at: datetime | None = None


def consent_to_read(row) -> ConsentEventRead:
    return ConsentEventRead(
        id=row.id,
        purpose=row.purpose,
        consent_version=row.consent_version,
        adults_attested=row.adults_attested,
        created_at=row.created_at,
    )


def croquis_to_read(row, *, latest=None) -> PersonalCroquisRead:
    latest_summary = None
    if latest is not None:
        latest_summary = PersonalCroquisVersionSummary(
            version=latest.version,
            status=latest.status,
            generated_asset_id=latest.generated_asset_id,
            geometry_profile=latest.geometry_profile,
            accepted_at=latest.accepted_at,
        )
    return PersonalCroquisRead(
        id=row.id,
        display_name=row.display_name,
        status=row.status,
        source_asset_id=row.source_asset_id,
        storage_consent_id=row.storage_consent_id,
        adults_attestation_at=row.adults_attestation_at,
        archived=row.archived_at is not None,
        erased=row.erase_requested_at is not None or row.deleted_at is not None,
        created_at=row.created_at,
        updated_at=row.updated_at,
        latest_accepted_version=latest_summary,
    )


def version_to_read(row) -> PersonalCroquisVersionRead:
    return PersonalCroquisVersionRead(
        id=row.id,
        croquis_id=row.croquis_id,
        version=row.version,
        status=row.status,
        generated_asset_id=row.generated_asset_id,
        geometry_profile=row.geometry_profile,
        prompt_version=row.prompt_version,
        created_at=row.created_at,
        accepted_at=row.accepted_at,
    )


class PhotoUploadFormNote(BaseModel):
    """Documentation-only schema — multipart uses Form fields."""

    storage_consent_id: uuid.UUID = Field(description="Valid croquis_storage consent id")
    display_name: str | None = None
