
import uuid

from pydantic import BaseModel, ConfigDict, Field


class VariantCreate(BaseModel):
    sku: str = Field(min_length=2, max_length=100)
    attributes: dict[str, str] = Field(default_factory=dict)
    price_minor: int | None = Field(default=None, ge=0)
    is_active: bool = True


class VariantUpdate(BaseModel):
    sku: str | None = Field(default=None, min_length=2, max_length=100)
    attributes: dict[str, str] | None = None
    price_minor: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class VariantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    sku: str
    attributes: dict[str, str]
    price_minor: int | None
    is_active: bool
