
from uuid import UUID
import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.product import Product
from app.models.category import Category
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductListResponse,
)

router = APIRouter(prefix="/products", tags=["Products"])


@router.post(
    "/",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_product(
    payload: ProductCreate,
    db: AsyncSession = Depends(get_db),
):
    category = await db.get(Category, payload.category_id)

    if not category or not category.is_active:
        raise HTTPException(404, "Active category not found")

    product = Product(
        **payload.model_dump(),
        status="draft",
    )

    db.add(product)

    try:
        await db.commit()
        await db.refresh(product)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            409,
            "Product SKU or slug already exists",
        )

    return product


@router.get("/", response_model=ProductListResponse)
async def list_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    category_id: UUID | None = None,
    search: str | None = Query(None, max_length=100),
    product_status: str | None = Query(
        None,
        alias="status",
        pattern="^(draft|active|archived)$",
    ),
    db: AsyncSession = Depends(get_db),
):
    filters = []

    if category_id:
        filters.append(Product.category_id == category_id)

    if product_status:
        filters.append(Product.status == product_status)

    if search:
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                Product.name.ilike(term),
                Product.sku.ilike(term),
                Product.description.ilike(term),
            )
        )

    total = await db.scalar(
        select(func.count(Product.id)).where(*filters)
    )

    result = await db.scalars(
        select(Product)
        .where(*filters)
        .order_by(Product.created_at.desc(), Product.id)
        .offset(skip)
        .limit(limit)
    )

    return ProductListResponse(
        items=result.all(),
        total=total or 0,
        skip=skip,
        limit=limit,
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    product = await db.get(Product, product_id)

    if not product:
        raise HTTPException(404, "Product not found")

    return product


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    db: AsyncSession = Depends(get_db),
):
    product = await db.get(Product, product_id)

    if not product:
        raise HTTPException(404, "Product not found")

    updates = payload.model_dump(exclude_unset=True)

    if "category_id" in updates:
        category_id = updates["category_id"]

        if category_id is None:
            raise HTTPException(422, "Category cannot be null")

        category = await db.get(Category, category_id)

        if not category or not category.is_active:
            raise HTTPException(404, "Active category not found")

    if "slug" in updates and updates["slug"] is not None:
        slug = updates["slug"].lower().strip()

        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            raise HTTPException(422, "Invalid product slug")

        updates["slug"] = slug

    if "currency" in updates and updates["currency"] is not None:
        updates["currency"] = updates["currency"].upper()

    for key, value in updates.items():
        setattr(product, key, value)

    try:
        await db.commit()
        await db.refresh(product)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            409,
            "Product slug or another database constraint conflicts",
        )

    return product


@router.post("/{product_id}/publish", response_model=ProductResponse)
async def publish_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    product = await db.get(Product, product_id)

    if not product:
        raise HTTPException(404, "Product not found")

    if product.status == "archived":
        raise HTTPException(409, "Archived products cannot be published")

    product.status = "active"

    await db.commit()
    await db.refresh(product)

    return product


@router.post("/{product_id}/archive", response_model=ProductResponse)
async def archive_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    product = await db.get(Product, product_id)

    if not product:
        raise HTTPException(404, "Product not found")

    product.status = "archived"

    await db.commit()
    await db.refresh(product)

    return product
