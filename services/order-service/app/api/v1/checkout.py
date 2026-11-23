
import hashlib
import json
import logging
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Response,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_http_client
from app.core.security import get_current_user, get_access_token

from app.repositories.checkout_repository import (
    acquire_checkout_lease,
    create_order_from_checkout,
    get_checkout_attempt,
    mark_checkout_compensation_complete,
    mark_checkout_failed,
    renew_checkout_lease,
    save_checkout_reservation,
)
from app.repositories.order_repository import get_user_order_by_id

from app.schemas.checkout import CheckoutRequest
from app.schemas.order import OrderResponse

from app.services.checkout_attempt_service import start_checkout_attempt
from app.services.checkout_client import CheckoutClient
from app.services.checkout_service import CheckoutService


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/checkout",
    tags=["Checkout"],
)


def create_request_hash(payload: CheckoutRequest) -> str:
    """Generate a deterministic hash of checkout request data."""

    normalized = {
        "shipping_address_id": payload.shipping_address_id,
    }

    encoded = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_checkout(
    payload: CheckoutRequest,
    response: Response,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=8,
        max_length=100,
    ),
    user_id: UUID = Depends(get_current_user),
    access_token: str = Depends(get_access_token),
    db: AsyncSession = Depends(get_db),
    http_client=Depends(get_http_client),
):
    # Shipping address persistence is not implemented yet.
    if payload.shipping_address_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Shipping address support is not available yet",
        )

    request_hash = create_request_hash(payload)

    # --------------------------------------------------
    # 1. CREATE OR RETRIEVE IDEMPOTENT CHECKOUT ATTEMPT
    # --------------------------------------------------

    attempt = await start_checkout_attempt(
        db=db,
        user_id=user_id,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )

    # Return the existing order for completed attempts.
    if attempt.status == "completed":
        if attempt.order_id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Completed checkout has no order reference",
            )

        existing_order = await get_user_order_by_id(
            db=db,
            order_id=attempt.order_id,
            user_id=user_id,
        )

        if existing_order is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Previously created order could not be retrieved",
            )

        response.status_code = status.HTTP_200_OK
        return existing_order

    # --------------------------------------------------
    # 2. ACQUIRE CHECKOUT LEASE
    # --------------------------------------------------

    acquired, lease_token = await acquire_checkout_lease(
        db=db,
        attempt_id=attempt.id,
        lease_duration_seconds=120,
    )

    if not acquired:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Checkout is already being processed. Retry shortly.",
        )

    checkout_client = CheckoutClient(http_client)
    checkout_service = CheckoutService(checkout_client)

    reservation_id = None
    reservation_saved = False

    try:
        # --------------------------------------------------
        # 3. VALIDATE CART, CATALOG AND INVENTORY
        # --------------------------------------------------

        checkout_data = await checkout_service.validate_cart(
            access_token=access_token,
            user_id=user_id,
        )

        # Renew lease after potentially lengthy validation.
        lease_renewed = await renew_checkout_lease(
            db=db,
            attempt_id=attempt.id,
            lease_token=lease_token,
            lease_duration_seconds=120,
        )

        if not lease_renewed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Checkout lease expired during cart validation",
            )

        # --------------------------------------------------
        # 4. RESERVE INVENTORY
        # --------------------------------------------------

        inventory_reservation = await checkout_client.reserve_stock(
            order_reference=f"CHK-{attempt.id}",
            inventory_items=checkout_data["inventory_items"],
            idempotency_key=f"checkout-{attempt.id}",
        )

        if not isinstance(inventory_reservation, dict):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Invalid response from Inventory Service",
            )

        reservation_value = (
            inventory_reservation.get("id")
            or inventory_reservation.get("reservation_id")
        )

        if not reservation_value:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Inventory service returned no reservation ID",
            )

        try:
            reservation_id = UUID(str(reservation_value))
        except (ValueError, TypeError, AttributeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Inventory service returned an invalid reservation ID",
            ) from exc

        # Renew lease after inventory reservation.
        lease_renewed = await renew_checkout_lease(
            db=db,
            attempt_id=attempt.id,
            lease_token=lease_token,
            lease_duration_seconds=120,
        )

        if not lease_renewed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Checkout lease expired during inventory reservation",
            )

        # --------------------------------------------------
        # 5. SAVE RESERVATION AGAINST CHECKOUT ATTEMPT
        # --------------------------------------------------

        reservation_saved = await save_checkout_reservation(
            db=db,
            attempt_id=attempt.id,
            lease_token=lease_token,
            reservation_id=reservation_id,
        )

        if not reservation_saved:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Checkout lease expired after inventory reservation. "
                    "The reservation requires recovery."
                ),
            )

        # --------------------------------------------------
        # 6. CREATE ORDER AND COMPLETE CHECKOUT ATOMICALLY
        # --------------------------------------------------

        order = await create_order_from_checkout(
            db=db,
            attempt_id=attempt.id,
            lease_token=lease_token,
            checkout_data=checkout_data,
        )

        logger.info(
            "Checkout completed successfully. user_id=%s order_id=%s",
            user_id,
            order.id,
        )

        return order

    except Exception as exc:
        # --------------------------------------------------
        # 7. LOG FAILURE AND RESET FAILED DB TRANSACTION
        # --------------------------------------------------

        logger.exception(
            "Checkout failed. user_id=%s attempt_id=%s",
            user_id,
            attempt.id,
        )

        try:
            await db.rollback()
        except Exception:
            logger.exception(
                "Database rollback failed. attempt_id=%s",
                attempt.id,
            )

        # --------------------------------------------------
        # 8. RELOAD LATEST CHECKOUT ATTEMPT
        # --------------------------------------------------

        try:
            latest_attempt = await get_checkout_attempt(
                db=db,
                user_id=user_id,
                idempotency_key=idempotency_key,
            )
        except Exception:
            logger.exception(
                "Could not reload checkout attempt. attempt_id=%s",
                attempt.id,
            )

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Checkout recovery could not inspect the attempt.",
            ) from exc

        # An order may have committed even if a later operation failed.
        if latest_attempt and latest_attempt.status == "completed":
            if latest_attempt.order_id is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Completed checkout has no order reference",
                )

            existing_order = await get_user_order_by_id(
                db=db,
                order_id=latest_attempt.order_id,
                user_id=user_id,
            )

            if existing_order is not None:
                response.status_code = status.HTTP_200_OK
                return existing_order

        # --------------------------------------------------
        # 9. HANDLE RESERVATION THAT WAS NOT SAVED
        # --------------------------------------------------

        if reservation_id is not None and not reservation_saved:
            # Do not release blindly. The reservation may be shared
            # by a retry using the same stable Inventory idempotency key.
            # This case must be reconciled by a recovery process.
            logger.critical(
                "Inventory reservation exists but was not saved "
                "to checkout attempt. attempt_id=%s reservation_id=%s",
                attempt.id,
                reservation_id,
            )

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "Inventory reservation may have been created, "
                    "but checkout could not save its reference. "
                    "Do not create a new checkout key; this attempt "
                    "requires recovery."
                ),
            ) from exc

        # --------------------------------------------------
        # 10. MARK CHECKOUT FAILED OR COMPENSATION PENDING
        # --------------------------------------------------

        if latest_attempt is not None:
            try:
                await mark_checkout_failed(
                    db=db,
                    attempt=latest_attempt,
                    error_message=str(exc)[:2000],
                )
            except Exception:
                logger.exception(
                    "Could not update failed checkout attempt. "
                    "attempt_id=%s",
                    attempt.id,
                )

                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Checkout failed and recovery status could not be saved.",
                ) from exc

        # --------------------------------------------------
        # 11. RELEASE INVENTORY IF RESERVATION WAS SAVED
        # --------------------------------------------------

        if reservation_saved and reservation_id is not None:
            try:
                await checkout_client.release_stock(
                    str(reservation_id)
                )

                await mark_checkout_compensation_complete(
                    db=db,
                    attempt_id=attempt.id,
                )

                logger.info(
                    "Inventory reservation released after checkout failure. "
                    "attempt_id=%s reservation_id=%s",
                    attempt.id,
                    reservation_id,
                )

            except Exception:
                logger.exception(
                    "Inventory compensation failed. "
                    "Attempt remains pending recovery. attempt_id=%s "
                    "reservation_id=%s",
                    attempt.id,
                    reservation_id,
                )

        # --------------------------------------------------
        # 12. RETURN APPROPRIATE ERROR
        # --------------------------------------------------

        if isinstance(exc, HTTPException):
            raise exc

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Checkout could not be completed. Please retry.",
        ) from exc
