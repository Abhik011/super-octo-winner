
from datetime import timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.checkout_attempt import CheckoutAttempt
from app.models.order import Order, OrderItem, OrderStatus


# --------------------------------------------------
# CHECKOUT ATTEMPT: CREATE OR RETRIEVE
# --------------------------------------------------

async def create_or_get_checkout_attempt(
    db: AsyncSession,
    user_id: UUID,
    idempotency_key: str,
    request_hash: str,
):
    statement = (
        insert(CheckoutAttempt)
        .values(
            id=uuid4(),
            user_id=user_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status="processing",
        )
        .on_conflict_do_nothing(
            index_elements=[
                CheckoutAttempt.user_id,
                CheckoutAttempt.idempotency_key,
            ]
        )
        .returning(CheckoutAttempt.id)
    )

    try:
        result = await db.execute(statement)
        created_id = result.scalar_one_or_none()
        await db.commit()

        attempt = await db.scalar(
            select(CheckoutAttempt).where(
                CheckoutAttempt.user_id == user_id,
                CheckoutAttempt.idempotency_key == idempotency_key,
            )
        )

        if attempt is None:
            raise HTTPException(
                status_code=500,
                detail="Unable to create checkout attempt",
            )

        if attempt.request_hash != request_hash:
            raise HTTPException(
                status_code=409,
                detail="Idempotency key reused with different checkout data",
            )

        return attempt, created_id is not None

    except Exception:
        await db.rollback()
        raise


# --------------------------------------------------
# CHECKOUT ATTEMPT: RETRIEVE
# --------------------------------------------------

async def get_checkout_attempt(
    db: AsyncSession,
    user_id: UUID,
    idempotency_key: str,
):
    return await db.scalar(
        select(CheckoutAttempt).where(
            CheckoutAttempt.user_id == user_id,
            CheckoutAttempt.idempotency_key == idempotency_key,
        )
    )


# --------------------------------------------------
# CHECKOUT ATTEMPT: MARK FAILED OR COMPENSATION
# --------------------------------------------------

async def mark_checkout_failed(
    db: AsyncSession,
    attempt: CheckoutAttempt,
    error_message: str,
):
    try:
        attempt.error_message = error_message[:500]

        if attempt.reservation_id is not None:
            # Reservation still needs to be released.
            attempt.status = "compensation_pending"
        else:
            attempt.status = "failed"

        attempt.lease_token = None
        attempt.lease_expires_at = None

        await db.commit()
        await db.refresh(attempt)

        return attempt

    except Exception:
        await db.rollback()
        raise


# --------------------------------------------------
# LEASE: ACQUIRE
# --------------------------------------------------

async def acquire_checkout_lease(
    db: AsyncSession,
    attempt_id: UUID,
    lease_duration_seconds: int = 60,
):
    if lease_duration_seconds <= 0:
        raise ValueError("Lease duration must be positive")

    lease_token = uuid4()

    statement = (
        update(CheckoutAttempt)
        .where(
            CheckoutAttempt.id == attempt_id,
            CheckoutAttempt.status == "processing",
        (
            CheckoutAttempt.lease_token.is_(None)
            | (CheckoutAttempt.lease_expires_at <= func.now())
        ),

        
        )
        .values(
            lease_token=lease_token,
            lease_expires_at=(
                func.now() + timedelta(seconds=lease_duration_seconds)
            ),
        )
        .returning(CheckoutAttempt.id)
    )

    try:
        result = await db.execute(statement)
        acquired_id = result.scalar_one_or_none()

        await db.commit()

        return acquired_id is not None, lease_token if acquired_id else None

    except Exception:
        await db.rollback()
        raise


# --------------------------------------------------
# LEASE: RENEW
# --------------------------------------------------

async def renew_checkout_lease(
    db: AsyncSession,
    attempt_id: UUID,
    lease_token: UUID,
    lease_duration_seconds: int = 60,
):
    if lease_duration_seconds <= 0:
        raise ValueError("Lease duration must be positive")

    statement = (
        update(CheckoutAttempt)
        .where(
            CheckoutAttempt.id == attempt_id,
            CheckoutAttempt.status == "processing",
            CheckoutAttempt.lease_token == lease_token,
            CheckoutAttempt.lease_expires_at > func.now(),
        )
        .values(
            lease_expires_at=(
                func.now() + timedelta(seconds=lease_duration_seconds)
            ),
        )
        .returning(CheckoutAttempt.id)
    )

    try:
        result = await db.execute(statement)
        renewed_id = result.scalar_one_or_none()

        await db.commit()

        return renewed_id is not None

    except Exception:
        await db.rollback()
        raise


# --------------------------------------------------
# RESERVATION: SAVE
# --------------------------------------------------

async def save_checkout_reservation(
    db: AsyncSession,
    attempt_id: UUID,
    lease_token: UUID,
    reservation_id: UUID,
):
    statement = (
        update(CheckoutAttempt)
        .where(
            CheckoutAttempt.id == attempt_id,
            CheckoutAttempt.status == "processing",
            CheckoutAttempt.lease_token == lease_token,
            CheckoutAttempt.lease_expires_at > func.now(),
            (
                CheckoutAttempt.reservation_id.is_(None)
                | (CheckoutAttempt.reservation_id == reservation_id)
            ),
        )
        .values(
            reservation_id=reservation_id,
        )
        .returning(CheckoutAttempt.id)
    )

    try:
        result = await db.execute(statement)
        saved_id = result.scalar_one_or_none()

        await db.commit()

        return saved_id is not None

    except Exception:
        await db.rollback()
        raise


# --------------------------------------------------
# ORDER: ATOMIC CREATION AND CHECKOUT COMPLETION
# --------------------------------------------------

async def create_order_from_checkout(
    db: AsyncSession,
    attempt_id: UUID,
    lease_token: UUID,
    checkout_data: dict,
):
    try:
        attempt = await db.scalar(
            select(CheckoutAttempt)
            .where(CheckoutAttempt.id == attempt_id)
            .with_for_update()
        )

        if attempt is None:
            raise HTTPException(
                status_code=404,
                detail="Checkout attempt not found",
            )

        # Idempotent response for an already completed checkout.
        if attempt.status == "completed":
            if attempt.order_id is None:
                raise HTTPException(
                    status_code=500,
                    detail="Completed checkout has no order reference",
                )

            existing_order = await db.scalar(
                select(Order)
                .where(Order.id == attempt.order_id)
                .options(selectinload(Order.items))
            )

            if existing_order is None:
                raise HTTPException(
                    status_code=500,
                    detail="Checkout order could not be retrieved",
                )

            await db.commit()
            return existing_order

        if (
            attempt.status != "processing"
            or attempt.lease_token != lease_token
            or attempt.lease_expires_at is None
            or attempt.reservation_id is None
        ):
            raise HTTPException(
                status_code=409,
                detail="Checkout lease or inventory reservation is invalid",
            )

        # Check lease against the PostgreSQL clock.
        lease_is_valid = await db.scalar(
            select(CheckoutAttempt.id).where(
                CheckoutAttempt.id == attempt_id,
                CheckoutAttempt.lease_token == lease_token,
                CheckoutAttempt.lease_expires_at > func.now(),
                CheckoutAttempt.status == "processing",
            )
        )

        if lease_is_valid is None:
            raise HTTPException(
                status_code=409,
                detail="Checkout lease has expired",
            )

        user_id = UUID(str(checkout_data["user_id"]))
        cart_id = UUID(str(checkout_data["cart_id"]))

        if user_id != attempt.user_id:
            raise HTTPException(
                status_code=403,
                detail="Checkout customer does not match attempt",
            )

        items = checkout_data["items"]

        if not items:
            raise HTTPException(
                status_code=400,
                detail="Cannot create an order without items",
            )

        subtotal_minor = checkout_data["subtotal_minor"]

        if (
            not isinstance(subtotal_minor, int)
            or isinstance(subtotal_minor, bool)
            or subtotal_minor < 0
        ):
            raise HTTPException(
                status_code=400,
                detail="Invalid checkout subtotal",
            )

        calculated_total = 0

        for item in items:
            quantity = item["quantity"]
            unit_price = item["unit_price_minor"]
            line_total = item["line_total_minor"]

            if (
                not isinstance(quantity, int)
                or isinstance(quantity, bool)
                or quantity <= 0
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid order item quantity",
                )

            if (
                not isinstance(unit_price, int)
                or isinstance(unit_price, bool)
                or unit_price < 0
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid order item price",
                )

            if line_total != unit_price * quantity:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid order item total",
                )

            calculated_total += line_total

        if calculated_total != subtotal_minor:
            raise HTTPException(
                status_code=409,
                detail="Checkout subtotal does not match item totals",
            )

        currency = checkout_data["currency"]

        if not isinstance(currency, str) or len(currency) != 3:
            raise HTTPException(
                status_code=400,
                detail="Invalid order currency",
            )

        # Create the order.
        order = Order(
            order_number=f"ORD-{uuid4().hex[:20].upper()}",
            user_id=user_id,
            cart_id=cart_id,
            status=OrderStatus.PENDING,
            currency=currency.upper(),
            subtotal_amount=subtotal_minor,
            discount_amount=0,
            shipping_amount=0,
            tax_amount=0,
            total_amount=subtotal_minor,
        )

        # Create immutable item snapshots.
        for item in items:
            order.items.append(
                OrderItem(
                    product_id=UUID(str(item["product_id"])),
                    variant_id=(
                        UUID(str(item["variant_id"]))
                        if item.get("variant_id")
                        else None
                    ),
                    product_name=item["product_name"],
                    sku=item["sku"],
                    variant_name=item.get("variant_name"),
                    quantity=item["quantity"],
                    unit_price=item["unit_price_minor"],
                    line_total=item["line_total_minor"],
                )
            )

        db.add(order)

        # Generate order ID without committing.
        await db.flush()

        # Complete the attempt in the same transaction.
        attempt.order_id = order.id
        attempt.status = "completed"
        attempt.lease_token = None
        attempt.lease_expires_at = None
        attempt.error_message = None

        await db.commit()

        return await db.scalar(
            select(Order)
            .where(Order.id == order.id)
            .options(selectinload(Order.items))
        )

    except Exception:
        await db.rollback()
        raise

async def mark_checkout_compensation_complete(
    db: AsyncSession,
    attempt_id: UUID,
):
    """
    Mark checkout failed after its inventory reservation
    has been successfully released.
    """
    try:
        attempt = await db.scalar(
            select(CheckoutAttempt)
            .where(CheckoutAttempt.id == attempt_id)
            .with_for_update()
        )

        if attempt is None:
            raise HTTPException(
                status_code=404,
                detail="Checkout attempt not found",
            )

        # Never change a completed checkout.
        if attempt.status == "completed":
            await db.commit()
            return attempt

        if attempt.status != "compensation_pending":
            raise HTTPException(
                status_code=409,
                detail="Checkout is not awaiting compensation",
            )

        attempt.status = "failed"
        attempt.lease_token = None
        attempt.lease_expires_at = None
        attempt.error_message = "Inventory reservation released"

        await db.commit()
        await db.refresh(attempt)

        return attempt

    except Exception:
        await db.rollback()
        raise 

