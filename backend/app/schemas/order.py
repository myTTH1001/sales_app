from pydantic import BaseModel, Field
from typing import List, Optional
from decimal import Decimal
from datetime import datetime


# =========================================================
# CREATE
# =========================================================
class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)


class OrderCreate(BaseModel):
    # ✅ [SỬA] min_length=1 — không cho phép items rỗng []
    items: List[OrderItemCreate] = Field(..., min_length=1)


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
    payment_method: str = Field(..., pattern="^(cash|card|transfer)$")

# =========================================================
# PAGINATION
# =========================================================
class OrderListResponse(BaseModel):
    total: Optional[int]
    data: List[OrderOut]
    has_more: bool