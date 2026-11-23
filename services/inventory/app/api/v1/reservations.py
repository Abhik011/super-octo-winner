
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.reservation import StockReservation
from app.schemas.reservation import (
    ReservationCreate,
    ReservationResponse,
)
from app.services.inventory_service import (
    reserve_stock,
    change_reservation_status,
)

router = APIRouter(prefix="/reservations", tags=["Reservations"])


@router.post("/", response_model=ReservationResponse, status_code=201)
async def create_reservation(
    payload: ReservationCreate,
    idempotency_key: str = Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=100,
    ),
    db: AsyncSession = Depends(get_db),
):
    reservation = await reserve_stock(
        db=db,
        order_reference=payload.order_reference,
        idempotency_key=idempotency_key,
        requested_items=[
            line.model_dump() for line in payload.items
        ],
    )

    result = await db.scalar(
        select(StockReservation)
        .options(selectinload(StockReservation.items))
        .where(StockReservation.id == reservation.id)
    )

    return result


@router.post("/{reservation_id}/confirm", response_model=ReservationResponse)
async def confirm_reservation(
    reservation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    reservation = await change_reservation_status(
        db,
        reservation_id,
        "confirmed",
    )

    result = await db.scalar(
        select(StockReservation)
        .options(selectinload(StockReservation.items))
        .where(StockReservation.id == reservation.id)
    )

    return result


@router.post("/{reservation_id}/release", response_model=ReservationResponse)
async def release_reservation(
    reservation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    reservation = await change_reservation_status(
        db,
        reservation_id,
        "released",
    )

    result = await db.scalar(
        select(StockReservation)
        .options(selectinload(StockReservation.items))
        .where(StockReservation.id == reservation.id)
    )

    return result
