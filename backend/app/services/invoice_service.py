from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app import models


def create_invoice(
    db: Session,
    *,
    order_id: int,
    user: dict,
    payment_method: str
):
    try:
        if payment_method not in ("cash", "card", "transfer"):
            raise HTTPException(400, "Invalid payment method")

        order = db.query(models.Order).filter(
            models.Order.id == order_id,
            models.Order.store_id == user["store_id"],
            models.Order.deleted_at.is_(None)
        ).with_for_update().first()

        if not order:
            raise HTTPException(404, "Order không tồn tại")

        if order.status != models.OrderStatus.confirmed:
            raise HTTPException(400, "Order chưa confirm")

        if order.invoice:
            raise HTTPException(400, "Order đã thanh toán")

        invoice = models.Invoice(
            order_id=order.id,
            store_id=order.store_id,
            total=order.total,
            payment_method=payment_method,
            cashier_id=user["user_id"],
            status="paid",
            paid_at=datetime.utcnow()
        )

        db.add(invoice)

        # 🔥 UPDATE ORDER STATUS
        order.status = models.OrderStatus.paid

        db.commit()
        db.refresh(invoice)

        return invoice

    except Exception:
        db.rollback()
        raise