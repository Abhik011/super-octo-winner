
import uuid

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ProductImageCreate(BaseModel):
    image_url: HttpUrl
    alt_text: str | None = Field(default=None, max_length=250)
    display_order: int = Field(default=0, ge=0)


class ProductImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    image_url: str
    alt_text: str | None
    display_order: int
