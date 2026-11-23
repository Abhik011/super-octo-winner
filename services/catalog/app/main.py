from fastapi import FastAPI

from app.core.config import settings
from app.api.v1.router import api_router

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "service": "catalog",
        "message": "Catalog Service is running",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "catalog",
    }