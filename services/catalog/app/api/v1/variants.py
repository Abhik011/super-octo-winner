
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.schemas.product_variant import (
    VariantCreate,
    VariantUpdate,
    VariantResponse,
)

router = APIRouter(prefix="/products", tags=["Product Variants"])


@router.post(
    "/{product_id}/variants",
    response_model=VariantResponse,
    status_code=201,
)
async def create_variant(
    product_id: UUID,
    payload: VariantCreate,
    db: AsyncSession = Depends(get_db),
):
    product = await db.get(Product, product_id)

    if not product or product.status == "archived":
        raise HTTPException(404, "Available product not found")

    variant = ProductVariant(
        product_id=product_id,
        sku=payload.sku.strip().upper(),
        attributes=payload.attributes,
        price_minor=payload.price_minor,
        is_active=payload.is_active,
    )

    db.add(variant)

    try:
        await db.commit()
        await db.refresh(variant)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Variant SKU already exists")

    return variant


@router.get(
    "/{product_id}/variants",
    response_model=list[VariantResponse],
)
async def list_variants(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    product = await db.get(Product, product_id)

    if not product:
        raise HTTPException(404, "Product not found")

    result = await db.scalars(
        select(ProductVariant)
        .where(ProductVariant.product_id == product_id)
        .order_by(ProductVariant.sku)
    )

    return result.all()


@router.patch(
    "/{product_id}/variants/{variant_id}",
    response_model=VariantResponse,
)
async def update_variant(
    product_id: UUID,
    variant_id: UUID,
    payload: VariantUpdate,
    db: AsyncSession = Depends(get_db),
):
    variant = await db.scalar(
        select(ProductVariant).where(
            ProductVariant.id == variant_id,
            ProductVariant.product_id == product_id,
        )
    )

    if not variant:
        raise HTTPException(404, "Variant not found")

    updates = payload.model_dump(exclude_unset=True)

    if "sku" in updates and updates["sku"] is not None:
        updates["sku"] = updates["sku"].strip().upper()

    for key, value in updates.items():
        setattr(variant, key, value)

    try:
        await db.commit()
        await db.refresh(variant)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Variant SKU already exists")

    return variant


@router.delete(
    "/{product_id}/variants/{variant_id}",
    status_code=204,
)
async def delete_variant(
    product_id: UUID,
    variant_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    variant = await db.scalar(
        select(ProductVariant).where(
            ProductVariant.id == variant_id,
            ProductVariant.product_id == product_id,
        )
    )

    if not variant:
        raise HTTPException(404, "Variant not found")

    await db.delete(variant)
    await db.commit()
