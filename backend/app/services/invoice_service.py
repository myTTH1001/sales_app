from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
from app.services.stock_service import apply_stock_movement
from app import models


# =========================================================
# GET ONE INVOICE
# =========================================================
def get_invoice(db: Session, *, invoice_id: int, user: dict):
    invoice = db.query(models.Invoice).filter(
        models.Invoice.id == invoice_id,
        models.Invoice.store_id == user["store_id"]
    ).first()

    if not invoice:
        raise HTTPException(404, "Invoice không tồn tại")

    return invoice


# =========================================================
# LIST INVOICES
# =========================================================
def list_invoices(
    db: Session,
    *,
    user: dict,
    status: str | None = None,
    cashier_id: int | None = None,
    limit: int = 10,
    offset: int = 0,
):
    query = db.query(models.Invoice).filter(
        models.Invoice.store_id == user["store_id"]
    )

    if status:
        query = query.filter(models.Invoice.status == status)

    if cashier_id:
        query = query.filter(models.Invoice.cashier_id == cashier_id)

    total = query.with_entities(func.count()).scalar()

    data = (
        query.order_by(models.Invoice.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "data": data,
        "has_more": (offset + len(data)) < total,
    }


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
            paid_at=datetime.now(timezone.utc)
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