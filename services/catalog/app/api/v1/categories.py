from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.category import Category
from app.schemas.category import (
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse,
)

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.post(
    "/",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    payload: CategoryCreate,
    db: AsyncSession = Depends(get_db),
):
    if payload.parent_id:
        parent = await db.get(Category, payload.parent_id)

        if not parent:
            raise HTTPException(404, "Parent category not found")

    category = Category(**payload.model_dump())

    db.add(category)

    try:
        await db.commit()
        await db.refresh(category)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            409,
            "Category slug already exists or category relationship is invalid",
        )

    return category


@router.get("/", response_model=list[CategoryResponse])
async def list_categories(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    if skip < 0 or not 1 <= limit <= 100:
        raise HTTPException(400, "Invalid pagination parameters")

    result = await db.scalars(
        select(Category)
        .order_by(Category.name)
        .offset(skip)
        .limit(limit)
    )

    return result.all()


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    category = await db.get(Category, category_id)

    if not category:
        raise HTTPException(404, "Category not found")

    return category


@router.patch("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: UUID,
    payload: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
):
    category = await db.get(Category, category_id)

    if not category:
        raise HTTPException(404, "Category not found")

    updates = payload.model_dump(exclude_unset=True)

    if "slug" in updates and updates["slug"] is not None:
        import re

        updates["slug"] = updates["slug"].lower().strip()

        if not re.fullmatch(
            r"[a-z0-9]+(?:-[a-z0-9]+)*",
            updates["slug"],
        ):
            raise HTTPException(422, "Invalid category slug")

    if "parent_id" in updates:
        parent_id = updates["parent_id"]

        if parent_id == category.id:
            raise HTTPException(400, "Category cannot be its own parent")

        if parent_id is not None:
            parent = await db.get(Category, parent_id)

            if not parent:
                raise HTTPException(404, "Parent category not found")

    for key, value in updates.items():
        setattr(category, key, value)

    try:
        await db.commit()
        await db.refresh(category)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Category update violates a database constraint")

    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    category = await db.get(Category, category_id)

    if not category:
        raise HTTPException(404, "Category not found")

    await db.delete(category)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            409,
            "Cannot delete a category containing products or child categories",
        )