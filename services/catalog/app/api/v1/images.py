
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.product import Product
from app.models.product_image import ProductImage
from app.schemas.product_image import (
    ProductImageCreate,
    ProductImageResponse,
)

router = APIRouter(prefix="/products", tags=["Product Images"])


@router.post(
    "/{product_id}/images",
    response_model=ProductImageResponse,
    status_code=201,
)
async def add_product_image(
    product_id: UUID,
    payload: ProductImageCreate,
    db: AsyncSession = Depends(get_db),
):
    product = await db.get(Product, product_id)

    if not product or product.status == "archived":
        raise HTTPException(404, "Available product not found")

    image = ProductImage(
        product_id=product_id,
        image_url=str(payload.image_url),
        alt_text=payload.alt_text,
        display_order=payload.display_order,
    )

    db.add(image)
    await db.commit()
    await db.refresh(image)

    return image


@router.get(
    "/{product_id}/images",
    response_model=list[ProductImageResponse],
)
async def list_product_images(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    product = await db.get(Product, product_id)

    if not product:
        raise HTTPException(404, "Product not found")

    result = await db.scalars(
        select(ProductImage)
        .where(ProductImage.product_id == product_id)
        .order_by(
            ProductImage.display_order,
            ProductImage.id,
        )
    )

    return result.all()


@router.delete(
    "/{product_id}/images/{image_id}",
    status_code=204,
)
async def delete_product_image(
    product_id: UUID,
    image_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    image = await db.scalar(
        select(ProductImage).where(
            ProductImage.id == image_id,
            ProductImage.product_id == product_id,
        )
    )

    if not image:
        raise HTTPException(404, "Product image not found")

    await db.delete(image)
    await db.commit()
