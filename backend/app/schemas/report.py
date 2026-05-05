from pydantic import BaseModel
from decimal import Decimal
from datetime import date


# =========================================================
# DAILY
# =========================================================
class RevenueByDay(BaseModel):
    date: date
    revenue: Decimal
    total_orders: int


# =========================================================
# CASHIER
# =========================================================
class RevenueByCashier(BaseModel):
    cashier_id: int
    username: str
    revenue: Decimal
    total_orders: int


# =========================================================
# PRODUCT
# =========================================================
class RevenueByProduct(BaseModel):
    product_id: int
    product_name: str
    total_sold: int
    revenue: Decimal


# =========================================================
# PAGINATION RESPONSE
# =========================================================
class ReportListResponse(BaseModel):
    data: list
    total: int
    has_more: bool