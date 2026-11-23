from fastapi import APIRouter

from app.api.v1.inventory import router as inventory_router
from app.api.v1.reservations import router as reservations_router

api_router = APIRouter()

api_router.include_router(inventory_router)
api_router.include_router(reservations_router)