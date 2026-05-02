from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# =========================================================
# CREATE
# =========================================================
class StockMovementCreate(BaseModel):
    product_id: int
    quantity: int
    type: str  # IMPORT, SALE, RETURN, ADJUST
    note: Optional[str] = None


# =========================================================
# RESPONSE
# =========================================================
class StockMovementOut(BaseModel):
    id: int
    product_id: int
    quantity: int
    type: str
    created_at: datetime

    class Config:
        from_attributes = True


# =========================================================
# SUMMARY (TỒN KHO)
# =========================================================
class StockSummary(BaseModel):
    product_id: int
    stock: int