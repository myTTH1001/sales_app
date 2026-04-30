from pydantic import BaseModel
from decimal import Decimal


from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
from typing import Optional, List


# =========================================================
# 🔹 BASE
# =========================================================
class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    price: Decimal = Field(..., ge=0)
    unit: Optional[str] = Field(default=None, max_length=50)
    image: Optional[str] = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str):
        return v.strip()


# =========================================================
# 🔹 CREATE
# =========================================================
class ProductCreate(ProductBase):
    name: str
    price: Decimal
    unit: str | None = None
    image: str | None = None


# =========================================================
# 🔹 UPDATE
# =========================================================
class ProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    price: Optional[Decimal] = Field(default=None, ge=0)
    unit: Optional[str] = Field(default=None, max_length=50)
    image: Optional[str] = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v):
        if v:
            return v.strip()
        return v


# =========================================================
# 🔹 RESPONSE
# =========================================================
class ProductResponse(BaseModel):
    id: int
    name: str
    price: Decimal
    unit: str | None
    image: str | None

    class Config:
        orm_mode = True


# =========================================================
# 🔹 LIST RESPONSE (pagination)
# =========================================================
class ProductListResponse(BaseModel):
    total: int
    items: List[ProductResponse]


# =========================================================
# 🔹 FILTER / QUERY PARAMS
# =========================================================
class ProductFilter(BaseModel):
    search: Optional[str] = None
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    page: int = 1
    limit: int = 10

    @field_validator("page", "limit")
    @classmethod
    def positive_number(cls, v):
        if v < 1:
            raise ValueError("must be >= 1")
        return v

