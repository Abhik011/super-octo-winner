
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.checkout import router as checkout_router
from app.api.v1.orders import router as orders_router
from app.core.config import settings
from app.core.database import engine
from app.core.http_client import create_http_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = await create_http_client()

    try:
        yield
    finally:
        await app.state.http_client.aclose()
        await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
)


# Register Orders API
app.include_router(
    orders_router,
    prefix="/api/v1",
)

# Register Checkout API
app.include_router(
    checkout_router,
    prefix="/api/v1",
)


@app.get("/health")
async def health():
    return {
        "service": "order-service",
        "status": "healthy",
    }
