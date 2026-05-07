from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException

from app import models
from app.schemas.order import OrderCreate
from app.services.stock_service import apply_stock_movement, get_stock_for_update


# =========================================================
# INTERNAL HELPERS
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
# CREATE ORDER (DRAFT)
# =========================================================
def create_order(db: Session, user: dict, data: OrderCreate):
    try:
        order = models.Order(
            user_id=user["user_id"],
            store_id=user["store_id"],
            status=models.OrderStatus.draft,
            created_at=datetime.now(timezone.utc)
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
# CONFIRM ORDER (TRỪ KHO)
# =========================================================
def confirm_order(db: Session, user: dict, order_id: int, payment_method: str, note=None):
    try:
        order = _get_order_for_update(db, order_id, user["store_id"])

        # ✅ Idempotent
        if order.status == models.OrderStatus.confirmed:
            return _load_order(db, order.id, user["store_id"])

        if order.status != models.OrderStatus.draft:
            raise HTTPException(400, f"Không thể confirm order ở trạng thái {order.status}")

        if order.invoice:
            raise HTTPException(400, "Order đã có invoice")

        # ✅ [FIX #6] Query items 1 lần duy nhất, dùng chung cho validate + apply movement
        # _load_order cuối cùng sẽ joinedload lại sau commit — không cần query thêm
        items = (
            db.query(models.OrderItem)
            .filter(models.OrderItem.order_id == order.id)
            .all()
        )

        if not items:
            raise HTTPException(400, "Order chưa có sản phẩm")

        # 🔥 chống deadlock — sort theo product_id trước khi lock
        items = sorted(items, key=lambda x: x.product_id)

        # 🔥 lock stock + validate tồn kho
        stock_map = {}
        for item in items:
            stock = get_stock_for_update(db, item.product_id, user["store_id"])
            stock_map[item.product_id] = stock

            if stock.quantity < item.quantity:
                raise HTTPException(
                    400,
                    f"Sản phẩm {item.product_id} chỉ còn {stock.quantity}"
                )

        # 🔥 trừ kho — dùng lại items đã sort, không query lại
        for item in items:
            apply_stock_movement(
                db,
                product_id=item.product_id,
                store_id=user["store_id"],
                quantity=-item.quantity,
                movement_type=models.StockMovementType.SALE,
                user_id=user["user_id"],
                order_item_id=item.id,
                note=note or f"Confirm order #{order.id}"
            )

        order.status = models.OrderStatus.confirmed

        db.commit()
        # _load_order thực hiện joinedload — đây là lần duy nhất load đầy đủ quan hệ
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

        # ✅ Idempotent
        if order.status == models.OrderStatus.cancelled:
            return _load_order(db, order.id, user["store_id"])

        if order.status == models.OrderStatus.paid:
            raise HTTPException(400, "Order đã thanh toán, không thể huỷ")

        # ❌ Không cho huỷ nếu đã có invoice
        if order.invoice:
            raise HTTPException(400, "Order đã có invoice")

        # ✅ [FIX #6] Query items 1 lần, dùng chung cho cả nhánh hoàn kho
        # _load_order cuối sẽ joinedload lại — không cần query thêm
        items = (
            db.query(models.OrderItem)
            .filter(models.OrderItem.order_id == order.id)
            .all()
        )

        # 🔥 nếu đã confirm → hoàn kho
        if order.status == models.OrderStatus.confirmed:
            items = sorted(items, key=lambda x: x.product_id)

            for item in items:
                apply_stock_movement(
                    db,
                    product_id=item.product_id,
                    store_id=user["store_id"],
                    quantity=item.quantity,
                    movement_type=models.StockMovementType.RETURN,
                    user_id=user["user_id"],
                    order_item_id=item.id,
                    note=reason or f"Cancel order #{order.id}"
                )

        order.status = models.OrderStatus.cancelled

        db.commit()
        return _load_order(db, order.id, user["store_id"])

    except Exception:
        db.rollback()
        raise


# =========================================================
# LIST ORDERS (PAGINATION)
# =========================================================
def list_orders(db: Session, user: dict, limit: int = 10, offset: int = 0):
    query = db.query(models.Order).filter(
        models.Order.store_id == user["store_id"],
        models.Order.deleted_at.is_(None)
    )

    # ✅ [FIX #5] Luôn đếm total — không phụ thuộc offset
    # Dùng query tách biệt để tránh conflict với options/order_by của query chính
    total = db.query(func.count(models.Order.id)).filter(
        models.Order.store_id == user["store_id"],
        models.Order.deleted_at.is_(None)
    ).scalar()

    orders = query.options(
        joinedload(models.Order.items)
        .joinedload(models.OrderItem.product)
    ).order_by(models.Order.id.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "data": orders,
        "has_more": len(orders) == limit
    }