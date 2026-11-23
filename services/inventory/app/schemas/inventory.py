
import uuid

from pydantic import BaseModel, Field, ConfigDict


class InventoryCreate(BaseModel):
    catalog_product_id: uuid.UUID
    catalog_variant_id: uuid.UUID | None = None
    sku: str = Field(min_length=2, max_length=100)
    quantity_on_hand: int = Field(ge=0)


class InventoryAdjust(BaseModel):
    quantity_change: int
    reason: str = Field(min_length=3, max_length=250)


class InventoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    catalog_product_id: uuid.UUID
    catalog_variant_id: uuid.UUID | None
    sku: str
    quantity_on_hand: int
    quantity_reserved: int
    available_quantity: int
