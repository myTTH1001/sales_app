from pydantic import BaseModel, Field
from typing import List, Optional
from decimal import Decimal
from datetime import datetime


# =========================================================
# CREATE
# =========================================================
class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)  # 🔥 bắt buộc > 0


class OrderCreate(BaseModel):
    items: List[OrderItemCreate]


# =========================================================
# RESPONSE
# =========================================================
class OrderItemOut(BaseModel):
    product_id: int
    quantity: int
    price: Decimal

    class Config:
        from_attributes = True


class OrderOut(BaseModel):
    id: int
    total: Decimal
    status: str
    created_at: datetime
    items: List[OrderItemOut]

    class Config:
        from_attributes = True


# =========================================================
# ACTION
# =========================================================
class OrderCancel(BaseModel):
    reason: Optional[str] = None


class OrderConfirm(BaseModel):
    note: Optional[str] = None

# =========================================================
# PAGINATION
# =========================================================
from typing import Generic, TypeVar

T = TypeVar("T")


class OrderListResponse(BaseModel):
    total: int
    data: List[OrderOut]