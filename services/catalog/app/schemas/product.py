
import re
import uuid

from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class ProductCreate(BaseModel):
    category_id: uuid.UUID
    name: str = Field(min_length=2, max_length=250)
    slug: str = Field(min_length=2, max_length=280)
    sku: str = Field(min_length=2, max_length=100)
    description: str | None = None

    base_price_minor: int = Field(ge=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)

    is_featured: bool = False

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value):
        value = value.lower().strip()
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value):
            raise ValueError("Invalid product slug")
        return value

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value):
        return value.strip().upper()

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value):
        return value.upper()


class ProductUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=2, max_length=250)
    slug: str | None = Field(default=None, min_length=2, max_length=280)
    description: str | None = None
    base_price_minor: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    is_featured: bool | None = None


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category_id: uuid.UUID
    name: str
    slug: str
    sku: str
    description: str | None
    base_price_minor: int
    currency: str
    status: str
    is_featured: bool
    created_at: datetime
    updated_at: datetime


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    skip: int
    limit: int
