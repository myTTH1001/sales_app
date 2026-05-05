from enum import Enum

from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime


class InvoiceOut(BaseModel):
    id: int
    order_id: int
    total: Decimal
    status: str
    payment_method: str
    cashier_id: int | None
    paid_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class PaymentMethod(str, Enum):
    cash = "cash"
    card = "card"
    transfer = "transfer"

class InvoiceCreate(BaseModel):
    payment_method: PaymentMethod