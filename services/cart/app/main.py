from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.redis import redis_client, close_redis
from app.core.config import settings
from app.api.v1.router import api_router
from app.core.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verify Redis connection
    await redis_client.ping()

    # Start expired cart cleanup scheduler
    start_scheduler()

    yield

    # Stop scheduler and close Redis
    stop_scheduler()
    await close_redis()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.API_VERSION,
    lifespan=lifespan,
)


app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "service": "Cart Service",
        "status": "running",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}