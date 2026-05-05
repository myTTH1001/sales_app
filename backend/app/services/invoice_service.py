from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app import models


# =========================================================
# CREATE INVOICE
# =========================================================
def create_invoice(
    db: Session,
    *,
    order_id: int,
    user: dict,
    payment_method: str
):
    try:
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
            return order.invoice  # idempotent

        invoice = models.Invoice(
            order_id=order.id,
            store_id=order.store_id,
            total=order.total,
            status="paid",
            payment_method=payment_method,
            cashier_id=user["user_id"],
            paid_at=datetime.utcnow()
        )

        db.add(invoice)

        # 🔥 update order
        order.status = models.OrderStatus.paid

        db.commit()
        db.refresh(invoice)

        return invoice

    except Exception:
        db.rollback()
        raise

# =========================================================
# CANCEL INVOICE
# =========================================================
def cancel_invoice(
    db: Session,
    *,
    invoice_id: int,
    user: dict
):
    try:
        invoice = db.query(models.Invoice).filter(
            models.Invoice.id == invoice_id,
            models.Invoice.store_id == user["store_id"]
        ).with_for_update().first()

        if not invoice:
            raise HTTPException(404, "Invoice không tồn tại")

        order = db.query(models.Order).filter(
            models.Order.id == invoice.order_id
        ).with_for_update().first()

        if not order:
            raise HTTPException(404, "Order không tồn tại")

        if invoice.status == "cancelled":
            return invoice  # idempotent

        # 🔥 hoàn kho nếu đã trừ
        if order.status == models.OrderStatus.paid:
            items = db.query(models.OrderItem).filter(
                models.OrderItem.order_id == order.id
            ).all()

            for item in items:
                from app.services.stock_service import apply_stock_movement

                apply_stock_movement(
                    db,
                    product_id=item.product_id,
                    store_id=order.store_id,
                    quantity=item.quantity,
                    movement_type=models.StockMovementType.RETURN,
                    user_id=user["user_id"],
                    order_item_id=item.id,
                    note=f"Cancel invoice #{invoice.id}"
                )

        invoice.status = "cancelled"
        order.status = models.OrderStatus.cancelled

        db.commit()
        return invoice

    except Exception:
        db.rollback()
        raise