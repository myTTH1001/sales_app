from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
from decimal import Decimal
from sqlalchemy.orm import joinedload
from app import models
from app.schemas.order import OrderCreate


# =========================================================
# GET STOCK
# =========================================================
def get_stock(db: Session, product_id: int, store_id: int) -> int:
    total = db.query(func.sum(models.StockMovement.quantity)).filter(
        models.StockMovement.product_id == product_id,
        models.StockMovement.store_id == store_id
    ).scalar()

    return total or 0


# =========================================================
# CREATE ORDER WITH ITEMS (CART)
# =========================================================
def create_order(db: Session, user: dict, data: OrderCreate):
    try:
        with db.begin():

            order = models.Order(
                user_id=user["user_id"],
                store_id=user["store_id"],
                status=models.OrderStatus.draft
            )
            db.add(order)
            db.flush()  # 👈 lấy order.id

            total = Decimal("0")

            for item_data in data.items:

                product = db.query(models.Product).filter(
                    models.Product.id == item_data.product_id,
                    models.Product.store_id == user["store_id"],
                    models.Product.deleted_at.is_(None)
                ).first()

                if not product:
                    raise HTTPException(404, f"Sản phẩm {item_data.product_id} không tồn tại")

                # 🔥 CHECK STOCK
                stock = get_stock(db, product.id, user["store_id"])
                if stock < item_data.quantity:
                    raise HTTPException(400, f"Tồn kho không đủ ({stock})")

                item = models.OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=item_data.quantity,
                    price=product.price
                )
                db.add(item)

                total += product.price * item_data.quantity

            order.total = total

        db.refresh(order)
        return order

    except Exception:
        db.rollback()
        raise


# =========================================================
# GET ORDER DETAIL
# =========================================================
def get_order(db: Session, user: dict, order_id: int):
    order = db.query(models.Order).filter(
        models.Order.id == order_id,
        models.Order.store_id == user["store_id"]
    ).first()

    if not order:
        raise HTTPException(404, "Không tìm thấy order")

    return order


# =========================================================
# CONFIRM ORDER
# =========================================================
def confirm_order(db: Session, user: dict, order_id: int):
    try:
        with db.begin():

            order = db.query(models.Order).filter(
                models.Order.id == order_id,
                models.Order.store_id == user["store_id"]
            ).with_for_update().first()

            if not order:
                raise HTTPException(400, "Order không hợp lệ")

            if not order.items:
                raise HTTPException(400, "Order chưa có sản phẩm")

            # 🔥 CHECK STOCK LẦN 2
            for item in order.items:
                stock = get_stock(db, item.product_id, user["store_id"])
                if stock < item.quantity:
                    raise HTTPException(400, f"Hết hàng product {item.product_id}")

            # 👉 trừ kho
            for item in order.items:
                db.add(models.StockMovement(
                    product_id=item.product_id,
                    store_id=user["store_id"],
                    quantity=-item.quantity,
                    type=models.StockMovementType.SALE,
                    order_item_id=item.id,
                    user_id=user["user_id"]
                ))

            # 👉 tạo invoice
            db.add(models.Invoice(
                order_id=order.id,
                store_id=user["store_id"],
                total=order.total,
                status="paid"
            ))

            order.status = models.OrderStatus.confirmed

        db.refresh(order)
        return order

    except Exception:
        db.rollback()
        raise


# =========================================================
# CANCEL ORDER
# =========================================================
def cancel_order(db: Session, user: dict, order_id: int):
    try:
        with db.begin():

            order = db.query(models.Order).filter(
                models.Order.id == order_id,
                models.Order.store_id == user["store_id"]
            ).first()

            if not order:
                raise HTTPException(404, "Không tìm thấy order")

            if order.status == models.OrderStatus.cancelled:
                raise HTTPException(400, "Order đã bị huỷ")

            if order.status != models.OrderStatus.confirmed:
                raise HTTPException(400, "Chỉ huỷ được order đã confirm")
            # 👉 hoàn kho
            for item in order.items:
                db.add(models.StockMovement(
                    product_id=item.product_id,
                    store_id=user["store_id"],
                    quantity=item.quantity,
                    type=models.StockMovementType.RETURN,
                    order_item_id=item.id,
                    user_id=user["user_id"]
                ))

            order.status = models.OrderStatus.cancelled

        db.refresh(order)
        return order

    except Exception:
        db.rollback()
        raise


# =========================================================
# LIST ORDERS (PAGINATION)
# =========================================================
def list_orders(
    db: Session,
    user: dict,
    limit: int = 10,
    offset: int = 0
):
    query = db.query(models.Order).filter(
        models.Order.store_id == user["store_id"]
    )

    # 👉 total trước
    total = query.count()

    # 👉 lấy data + eager load items
    orders = query.options(
        joinedload(models.Order.items)
    ).order_by(models.Order.id.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "data": orders
    }