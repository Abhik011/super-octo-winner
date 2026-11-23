import httpx

from fastapi import HTTPException
from app.core.config import settings
from urllib.parse import quote

class CheckoutClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def get_cart(self, access_token: str):
        response = await self.client.get(
            f"{settings.CART_SERVICE_URL}/api/v1/carts/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail="Unable to retrieve customer cart",
            )

        return response.json()

    async def get_product(self, product_id: str):
        response = await self.client.get(
            f"{settings.CATALOG_SERVICE_URL}/api/v1/products/{product_id}"
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=409,
                detail=f"Product {product_id} is unavailable",
            )

        return response.json()

    async def get_variants(self, product_id: str):
        response = await self.client.get(
            f"{settings.CATALOG_SERVICE_URL}/api/v1/products/{product_id}/variants"
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail="Unable to retrieve product variants",
            )

        return response.json()

    async def release_stock(self, reservation_id: str):
        response = await self.client.post(
            f"{settings.INVENTORY_SERVICE_URL}/api/v1/reservations/{reservation_id}/release"
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail="Failed to release inventory reservation",
            )

        return response.json()    

    async def confirm_stock(self, reservation_id: str):
        response = await self.client.post(
            f"{settings.INVENTORY_SERVICE_URL}/api/v1/reservations/{reservation_id}/confirm"
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail="Failed to confirm inventory reservation",
            )

        return response.json()

    
    async def get_inventory_by_sku(self, sku: str):
        response = await self.client.get(
            f"{settings.INVENTORY_SERVICE_URL}/api/v1/inventory/by-sku/{quote(sku, safe='')}"
        )

        if response.status_code == 404:
            raise HTTPException(
                status_code=409,
                detail=f"Inventory unavailable for SKU {sku}",
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail="Unable to retrieve inventory",
            )

        return response.json()

    async def reserve_stock(
        self,
        order_reference: str,
        inventory_items: list[dict],
        idempotency_key: str,
    ):
        response = await self.client.post(
            f"{settings.INVENTORY_SERVICE_URL}/api/v1/reservations/",
            headers={"Idempotency-Key": idempotency_key},
            json={
                "order_reference": order_reference,
                "items": inventory_items,
            },
        )

        if response.status_code not in (200, 201):
            raise HTTPException(
                status_code=409,
                detail="Unable to reserve inventory",
            )

        return response.json()