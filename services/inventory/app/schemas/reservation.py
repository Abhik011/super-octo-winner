
import uuid

from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class ReservationLineCreate(BaseModel):
    inventory_item_id: uuid.UUID
    quantity: int = Field(gt=0)


class ReservationCreate(BaseModel):
    order_reference: str = Field(min_length=1, max_length=100)
    items: list[ReservationLineCreate] = Field(min_length=1, max_length=50)


class ReservationItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    inventory_item_id: uuid.UUID
    quantity: int


class ReservationResponse(BaseModel):
    id: uuid.UUID
    order_reference: str
    status: str
    expires_at: datetime
    items: list[ReservationItemResponse]
