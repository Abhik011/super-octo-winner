import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.api.v1.router import api_router
from app.db.session import engine
from app.services.reservation_expiry import reservation_expiry_worker

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    expiry_task = asyncio.create_task(
        reservation_expiry_worker(),
        name="reservation-expiry-worker",
    )

    try:
        yield
    finally:
        expiry_task.cancel()

        try:
            await expiry_task
        except asyncio.CancelledError:
            pass

        await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "service": "inventory",
        "message": "Inventory Service is running",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "inventory",
    }