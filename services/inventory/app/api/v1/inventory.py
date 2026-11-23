
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.inventory_item import InventoryItem
from app.schemas.inventory import (
    InventoryCreate,
    InventoryAdjust,
    InventoryResponse,
)
from app.services.inventory_service import create_stock, adjust_stock

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.post("/", response_model=InventoryResponse, status_code=201)
async def create_inventory(
    payload: InventoryCreate,
    db: AsyncSession = Depends(get_db),
):
    return await create_stock(
        db=db,
        catalog_product_id=payload.catalog_product_id,
        catalog_variant_id=payload.catalog_variant_id,
        sku=payload.sku,
        quantity=payload.quantity_on_hand,
    )


@router.get("/", response_model=list[InventoryResponse])
async def list_inventory(
    db: AsyncSession = Depends(get_db),
):
    result = await db.scalars(
        select(InventoryItem).order_by(InventoryItem.sku)
    )
    return result.all()


@router.get("/{item_id}", response_model=InventoryResponse)
async def get_inventory(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(InventoryItem, item_id)

    if not item:
        raise HTTPException(404, "Inventory item not found")

    return item


@router.post("/{item_id}/adjust", response_model=InventoryResponse)
async def adjust_inventory(
    item_id: UUID,
    payload: InventoryAdjust,
    db: AsyncSession = Depends(get_db),
):
    return await adjust_stock(
        db=db,
        item_id=item_id,
        quantity_change=payload.quantity_change,
    )

@router.get("/by-sku/{sku}", response_model=InventoryResponse)
async def get_inventory_by_sku(
    sku: str,
    db: AsyncSession = Depends(get_db),
):
    item = await db.scalar(
        select(InventoryItem).where(
            InventoryItem.sku == sku.strip().upper()
        )
    )

    if not item:
        raise HTTPException(404, "Inventory item not found")

    return item