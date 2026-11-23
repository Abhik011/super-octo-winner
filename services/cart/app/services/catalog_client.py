import json
from uuid import UUID

import httpx
from fastapi import HTTPException
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.redis import redis_client


CACHE_TTL = 300
CATALOG_TIMEOUT = 5.0


async def cached_get(key: str, url: str):
    try:
        cached = await redis_client.get(key)
        if cached:
            return json.loads(cached)
    except (RedisError, json.JSONDecodeError):
        pass

    try:
        async with httpx.AsyncClient(
            timeout=CATALOG_TIMEOUT
        ) as client:
            response = await client.get(url)

        if response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail="Catalog resource not found",
            )

        response.raise_for_status()
        data = response.json()

    except HTTPException:
        raise
    except httpx.HTTPStatusError:
        raise HTTPException(
            status_code=503,
            detail="Catalog Service returned an error",
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Catalog Service is unavailable",
        )

    try:
        await redis_client.setex(
            key,
            CACHE_TTL,
            json.dumps(data),
        )
    except RedisError:
        pass

    return data


async def get_product(product_id: UUID):
    return await cached_get(
        f"catalog:product:{product_id}",
        f"{settings.CATALOG_SERVICE_URL}/api/v1/products/{product_id}",
    )


async def get_product_variants(product_id: UUID):
    return await cached_get(
        f"catalog:variants:{product_id}",
        f"{settings.CATALOG_SERVICE_URL}/api/v1/products/{product_id}/variants",
    )


async def validate_cart_product(
    product_id: UUID,
    variant_id: UUID | None,
    sku: str,
):
    product = await get_product(product_id)

    if product.get("status") != "active":
        raise HTTPException(
            status_code=400,
            detail="Product is not available",
        )

    if variant_id is None:
        if product.get("sku") != sku:
            raise HTTPException(
                status_code=400,
                detail="Product SKU mismatch",
            )
        return product

    variants = await get_product_variants(product_id)

    variant = next(
        (
            item for item in variants
            if item.get("id") == str(variant_id)
        ),
        None,
    )

    if not variant:
        raise HTTPException(
            status_code=400,
            detail="Invalid product variant",
        )

    if variant.get("product_id") != str(product_id):
        raise HTTPException(
            status_code=400,
            detail="Variant does not belong to this product",
        )

    if not variant.get("is_active"):
        raise HTTPException(
            status_code=400,
            detail="Variant is unavailable",
        )

    if variant.get("sku") != sku:
        raise HTTPException(
            status_code=400,
            detail="Variant SKU mismatch",
        )

    return product