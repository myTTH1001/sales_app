from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.security import require_permission
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["Reports"])


# =========================================================
# DAILY
# =========================================================
@router.get("/daily")
def report_daily(
    start_date: datetime,
    end_date: datetime,
    db: Session = Depends(get_db),
    user=Depends(require_permission("report:view"))
):
    return report_service.revenue_by_day(db, user, start_date, end_date)


# =========================================================
# CASHIER
# =========================================================
@router.get("/cashier")
def report_cashier(
    start_date: datetime,
    end_date: datetime,
    db: Session = Depends(get_db),
    user=Depends(require_permission("report:view"))
):
    return report_service.revenue_by_cashier(db, user, start_date, end_date)


# =========================================================
# PRODUCT (PAGINATION)
# =========================================================
@router.get("/product")
def report_product(
    start_date: datetime,
    end_date: datetime,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(require_permission("report:view"))
):
    return report_service.revenue_by_product(
        db, user, start_date, end_date, limit, offset
    )