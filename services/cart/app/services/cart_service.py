from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.services.catalog_client import validate_cart_product
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.schemas.cart import CartItemCreate
from datetime import datetime, timedelta, timezone

async def get_guest_cart(
    db: AsyncSession,
    guest_id: UUID,
) -> Cart:
    result = await db.execute(
        select(Cart)
        .options(selectinload(Cart.items))
        .where(
            Cart.guest_id == guest_id,
            Cart.status == "active",
            Cart.expires_at > datetime.now(timezone.utc),  
        )
    )

    cart = result.scalar_one_or_none()

    if cart is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart not found",
        )

    return cart


async def create_guest_cart(db: AsyncSession) -> Cart:
    cart = Cart(
        id=uuid4(),
        guest_id=uuid4(),
        status="active",
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )

    db.add(cart)
    await db.commit()

    return await get_guest_cart(db, cart.guest_id)


async def add_cart_item(
    db: AsyncSession,
    guest_id: UUID,
    payload: CartItemCreate,
) -> Cart:
    

    await validate_cart_product(
        product_id=payload.product_id,
        variant_id=payload.variant_id,
        sku=payload.sku,
    )

    cart = await get_guest_cart(db, guest_id)
    # Lock the cart row to serialize concurrent modifications.
    await db.execute(
        select(Cart)
        .where(Cart.id == cart.id)
        .with_for_update()
    )

   
    
    existing_result = await db.execute(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.sku == payload.sku,
        )
    )
    existing_item = existing_result.scalar_one_or_none()

    if existing_item:
        existing_item.quantity += payload.quantity
    else:
        db.add(
            CartItem(
                cart_id=cart.id,
                product_id=payload.product_id,
                variant_id=payload.variant_id,
                sku=payload.sku,
                quantity=payload.quantity,
            )
        )

    await db.commit()
    return await get_guest_cart(db, guest_id)


async def update_cart_item(
    db: AsyncSession,
    guest_id: UUID,
    item_id: UUID,
    quantity: int,
) -> Cart:
    cart = await get_guest_cart(db, guest_id)

    result = await db.execute(
        select(CartItem).where(
            CartItem.id == item_id,
            CartItem.cart_id == cart.id,
        )
    )
    item = result.scalar_one_or_none()

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Cart item not found",
        )

    item.quantity = quantity
    await db.commit()

    return await get_guest_cart(db, guest_id)


async def remove_cart_item(
    db: AsyncSession,
    guest_id: UUID,
    item_id: UUID,
) -> Cart:
    cart = await get_guest_cart(db, guest_id)

    result = await db.execute(
        select(CartItem).where(
            CartItem.id == item_id,
            CartItem.cart_id == cart.id,
        )
    )
    item = result.scalar_one_or_none()

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Cart item not found",
        )

    await db.delete(item)
    await db.commit()

    return await get_guest_cart(db, guest_id)



from sqlalchemy.exc import IntegrityError


async def get_user_cart(
    db: AsyncSession,
    user_id: UUID,
) -> Cart:
    result = await db.execute(
        select(Cart)
        .options(selectinload(Cart.items))
        .where(
            Cart.user_id == user_id,
            Cart.status == "active",
        )
    )

    cart = result.scalar_one_or_none()

    if cart:
        return cart

    cart = Cart(
        id=uuid4(),
        user_id=user_id,
        status="active",
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )

    db.add(cart)

    try:
        await db.commit()
    except IntegrityError:
        # Another request may have created the user's cart concurrently.
        await db.rollback()

    result = await db.execute(
        select(Cart)
        .options(selectinload(Cart.items))
        .where(
            Cart.user_id == user_id,
            Cart.status == "active",
        )
    )

    cart = result.scalar_one_or_none()

    if cart is None:
        raise HTTPException(
            status_code=500,
            detail="Unable to create or retrieve user cart",
        )

    return cart


async def add_user_cart_item(
    db: AsyncSession,
    user_id: UUID,
    payload: CartItemCreate,
) -> Cart:
    await validate_cart_product(
        product_id=payload.product_id,
        variant_id=payload.variant_id,
        sku=payload.sku,
    )

    cart = await get_user_cart(db, user_id)

    # Lock the cart row to serialize simultaneous additions.
    await db.execute(
        select(Cart)
        .where(
            Cart.id == cart.id,
            Cart.user_id == user_id,
            Cart.status == "active",
        )
        .with_for_update()
    )

    result = await db.execute(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.sku == payload.sku,
        )
    )
    existing_item = result.scalar_one_or_none()

    if existing_item:
        new_quantity = existing_item.quantity + payload.quantity

        if new_quantity > 100:
            raise HTTPException(
                status_code=409,
                detail="Maximum quantity of 100 per SKU exceeded",
            )

        existing_item.quantity = new_quantity
    else:
        db.add(
            CartItem(
                cart_id=cart.id,
                product_id=payload.product_id,
                variant_id=payload.variant_id,
                sku=payload.sku,
                quantity=payload.quantity,
            )
        )

    await db.commit()
    return await get_user_cart(db, user_id)


async def update_user_cart_item(
    db: AsyncSession,
    user_id: UUID,
    item_id: UUID,
    quantity: int,
) -> Cart:
    cart = await get_user_cart(db, user_id)

    await db.execute(
        select(Cart)
        .where(Cart.id == cart.id)
        .with_for_update()
    )

    result = await db.execute(
        select(CartItem).where(
            CartItem.id == item_id,
            CartItem.cart_id == cart.id,
        )
    )
    item = result.scalar_one_or_none()

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Cart item not found",
        )

    item.quantity = quantity
    await db.commit()

    return await get_user_cart(db, user_id)


async def remove_user_cart_item(
    db: AsyncSession,
    user_id: UUID,
    item_id: UUID,
) -> Cart:
    cart = await get_user_cart(db, user_id)

    await db.execute(
        select(Cart)
        .where(Cart.id == cart.id)
        .with_for_update()
    )

    result = await db.execute(
        select(CartItem).where(
            CartItem.id == item_id,
            CartItem.cart_id == cart.id,
        )
    )
    item = result.scalar_one_or_none()

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Cart item not found",
        )

    await db.delete(item)
    await db.commit()

    return await get_user_cart(db, user_id)


async def merge_guest_cart(
    db: AsyncSession,
    user_id: UUID,
    guest_id: UUID,
) -> Cart:
    try:
        # 1. Find the guest cart.
        result = await db.execute(
            select(Cart).where(Cart.guest_id == guest_id)
        )
        guest_cart = result.scalar_one_or_none()

        if guest_cart is None:
            raise HTTPException(
                status_code=404,
                detail="Guest cart not found",
            )

        # 2. Handle repeated merge requests.
        if guest_cart.status == "converted":
            if guest_cart.user_id == user_id:
                return await get_user_cart(db, user_id)

            raise HTTPException(
                status_code=409,
                detail="Guest cart has already been converted",
            )

        # 3. Validate guest cart.
        now = datetime.now(timezone.utc)

        if (
            guest_cart.status != "active"
            or guest_cart.expires_at is None
            or guest_cart.expires_at <= now
        ):
            raise HTTPException(
                status_code=404,
                detail="Guest cart is expired or inactive",
            )

        # 4. Validate guest products against Catalog.
        guest_cart = await get_guest_cart(db, guest_id)

        for item in guest_cart.items:
            await validate_cart_product(
                product_id=item.product_id,
                variant_id=item.variant_id,
                sku=item.sku,
            )

        # 5. Get authenticated user's cart.
        user_cart = await get_user_cart(db, user_id)

        # 6. Lock both cart rows in consistent order.
        cart_ids = sorted(
            [guest_cart.id, user_cart.id],
            key=str,
        )

        lock_result = await db.execute(
            select(Cart)
            .where(Cart.id.in_(cart_ids))
            .order_by(Cart.id)
            .with_for_update()
        )

        locked_carts = lock_result.scalars().all()

        if len(locked_carts) != 2:
            raise HTTPException(
                status_code=409,
                detail="Unable to lock both carts",
            )

        # 7. Reload both carts and their items.
        result = await db.execute(
            select(Cart)
            .options(selectinload(Cart.items))
            .where(Cart.id == guest_cart.id)
            .execution_options(populate_existing=True)
        )
        guest_cart = result.scalar_one_or_none()

        result = await db.execute(
            select(Cart)
            .options(selectinload(Cart.items))
            .where(
                Cart.id == user_cart.id,
                Cart.user_id == user_id,
                Cart.status == "active",
            )
            .execution_options(populate_existing=True)
        )
        user_cart = result.scalar_one_or_none()

        if guest_cart is None or user_cart is None:
            raise HTTPException(
                status_code=409,
                detail="Cart state changed during merge",
            )

        # 8. Recheck guest cart after obtaining locks.
        if guest_cart.status == "converted":
            if guest_cart.user_id == user_id:
                await db.rollback()
                return await get_user_cart(db, user_id)

            raise HTTPException(
                status_code=409,
                detail="Guest cart has already been converted",
            )

        now = datetime.now(timezone.utc)

        if (
            guest_cart.status != "active"
            or guest_cart.expires_at is None
            or guest_cart.expires_at <= now
        ):
            raise HTTPException(
                status_code=404,
                detail="Guest cart is expired or inactive",
            )

        # 9. Index existing user cart items by SKU.
        user_items_by_sku = {
            item.sku: item
            for item in user_cart.items
        }

        # 10. Merge guest cart items.
        for guest_item in guest_cart.items:
            existing_item = user_items_by_sku.get(
                guest_item.sku
            )

            if existing_item:
                # Ensure SKU identifies the same product/variant.
                if (
                    existing_item.product_id
                    != guest_item.product_id
                    or existing_item.variant_id
                    != guest_item.variant_id
                ):
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"SKU conflict detected: "
                            f"{guest_item.sku}"
                        ),
                    )

                combined_quantity = (
                    existing_item.quantity
                    + guest_item.quantity
                )

                if combined_quantity > 100:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Merging SKU {guest_item.sku} "
                            "would exceed the maximum quantity of 100"
                        ),
                    )

                existing_item.quantity = combined_quantity

            else:
                if guest_item.quantity > 100:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Maximum quantity exceeded for "
                            f"SKU {guest_item.sku}"
                        ),
                    )

                new_item = CartItem(
                    cart_id=user_cart.id,
                    product_id=guest_item.product_id,
                    variant_id=guest_item.variant_id,
                    sku=guest_item.sku,
                    quantity=guest_item.quantity,
                )

                db.add(new_item)
                user_items_by_sku[guest_item.sku] = new_item

        # 11. Convert guest cart.
        guest_cart.status = "converted"
        guest_cart.user_id = user_id

        # 12. Commit both cart changes atomically.
        await db.commit()

        # 13. Return updated authenticated cart.
        return await get_user_cart(db, user_id)

    except Exception:
        await db.rollback()
        raise
