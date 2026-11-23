from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CartItemCreate(BaseModel):
    product_id: UUID
    variant_id: UUID | None = None
    sku: str = Field(min_length=1, max_length=100)
    quantity: int = Field(default=1, ge=1, le=100)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1, le=100)


class CartMergeRequest(BaseModel):
    guest_id: UUID


class CartItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    variant_id: UUID | None
    sku: str
    quantity: int


class CartResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None
    guest_id: UUID | None
    status: str
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
    items: list[CartItemResponse] = Field(default_factory=list)