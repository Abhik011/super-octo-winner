import hashlib
import json
import uuid

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inventory_item import InventoryItem
from app.models.reservation import StockReservation
from app.models.reservation_item import StockReservationItem    


async def create_stock(
    db: AsyncSession,
    catalog_product_id: uuid.UUID,
    catalog_variant_id: uuid.UUID | None,
    sku: str,
    quantity: int,
):
    item = InventoryItem(
        catalog_product_id=catalog_product_id,
        catalog_variant_id=catalog_variant_id,
        sku=sku.strip().upper(),
        quantity_on_hand=quantity,
        quantity_reserved=0,
    )

    db.add(item)

    try:
        await db.commit()
        await db.refresh(item)
    except Exception:
        await db.rollback()
        raise

    return item


async def adjust_stock(
    db: AsyncSession,
    item_id: uuid.UUID,
    quantity_change: int,
):
    item = await db.scalar(
        select(InventoryItem)
        .where(InventoryItem.id == item_id)
        .with_for_update()
    )

    if not item:
        raise HTTPException(404, "Inventory item not found")

    new_quantity = item.quantity_on_hand + quantity_change

    if new_quantity < item.quantity_reserved:
        raise HTTPException(
            409,
            "Adjustment would reduce stock below reserved quantity",
        )

    item.quantity_on_hand = new_quantity

    await db.commit()
    await db.refresh(item)

    return item


async def reserve_stock(
    db: AsyncSession,
    order_reference: str,
    idempotency_key: str,
    requested_items: list[dict],
):
    order_reference = order_reference.strip()
    idempotency_key = idempotency_key.strip()

    if not order_reference or not idempotency_key:
        raise HTTPException(422, "Order reference and idempotency key are required")

    if len(idempotency_key) > 100:
        raise HTTPException(422, "Idempotency key is too long")

    if not requested_items:
        raise HTTPException(422, "At least one inventory item is required")

    # Normalize and combine duplicate inventory IDs.
    quantities: dict[uuid.UUID, int] = {}

    for line in requested_items:
        try:
            item_id = uuid.UUID(str(line["inventory_item_id"]))
            quantity = line["quantity"]
        except (KeyError, ValueError, TypeError, AttributeError):
            raise HTTPException(422, "Invalid inventory item or quantity")

        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise HTTPException(422, "Quantity must be a positive integer")

        quantities[item_id] = quantities.get(item_id, 0) + quantity

    if len(quantities) > 50:
        raise HTTPException(422, "Too many unique inventory items")

    # Create a deterministic hash, independent of input item ordering.
    canonical_request = {
        "order_reference": order_reference,
        "items": [
            {
                "inventory_item_id": str(item_id),
                "quantity": quantities[item_id],
            }
            for item_id in sorted(quantities, key=str)
        ],
    }

    request_hash = hashlib.sha256(
        json.dumps(
            canonical_request,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    async def find_existing_reservation():
        return await db.scalar(
            select(StockReservation)
            .options(selectinload(StockReservation.items))
            .where(StockReservation.idempotency_key == idempotency_key)
        )

    def validate_replay(existing):
        if existing.order_reference != order_reference:
            raise HTTPException(
                409,
                "Idempotency key was already used for another order",
            )

        if existing.request_hash is None:
            raise HTTPException(
                409,
                "Existing reservation has no request hash; replay cannot be verified",
            )

        if existing.request_hash != request_hash:
            raise HTTPException(
                409,
                "Idempotency key was reused with a different reservation payload",
            )

    # Fast path: handle normal retries.
    existing = await find_existing_reservation()

    if existing:
        validate_replay(existing)
        return existing

    reservation = StockReservation(
        order_reference=order_reference,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        status="active",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )

    try:
        db.add(reservation)
        await db.flush()

        # Lock inventory rows in a consistent order.
        for item_id in sorted(quantities, key=str):
            item = await db.scalar(
                select(InventoryItem)
                .where(InventoryItem.id == item_id)
                .with_for_update()
            )

            if not item:
                raise HTTPException(
                    404,
                    f"Inventory item {item_id} not found",
                )

            quantity = quantities[item_id]

            if item.quantity_on_hand - item.quantity_reserved < quantity:
                raise HTTPException(
                    409,
                    f"Insufficient stock for SKU {item.sku}",
                )

            item.quantity_reserved += quantity

            db.add(
                StockReservationItem(
                    reservation_id=reservation.id,
                    inventory_item_id=item.id,
                    quantity=quantity,
                )
            )

        await db.commit()

        result = await find_existing_reservation()
        return result

    except IntegrityError:
        # Another request may have inserted the same idempotency key.
        await db.rollback()

        existing = await find_existing_reservation()

        if existing:
            validate_replay(existing)
            return existing

        # It was a different integrity error; don't hide it.
        raise

    except Exception:
        await db.rollback()
        raise

async def change_reservation_status(
    db: AsyncSession,
    reservation_id: uuid.UUID,
    target_status: str,
):
    reservation = await db.scalar(
        select(StockReservation)
        .where(StockReservation.id == reservation_id)
        .with_for_update()
    )

    if not reservation:
        raise HTTPException(404, "Reservation not found")

    if target_status == "confirmed" and reservation.status == "confirmed":
        return reservation

    if target_status == "released" and reservation.status in (
        "released",
        "expired",
    ):
        return reservation

    if reservation.status != "active":
        raise HTTPException(
            409,
            f"Cannot {target_status} a {reservation.status} reservation",
        )

    now = datetime.now(timezone.utc)

    lines = await db.scalars(
        select(StockReservationItem)
        .where(StockReservationItem.reservation_id == reservation.id)
        .order_by(StockReservationItem.inventory_item_id)
    )

    items = list(lines.all())

    locked_items = []

    for line in items:
        item = await db.scalar(
            select(InventoryItem)
            .where(InventoryItem.id == line.inventory_item_id)
            .with_for_update()
        )

        if not item:
            raise HTTPException(409, "Reserved inventory record is missing")

        locked_items.append((item, line))

    if target_status == "confirmed" and reservation.expires_at <= now:
        for item, line in locked_items:
            item.quantity_reserved -= line.quantity

        reservation.status = "expired"

        await db.commit()
        await db.refresh(reservation)

        raise HTTPException(409, "Reservation has expired")

    for item, line in locked_items:
        item.quantity_reserved -= line.quantity

        if target_status == "confirmed":
            item.quantity_on_hand -= line.quantity

    reservation.status = target_status

    await db.commit()
    await db.refresh(reservation)

    return reservation
