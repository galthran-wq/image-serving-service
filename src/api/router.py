from fastapi import APIRouter

from src.api.endpoints import health, images

router = APIRouter()
router.include_router(health.router, tags=["health"])
router.include_router(images.router, tags=["images"])
