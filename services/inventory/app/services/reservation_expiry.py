import asyncio
import logging

from sqlalchemy import func, select

from app.db.session import AsyncSessionLocal
from app.models.inventory_item import InventoryItem
from app.models.reservation import StockReservation
from app.models.reservation_item import StockReservationItem

logger = logging.getLogger(__name__)

BATCH_SIZE = 100
POLL_INTERVAL_SECONDS = 5


async def expire_due_reservations(
    batch_size: int = BATCH_SIZE,
) -> int:
    """
    Expire overdue reservations and release their stock atomically.
    Safe for multiple workers through PostgreSQL SKIP LOCKED.
    """

    async with AsyncSessionLocal() as db:
        async with db.begin():

            # Lock eligible reservations so another worker cannot
            # process the same reservation simultaneously.
            result = await db.scalars(
                select(StockReservation)
                .where(
                    StockReservation.status == "active",
                    StockReservation.expires_at <= func.now(),
                )
                .order_by(StockReservation.expires_at)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )

            reservations = list(result.all())

            if not reservations:
                return 0

            reservation_ids = [r.id for r in reservations]

            # Fetch all reservation lines for this batch.
            result = await db.scalars(
                select(StockReservationItem)
                .where(
                    StockReservationItem.reservation_id.in_(
                        reservation_ids
                    )
                )
                .order_by(
                    StockReservationItem.inventory_item_id
                )
            )

            reservation_lines = list(result.all())

            # Aggregate quantities by inventory item.
            release_quantities: dict = {}

            for line in reservation_lines:
                release_quantities[line.inventory_item_id] = (
                    release_quantities.get(
                        line.inventory_item_id, 0
                    ) + line.quantity
                )

            # Lock inventory rows in a consistent order.
            inventory_ids = sorted(
                release_quantities,
                key=str,
            )

            if inventory_ids:
                result = await db.scalars(
                    select(InventoryItem)
                    .where(InventoryItem.id.in_(inventory_ids))
                    .order_by(InventoryItem.id)
                    .with_for_update()
                )

                inventory_items = {
                    item.id: item
                    for item in result.all()
                }

                # Validate all quantities before changing anything.
                for item_id, quantity in release_quantities.items():
                    item = inventory_items.get(item_id)

                    if item is None:
                        raise RuntimeError(
                            f"Inventory item {item_id} is missing"
                        )

                    if item.quantity_reserved < quantity:
                        raise RuntimeError(
                            f"Reserved quantity inconsistency for "
                            f"inventory item {item_id}"
                        )

                # Release the reserved quantities.
                for item_id, quantity in release_quantities.items():
                    inventory_items[item_id].quantity_reserved -= quantity

            # Mark reservations expired in the same transaction.
            for reservation in reservations:
                reservation.status = "expired"

            processed_count = len(reservations)

        # Transaction commits here.
        return processed_count


async def reservation_expiry_worker():
    logger.info("Reservation expiry worker started")

    while True:
        try:
            processed = await expire_due_reservations()

            if processed:
                logger.info(
                    "Expired %s reservations",
                    processed,
                )

            # If the batch was full, immediately check for more.
            if processed == BATCH_SIZE:
                continue

        except asyncio.CancelledError:
            logger.info("Reservation expiry worker stopping")
            raise

        except Exception:
            logger.exception(
                "Reservation expiry batch failed"
            )

        await asyncio.sleep(POLL_INTERVAL_SECONDS)