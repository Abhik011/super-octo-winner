
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.order import OrderStatus


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    variant_id: UUID | None
    product_name: str
    sku: str
    variant_name: str | None
    quantity: int
    unit_price: int
    line_total: int


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_number: str
    user_id: UUID
    cart_id: UUID
    status: OrderStatus
    currency: str
    subtotal_amount: int
    discount_amount: int
    shipping_amount: int
    tax_amount: int
    total_amount: int
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemResponse]
