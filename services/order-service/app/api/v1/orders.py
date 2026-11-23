from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.repositories.order_repository import (
    get_user_orders,
    get_user_order_by_id,
    get_user_order_by_number,
)
from app.schemas.order import OrderResponse

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.get(
    "",
    response_model=list[OrderResponse],
    summary="Get customer order history",
)
async def list_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_user_orders(
        db=db,
        user_id=user_id,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/number/{order_number}",
    response_model=OrderResponse,
    summary="Get order by order number",
)
async def retrieve_order_by_number(
    order_number: str,
    user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    order = await get_user_order_by_number(
        db=db,
        order_number=order_number,
        user_id=user_id,
    )

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    return order


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Get order by ID",
)
async def retrieve_order(
    order_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    order = await get_user_order_by_id(
        db=db,
        order_id=order_id,
        user_id=user_id,
    )

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    return order