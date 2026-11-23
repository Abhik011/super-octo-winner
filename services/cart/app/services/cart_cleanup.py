from datetime import datetime, timezone

from sqlalchemy import delete

from app.db.session import AsyncSessionLocal
from app.models.cart import Cart


async def cleanup_expired_carts():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            delete(Cart).where(
                Cart.status == "active",
                Cart.expires_at.is_not(None),
                Cart.expires_at <= datetime.now(timezone.utc),
            )
        )

        await db.commit()

        return result.rowcount or 0