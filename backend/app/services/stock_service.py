from sqlalchemy.orm import Session
from fastapi import HTTPException
from app import models
import uuid


# =========================================================
# 🔹 LOCK STOCK ROW
# =========================================================
def get_stock_for_update(db: Session, product_id: int, store_id: int):
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
        stock = models.Stock(
            product_id=product_id,
            store_id=store_id,
            quantity=0
        )
        db.add(stock)
        db.flush()

    return stock


# =========================================================
# 🔹 CORE MOVEMENT
# =========================================================
def apply_stock_movement(
    db: Session,
    *,
    product_id: int,
    store_id: int,
    quantity: int,
    movement_type: models.StockMovementType,
    user_id: int = None,
    note: str = None,
    order_item_id: int = None,
    transfer_ref: str = None
):
    stock = get_stock_for_update(db, product_id, store_id)

    new_quantity = stock.quantity + quantity

    if new_quantity < 0:
        raise HTTPException(400, "Không đủ tồn kho")

    stock.quantity = new_quantity

    movement = models.StockMovement(
        product_id=product_id,
        store_id=store_id,
        quantity=quantity,
        type=movement_type,
        user_id=user_id,
        note=note,
        order_item_id=order_item_id,
        transfer_ref=transfer_ref
    )

    db.add(movement)
    return movement


# =========================================================
# 🔹 IMPORT
# =========================================================
def import_stock(
    db: Session,
    *,
    product_id: int,
    store_id: int,
    quantity: int,
    user_id: int,
    note: str = None
):
    if quantity <= 0:
        raise HTTPException(400, "Quantity phải > 0")

    return apply_stock_movement(
        db,
        product_id=product_id,
        store_id=store_id,
        quantity=quantity,
        movement_type=models.StockMovementType.IMPORT,
        user_id=user_id,
        note=note or "Nhập kho"
    )


# =========================================================
# 🔹 ORDER FLOW
# =========================================================
def deduct_stock_for_order(db: Session, order: models.Order):
    for item in order.items:
        apply_stock_movement(
            db,
            product_id=item.product_id,
            store_id=order.store_id,
            quantity=-item.quantity,
            movement_type=models.StockMovementType.SALE,
            user_id=order.user_id,
            order_item_id=item.id,
            note=f"Bán hàng order #{order.id}"
        )


def restore_stock_from_order(db: Session, order: models.Order):
    for item in order.items:
        apply_stock_movement(
            db,
            product_id=item.product_id,
            store_id=order.store_id,
            quantity=item.quantity,
            movement_type=models.StockMovementType.RETURN,
            user_id=order.user_id,
            order_item_id=item.id,
            note=f"Hủy order #{order.id}"
        )


# =========================================================
# 🔹 ADJUST
# =========================================================
def adjust_stock(
    db: Session,
    *,
    product_id: int,
    store_id: int,
    new_quantity: int,
    user_id: int
):
    if new_quantity < 0:
        raise HTTPException(400, "Tồn kho không thể âm")

    stock = get_stock_for_update(db, product_id, store_id)

    diff = new_quantity - stock.quantity

    if diff == 0:
        return None

    return apply_stock_movement(
        db,
        product_id=product_id,
        store_id=store_id,
        quantity=diff,
        movement_type=models.StockMovementType.ADJUST,
        user_id=user_id,
        note="Kiểm kho"
    )


# =========================================================
# 🔹 TRANSFER
# =========================================================
def transfer_stock(
    db: Session,
    *,
    product_id: int,
    from_store: int,
    to_store: int,
    quantity: int,
    user_id: int
):
    if quantity <= 0:
        raise HTTPException(400, "Quantity phải > 0")

    if from_store == to_store:
        raise HTTPException(400, "Không thể chuyển cùng store")

    ref = str(uuid.uuid4())

    # trừ kho nguồn
    apply_stock_movement(
        db,
        product_id=product_id,
        store_id=from_store,
        quantity=-quantity,
        movement_type=models.StockMovementType.TRANSFER,
        user_id=user_id,
        note="Chuyển kho đi",
        transfer_ref=ref
    )

    # cộng kho đích
    apply_stock_movement(
        db,
        product_id=product_id,
        store_id=to_store,
        quantity=quantity,
        movement_type=models.StockMovementType.TRANSFER,
        user_id=user_id,
        note="Nhận chuyển kho",
        transfer_ref=ref
    )


# =========================================================
# 🔹 GET STOCK
# =========================================================
def get_stock(db: Session, product_id: int, store_id: int):
    stock = db.query(models.Stock).filter(
        models.Stock.product_id == product_id,
        models.Stock.store_id == store_id
    ).first()

    return stock.quantity if stock else 0