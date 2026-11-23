from fastapi import APIRouter

from app.api.v1.carts import router as carts_router

api_router = APIRouter()
api_router.include_router(carts_router)