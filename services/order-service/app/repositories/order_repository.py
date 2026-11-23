from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order


async def get_user_orders(
    db: AsyncSession,
    user_id: UUID,
    skip: int = 0,
    limit: int = 20,
):
    statement = (
        select(Order)
        .where(Order.user_id == user_id)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc(), Order.id.desc())
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(statement)
    return result.scalars().all()


async def get_user_order_by_id(
    db: AsyncSession,
    order_id: UUID,
    user_id: UUID,
):
    statement = (
        select(Order)
        .where(
            Order.id == order_id,
            Order.user_id == user_id,
        )
        .options(selectinload(Order.items))
    )

    result = await db.execute(statement)
    return result.scalar_one_or_none()


async def get_user_order_by_number(
    db: AsyncSession,
    order_number: str,
    user_id: UUID,
):
    statement = (
        select(Order)
        .where(
            Order.order_number == order_number,
            Order.user_id == user_id,
        )
        .options(selectinload(Order.items))
    )

    result = await db.execute(statement)
    return result.scalar_one_or_none()