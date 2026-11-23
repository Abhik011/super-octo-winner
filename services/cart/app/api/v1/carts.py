from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_id
from app.db.session import get_db
from app.schemas.cart import (
    CartItemCreate,
    CartItemUpdate,
    CartMergeRequest,
    CartResponse,
)
from app.services.cart_service import (
    create_guest_cart,
    get_guest_cart,
    add_cart_item,
    update_cart_item,
    remove_cart_item,
    get_user_cart,
    add_user_cart_item,
    update_user_cart_item,
    remove_user_cart_item,
    merge_guest_cart,
)

router = APIRouter(prefix="/carts", tags=["Cart"])


# -------------------------
# Guest cart endpoints
# -------------------------

@router.post(
    "/guest",
    response_model=CartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_cart(
    db: AsyncSession = Depends(get_db),
):
    return await create_guest_cart(db)


@router.get(
    "/guest/{guest_id}",
    response_model=CartResponse,
)
async def get_cart(
    guest_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    return await get_guest_cart(db, guest_id)


@router.post(
    "/guest/{guest_id}/items",
    response_model=CartResponse,
)
async def add_item(
    guest_id: UUID,
    payload: CartItemCreate,
    db: AsyncSession = Depends(get_db),
):
    return await add_cart_item(db, guest_id, payload)


@router.patch(
    "/guest/{guest_id}/items/{item_id}",
    response_model=CartResponse,
)
async def update_item(
    guest_id: UUID,
    item_id: UUID,
    payload: CartItemUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await update_cart_item(
        db, guest_id, item_id, payload.quantity
    )


@router.delete(
    "/guest/{guest_id}/items/{item_id}",
    response_model=CartResponse,
)
async def delete_item(
    guest_id: UUID,
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    return await remove_cart_item(db, guest_id, item_id)


# -------------------------
# Authenticated cart endpoints
# -------------------------

@router.get(
    "/me",
    response_model=CartResponse,
)
async def get_my_cart(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await get_user_cart(db, user_id)


@router.post(
    "/me/items",
    response_model=CartResponse,
)
async def add_my_cart_item(
    payload: CartItemCreate,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await add_user_cart_item(db, user_id, payload)


@router.patch(
    "/me/items/{item_id}",
    response_model=CartResponse,
)
async def update_my_cart_item(
    item_id: UUID,
    payload: CartItemUpdate,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await update_user_cart_item(
        db, user_id, item_id, payload.quantity
    )


@router.delete(
    "/me/items/{item_id}",
    response_model=CartResponse,
)
async def delete_my_cart_item(
    item_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await remove_user_cart_item(
        db, user_id, item_id
    )


@router.post(
    "/merge",
    response_model=CartResponse,
)
async def merge_my_cart(
    payload: CartMergeRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await merge_guest_cart(
        db,
        user_id,
        payload.guest_id,
    )