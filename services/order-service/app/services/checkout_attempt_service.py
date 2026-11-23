
from fastapi import HTTPException

from app.repositories.checkout_repository import (
    create_or_get_checkout_attempt,
)


async def start_checkout_attempt(
    db,
    user_id,
    idempotency_key,
    request_hash,
):
    attempt, created = await create_or_get_checkout_attempt(
        db=db,
        user_id=user_id,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )

    if created:
        return attempt

    if attempt.status in ("processing", "completed"):
        return attempt

    if attempt.status == "failed":
        raise HTTPException(
            status_code=409,
            detail="Previous checkout failed. Use a new idempotency key.",
        )

    if attempt.status == "compensation_pending":
        raise HTTPException(
            status_code=409,
            detail="Checkout requires inventory compensation.",
        )

    raise HTTPException(
        status_code=409,
        detail="Checkout attempt cannot be continued.",
    )
