from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import require_permission

from app.schemas.order import (
    OrderCreate,
    OrderOut,
    OrderCancel,
    OrderConfirm
)

from app.services import order_service

router = APIRouter(prefix="/orders", tags=["Orders"])


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
    return order_service.confirm_order(db, user, order_id)


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
    return order_service.cancel_order(db, user, order_id)