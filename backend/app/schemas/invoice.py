from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime
from typing import Optional


class InvoiceOut(BaseModel):
    id: int
    order_id: int
    total: Decimal
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class InvoiceDetail(BaseModel):
    id: int
    order_id: int
    total: Decimal
    status: str
    created_at: datetime

    class Config:
        from_attributes = True