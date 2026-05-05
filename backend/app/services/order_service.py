from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException
from app.services.invoice_service import create_invoice_internal
from app import models
from app.schemas.order import OrderCreate


# =========================================================
# INTERNAL: load order
# =========================================================
def _get_order_for_update(db: Session, order_id: int, store_id: int):
    order = (
        db.query(models.Order)
        .filter(
            models.Order.id == order_id,
            models.Order.store_id == store_id,
            models.Order.deleted_at.is_(None)
        )
        .with_for_update()
        .first()
    )
    if not order:
        raise HTTPException(404, "Không tìm thấy order")
    return order


def _load_order(db: Session, order_id: int, store_id: int):
    order = (
        db.query(models.Order)
        .filter(
            models.Order.id == order_id,
            models.Order.store_id == store_id,
            models.Order.deleted_at.is_(None)
        )
        .options(
            joinedload(models.Order.items)
            .joinedload(models.OrderItem.product),
            joinedload(models.Order.invoice)
        )
        .first()
    )
    if not order:
        raise HTTPException(404, "Không tìm thấy order")
    return order


# =========================================================
# STOCK HELPERS
# =========================================================
def _lock_stock(db: Session, product_id: int, store_id: int):
    stock = (
        db.query(models.Stock)
        .filter(
            models.Stock.product_id == product_id,
            models.Stock.store_id == store_id
        )
        .with_for_update()
        .first()
    )
    if not stock:
        raise HTTPException(400, f"Sản phẩm {product_id} chưa có tồn kho")
    return stock


def _deduct_stock(db: Session, stock, quantity: int, item_id: int, user: dict, note=None):
    if stock.quantity < quantity:
        raise HTTPException(400, f"Không đủ hàng (còn {stock.quantity})")

    stock.quantity -= quantity

    db.add(models.StockMovement(
        product_id=stock.product_id,
        store_id=stock.store_id,
        quantity=-quantity,
        type=models.StockMovementType.SALE,
        order_item_id=item_id,
        user_id=user["user_id"],
        note=note
    ))


def _return_stock(db: Session, stock, quantity: int, item_id: int, user: dict, note=None):
    stock.quantity += quantity

    db.add(models.StockMovement(
        product_id=stock.product_id,
        store_id=stock.store_id,
        quantity=quantity,
        type=models.StockMovementType.RETURN,
        order_item_id=item_id,
        user_id=user["user_id"],
        note=note
    ))


# =========================================================
# CREATE ORDER
# =========================================================
def create_order(db: Session, user: dict, data: OrderCreate):
    try:
        order = models.Order(
            user_id=user["user_id"],
            store_id=user["store_id"],
            status=models.OrderStatus.draft
        )
        db.add(order)
        db.flush()

        total = Decimal("0")

        for item_data in data.items:
            product = db.query(models.Product).filter(
                models.Product.id == item_data.product_id,
                models.Product.store_id == user["store_id"],
                models.Product.deleted_at.is_(None)
            ).first()

            if not product:
                raise HTTPException(404, f"Sản phẩm {item_data.product_id} không tồn tại")

            db.add(models.OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=item_data.quantity,
                price=product.price
            ))

            total += product.price * item_data.quantity

        order.total = total
        db.commit()

        return _load_order(db, order.id, user["store_id"])

    except Exception:
        db.rollback()
        raise


# =========================================================
# GET ORDER
# =========================================================
def get_order(db: Session, user: dict, order_id: int):
    return _load_order(db, order_id, user["store_id"])


# =========================================================
# CONFIRM ORDER
# =========================================================
def confirm_order(db: Session, user: dict, order_id: int, payment_method: str, note=None):
    try:
        if payment_method not in ("cash", "card", "transfer"):
            raise HTTPException(400, "Phương thức thanh toán không hợp lệ")

        order = _get_order_for_update(db, order_id, user["store_id"])

        if order.status != models.OrderStatus.draft:
            raise HTTPException(400, f"Không thể confirm order ở trạng thái {order.status}")

        if order.invoice:
            raise HTTPException(400, "Order đã có invoice")

        items = db.query(models.OrderItem).filter(
            models.OrderItem.order_id == order.id
        ).all()

        if not items:
            raise HTTPException(400, "Order chưa có sản phẩm")

        # 🔥 chống deadlock
        items = sorted(items, key=lambda x: x.product_id)

        # 🔥 lock stock
        stock_map = {}
        for item in items:
            stock = _lock_stock(db, item.product_id, user["store_id"])
            stock_map[item.product_id] = stock

            if stock.quantity < item.quantity:
                raise HTTPException(
                    400,
                    f"Sản phẩm {item.product_id} chỉ còn {stock.quantity}"
                )

        # 🔥 trừ kho
        for item in items:
            stock = stock_map[item.product_id]
            _deduct_stock(db, stock, item.quantity, item.id, user, note)

        order.status = models.OrderStatus.confirmed

        db.commit()
        return _load_order(db, order.id, user["store_id"])

    except Exception:
        db.rollback()
        raise


# =========================================================
# CANCEL ORDER
# =========================================================
def cancel_order(db: Session, user: dict, order_id: int, reason=None):
    try:
        order = _get_order_for_update(db, order_id, user["store_id"])

        if order.status == models.OrderStatus.cancelled:
            raise HTTPException(400, "Order đã bị huỷ")

        if order.status == models.OrderStatus.paid:
            raise HTTPException(400, "Order đã thanh toán, không thể huỷ")
        
        items = db.query(models.OrderItem).filter(
            models.OrderItem.order_id == order.id
        ).all()

        if order.status == models.OrderStatus.confirmed:
            for item in sorted(items, key=lambda x: x.product_id):
                stock = _lock_stock(db, item.product_id, user["store_id"])
                _return_stock(db, stock, item.quantity, item.id, user, reason)

            invoice = db.query(models.Invoice).filter(
                models.Invoice.order_id == order.id
            ).first()

            if invoice:
                if invoice.status != "paid":
                    raise HTTPException(400, "Invoice không thể huỷ")
                invoice.status = "cancelled"

        order.status = models.OrderStatus.cancelled

        db.commit()
        return _load_order(db, order.id, user["store_id"])

    except Exception:
        db.rollback()
        raise


# =========================================================
# LIST ORDERS
# =========================================================
def list_orders(db: Session, user: dict, limit: int = 10, offset: int = 0):
    query = db.query(models.Order).filter(
        models.Order.store_id == user["store_id"],
        models.Order.deleted_at.is_(None)
    )

    total = query.count() if offset == 0 else None

    orders = query.options(
        joinedload(models.Order.items)
        .joinedload(models.OrderItem.product)
    ).order_by(models.Order.id.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "data": orders,
        "has_more": len(orders) == limit
    }