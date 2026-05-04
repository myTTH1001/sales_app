from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import require_permission

from app.schemas.order import (
    OrderCreate,
    OrderOut,
    OrderCancel,
    OrderConfirm,
    OrderListResponse
)

from app.services import order_service

router = APIRouter(prefix="/orders", tags=["Orders"])


# =========================================================
# LIST ORDERS (PAGINATION)
# =========================================================
@router.get("", response_model=OrderListResponse)
def list_orders(
    # ✅ [SỬA] giới hạn limit/offset tránh client query quá lớn
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(require_permission("order:view"))
):
    return order_service.list_orders(db, user, limit, offset)


# =========================================================
# CREATE ORDER
# =========================================================
@router.post("", response_model=OrderOut)
def create_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permission("order:create"))
):
    return order_service.create_order(db, user, data)


# =========================================================
# GET ORDER DETAIL
# =========================================================
@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permission("order:view"))
):
    return order_service.get_order(db, user, order_id)


# =========================================================
# CONFIRM ORDER
# =========================================================
@router.post("/{order_id}/confirm", response_model=OrderOut)
def confirm_order(
    order_id: int,
    data: OrderConfirm,
    db: Session = Depends(get_db),
    user=Depends(require_permission("order:confirm"))
):
    # ✅ [SỬA] truyền note vào service thay vì bỏ qua
    return order_service.confirm_order(db, user, order_id, 
        payment_method=data.payment_method, note=data.note)


# =========================================================
# CANCEL ORDER
# =========================================================
@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel_order(
    order_id: int,
    data: OrderCancel,
    db: Session = Depends(get_db),
    user=Depends(require_permission("order:cancel"))
):
    # ✅ [SỬA] truyền reason vào service thay vì bỏ qua
    return order_service.cancel_order(db, user, order_id, reason=data.reason)