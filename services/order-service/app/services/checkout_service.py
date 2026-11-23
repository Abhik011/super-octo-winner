
from uuid import UUID

from fastapi import HTTPException

from app.services.checkout_client import CheckoutClient


class CheckoutService:
    def __init__(self, client: CheckoutClient):
        self.client = client

    async def validate_cart(self, access_token: str, user_id: UUID) -> dict:
        cart = await self.client.get_cart(access_token)

        if str(cart.get("user_id")) != str(user_id):
            raise HTTPException(
                status_code=403,
                detail="Cart does not belong to the authenticated customer",
            )

        if cart.get("status") != "active":
            raise HTTPException(
                status_code=409,
                detail="Cart is not active",
            )

        cart_items = cart.get("items", [])

        if not cart_items:
            raise HTTPException(
                status_code=400,
                detail="Cannot checkout an empty cart",
            )

        order_items = []
        inventory_quantities = {}
        currency = None
        subtotal_minor = 0

        for cart_item in cart_items:
            product_id = cart_item.get("product_id")
            variant_id = cart_item.get("variant_id")
            cart_sku = cart_item.get("sku")
            quantity = cart_item.get("quantity")

            if (
                not isinstance(quantity, int)
                or isinstance(quantity, bool)
                or quantity <= 0
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid cart item quantity",
                )

            if not product_id or not cart_sku:
                raise HTTPException(
                    status_code=409,
                    detail="Cart item is missing product or SKU information",
                )

            product = await self.client.get_product(product_id)

            if product.get("status") != "active":
                raise HTTPException(
                    status_code=409,
                    detail=f"Product {product_id} is not available",
                )

            selected_variant = None

            if variant_id:
                variants = await self.client.get_variants(product_id)

                selected_variant = next(
                    (
                        variant
                        for variant in variants
                        if str(variant.get("id")) == str(variant_id)
                    ),
                    None,
                )

                if (
                    selected_variant is None
                    or not selected_variant.get("is_active")
                    or str(selected_variant.get("product_id")) != str(product_id)
                ):
                    raise HTTPException(
                        status_code=409,
                        detail="Selected product variant is unavailable",
                    )

                if selected_variant.get("sku") != cart_sku:
                    raise HTTPException(
                        status_code=409,
                        detail="Cart SKU does not match the selected variant",
                    )

                variant_price = selected_variant.get("price_minor")
                unit_price = (
                    variant_price
                    if variant_price is not None
                    else product.get("base_price_minor")
                )

                attributes = selected_variant.get("attributes") or {}

                variant_name = (
                    ", ".join(
                        f"{key}: {value}"
                        for key, value in sorted(attributes.items())
                    )
                    if isinstance(attributes, dict)
                    else None
                )

            else:
                if product.get("sku") != cart_sku:
                    raise HTTPException(
                        status_code=409,
                        detail="Cart SKU does not match the product SKU",
                    )

                unit_price = product.get("base_price_minor")
                variant_name = None

            if (
                not isinstance(unit_price, int)
                or isinstance(unit_price, bool)
                or unit_price < 0
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Product has an invalid price",
                )

            item_currency = product.get("currency")

            if not isinstance(item_currency, str) or len(item_currency) != 3:
                raise HTTPException(
                    status_code=409,
                    detail="Product has an invalid currency",
                )

            item_currency = item_currency.upper()

            if currency is None:
                currency = item_currency
            elif currency != item_currency:
                raise HTTPException(
                    status_code=409,
                    detail="Cart contains products with different currencies",
                )

            inventory = await self.client.get_inventory_by_sku(cart_sku)

            if (
                str(inventory.get("catalog_product_id")) != str(product_id)
                or str(inventory.get("sku")) != str(cart_sku)
                or (
                    str(inventory.get("catalog_variant_id"))
                    != str(variant_id)
                    if variant_id
                    else inventory.get("catalog_variant_id") is not None
                )
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Inventory record does not match the catalog item",
                )

            available_quantity = inventory.get("available_quantity")

            if (
                not isinstance(available_quantity, int)
                or isinstance(available_quantity, bool)
                or available_quantity < quantity
            ):
                raise HTTPException(
                    status_code=409,
                    detail=f"Insufficient stock for SKU {cart_sku}",
                )

            line_total = unit_price * quantity
            subtotal_minor += line_total

            inventory_id = str(inventory["id"])

            inventory_quantities[inventory_id] = (
                inventory_quantities.get(inventory_id, 0) + quantity
            )

            order_items.append(
                {
                    "product_id": str(product_id),
                    "variant_id": str(variant_id) if variant_id else None,
                    "product_name": product["name"],
                    "sku": cart_sku,
                    "variant_name": variant_name,
                    "quantity": quantity,
                    "unit_price_minor": unit_price,
                    "line_total_minor": line_total,
                }
            )

        inventory_items = [
            {
                "inventory_item_id": inventory_id,
                "quantity": quantity,
            }
            for inventory_id, quantity in inventory_quantities.items()
        ]

        return {
            "user_id": str(user_id),
            "cart_id": str(cart["id"]),
            "currency": currency,
            "items": order_items,
            "inventory_items": inventory_items,
            "subtotal_minor": subtotal_minor,
        }
