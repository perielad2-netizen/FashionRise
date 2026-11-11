from app.models.ai_job import AIJob
from app.models.body_measurement_profile import BodyMeasurementProfile
from app.models.color_palette import ColorPalette
from app.models.design_export import DesignExport
from app.models.design_revision import DesignRevision
from app.models.fabric_asset import FabricAsset
from app.models.gallery_comment import GalleryComment
from app.models.gallery_comment_like import GalleryCommentLike
from app.models.gallery_item import GalleryItem
from app.models.gallery_like import GalleryLike
from app.models.garment_design import GarmentDesign
from app.models.garment_template import GarmentTemplate
from app.models.magic_look_meta import MagicLookMeta
from app.models.material_definition import MaterialDefinition
from app.models.personal_croquis import PersonalCroquis, PersonalCroquisVersion
from app.models import personal_croquis_ddl as _personal_croquis_ddl  # noqa: F401 — register DDL
from app.models.personal_croquis_ai_consent import PersonalCroquisAiConsentBinding
from app.models.personal_croquis_spend import PersonalCroquisSpendReservation
from app.models.private_media_asset import PrivateMediaAsset
from app.models.private_media_cleanup import PrivateMediaCleanupQueue
from app.models.iap_apple_notification import IapAppleNotification
from app.models.iap_purchase import IapPurchase
from app.models.iap_stars_adjustment import IapStarsAdjustment
from app.models.push_subscription import PushSubscription
from app.models.rating import Rating
from app.models.email_verification_token import EmailVerificationToken
from app.models.refresh_token import RefreshToken
from app.models.registration_invitation import RegistrationInvitation
from app.models.star_cart import StarCart, StarCartItem
from app.models.techpack_ai_artifact import TechpackAIArtifact
from app.models.techpack_ai_run import TechpackAIRun
from app.models.techpack_draft import TechpackDraft, TechpackExport
from app.models.user import User
from app.models.user_consent_event import UserConsentEvent
from app.models.user_follow import UserFollow
from app.models.user_friendship import UserFriendship
from app.models.user_profile import UserProfile

__all__ = [
    "AIJob",
    "BodyMeasurementProfile",
    "ColorPalette",
    "DesignExport",
    "DesignRevision",
    "FabricAsset",
    "GalleryComment",
    "GalleryCommentLike",
    "GalleryItem",
    "GalleryLike",
    "GarmentDesign",
    "GarmentTemplate",
    "MagicLookMeta",
    "MaterialDefinition",
    "PersonalCroquis",
    "PersonalCroquisVersion",
    "PersonalCroquisAiConsentBinding",
    "PersonalCroquisSpendReservation",
    "PrivateMediaAsset",
    "PrivateMediaCleanupQueue",
    "IapAppleNotification",
    "IapPurchase",
    "IapStarsAdjustment",
    "PushSubscription",
    "Rating",
    "EmailVerificationToken",
    "RefreshToken",
    "RegistrationInvitation",
    "StarCart",
    "StarCartItem",
    "TechpackAIArtifact",
    "TechpackAIRun",
    "TechpackDraft",
    "TechpackExport",
    "User",
    "UserConsentEvent",
    "UserFollow",
    "UserFriendship",
    "UserProfile",
]
