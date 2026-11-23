from fastapi import APIRouter

from app.api.v1.categories import router as categories_router
from app.api.v1.products import router as products_router
from app.api.v1.variants import router as variants_router
from app.api.v1.images import router as images_router

api_router = APIRouter()

api_router.include_router(categories_router)
api_router.include_router(products_router)
api_router.include_router(variants_router)
api_router.include_router(images_router)