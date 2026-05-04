from datetime import datetime

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from fastapi import HTTPException
from decimal import Decimal
from app import models
from app.schemas.order import OrderCreate


# =========================================================
# GET STOCK
# =========================================================
def get_stock(db: Session, product_id: int, store_id: int) -> int:
    total = db.query(func.sum(models.StockMovement.quantity)).filter(
        models.StockMovement.product_id == product_id,
        models.StockMovement.store_id == store_id,
        models.StockMovement.status == "done"  # ✅ [SỬA] chỉ tính movement hợp lệ
    ).scalar()
    return total or 0


# =========================================================
# HELPER: load order với items
# =========================================================
def _load_order_with_items(db: Session, order_id: int, store_id: int):  # ✅ [SỬA] thêm store_id
    return db.query(models.Order).filter(
        models.Order.id == order_id,
        models.Order.store_id == store_id  # ✅ [SỬA] luôn filter store tránh data leak
    ).options(
        joinedload(models.Order.items)
    ).first()


# =========================================================
# CREATE ORDER
# =========================================================
def create_order(db: Session, user: dict, data: OrderCreate):
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
        ).with_for_update().first()

        if not product:
            raise HTTPException(404, f"Sản phẩm {item_data.product_id} không tồn tại")

        stock = get_stock(db, product.id, user["store_id"])
        if stock < item_data.quantity:
            raise HTTPException(400, f"Tồn kho không đủ: còn {stock}")

        db.add(models.OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=item_data.quantity,
            price=product.price
        ))
        total += product.price * item_data.quantity

    order.total = total
    db.commit()
    return _load_order_with_items(db, order.id, user["store_id"])  # ✅ [SỬA] truyền store_id


# =========================================================
# GET ORDER DETAIL
# =========================================================
def get_order(db: Session, user: dict, order_id: int):
    order = db.query(models.Order).filter(
        models.Order.id == order_id,
        models.Order.store_id == user["store_id"]
    ).options(
        joinedload(models.Order.items).joinedload(models.OrderItem.product)
    ).first()

    if not order:
        raise HTTPException(404, "Không tìm thấy order")

    return order


# =========================================================
# CONFIRM ORDER
# =========================================================
def confirm_order(db: Session, user: dict, order_id: int, payment_method: str, note: str = None):
    order = db.query(models.Order).filter(
        models.Order.id == order_id,
        models.Order.store_id == user["store_id"]
    ).with_for_update().first()

    if not order:
        raise HTTPException(404, "Không tìm thấy order")

    if order.status != models.OrderStatus.draft:
        raise HTTPException(400, f"Không thể confirm order ở trạng thái {order.status}")

    items = db.query(models.OrderItem).filter(
        models.OrderItem.order_id == order.id
    ).all()

    if not items:
        raise HTTPException(400, "Order chưa có sản phẩm")

    for item in items:
        stock = get_stock(db, item.product_id, user["store_id"])
        if stock < item.quantity:
            raise HTTPException(400, f"Hết hàng sản phẩm {item.product_id}: còn {stock}")

    for item in items:
        db.add(models.StockMovement(
            product_id=item.product_id,
            store_id=user["store_id"],
            quantity=-item.quantity,
            type=models.StockMovementType.SALE,
            order_item_id=item.id,
            user_id=user["user_id"],
            note=note
        ))

    db.add(models.Invoice(
        order_id=order.id,
        store_id=user["store_id"],
        total=order.total,
        status="paid",
        payment_method = payment_method,
        cashier_id=user["user_id"],
        paid_at=datetime.utcnow()
    ))

    order.status = models.OrderStatus.confirmed
    db.commit()
    return _load_order_with_items(db, order_id, user["store_id"])  # ✅ [SỬA] truyền store_id


# =========================================================
# CANCEL ORDER
# =========================================================
def cancel_order(db: Session, user: dict, order_id: int, reason: str = None):
    order = db.query(models.Order).filter(
        models.Order.id == order_id,
        models.Order.store_id == user["store_id"]
    ).with_for_update().first()

    if not order:
        raise HTTPException(404, "Không tìm thấy order")

    if order.status == models.OrderStatus.cancelled:
        raise HTTPException(400, "Order đã bị huỷ")

    if order.status not in (models.OrderStatus.draft, models.OrderStatus.confirmed):
        raise HTTPException(400, f"Không thể huỷ order ở trạng thái {order.status}")

    items = db.query(models.OrderItem).filter(
        models.OrderItem.order_id == order.id
    ).all()

    if order.status == models.OrderStatus.confirmed:
        for item in items:
            db.add(models.StockMovement(
                product_id=item.product_id,
                store_id=user["store_id"],
                quantity=item.quantity,
                type=models.StockMovementType.RETURN,
                order_item_id=item.id,
                user_id=user["user_id"],
                note=reason
            ))
        invoice = db.query(models.Invoice).filter(
            models.Invoice.order_id == order.id
        ).first()
        if invoice:
            invoice.status = "cancelled"

    order.status = models.OrderStatus.cancelled
    db.commit()
    return _load_order_with_items(db, order_id, user["store_id"])  # ✅ [SỬA] truyền store_id


# =========================================================
# LIST ORDERS (PAGINATION)
# =========================================================
def list_orders(db: Session, user: dict, limit: int = 10, offset: int = 0):
    query = db.query(models.Order).filter(
        models.Order.store_id == user["store_id"]
    )

    total = query.count()

    orders = query.options(
        joinedload(models.Order.items).joinedload(models.OrderItem.product)
    ).order_by(models.Order.id.desc()).offset(offset).limit(limit).all()

    return {"total": total, "data": orders}