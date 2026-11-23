from pydantic import BaseModel, Field


class CheckoutRequest(BaseModel):
    shipping_address_id: str | None = Field(
        default=None,
        max_length=100,
    )