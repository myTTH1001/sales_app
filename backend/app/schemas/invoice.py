from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime


class InvoiceOut(BaseModel):
    id: int
    order_id: int
    total: Decimal
    status: str
    payment_method: str
    created_at: datetime

    class Config:
        from_attributes = True


class InvoiceCreate(BaseModel):
    payment_method: str = Field(..., pattern="^(cash|card|transfer)$")