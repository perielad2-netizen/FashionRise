from fastapi import APIRouter

from app.api.v1.routes import (
    ai_routes,
    auth,
    designs,
    exports,
    gallery,
    materials,
    palettes,
    profiles,
    ratings,
    templates,
    uploads,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(profiles.router, prefix="/profiles", tags=["profiles"])
api_router.include_router(designs.router, prefix="/designs", tags=["designs"])
api_router.include_router(materials.router, prefix="/materials", tags=["materials"])
api_router.include_router(templates.router, prefix="/templates", tags=["templates"])
api_router.include_router(palettes.router, prefix="/palettes", tags=["palettes"])
api_router.include_router(gallery.router, prefix="/gallery", tags=["gallery"])
api_router.include_router(ratings.router, prefix="/ratings", tags=["ratings"])
api_router.include_router(exports.router, prefix="/exports", tags=["exports"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
api_router.include_router(ai_routes.router, prefix="/ai", tags=["ai"])
