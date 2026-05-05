from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.security import get_current_user, require_permission
from app.services.stock_service import (
    import_stock,
    adjust_stock,
    transfer_stock
)

router = APIRouter(prefix="/stock", tags=["Stock"])


# =========================================================
# 🔹 VALIDATION
# =========================================================
def validate_product(db, product_id, store_id):
    product = db.query(models.Product).filter(
        models.Product.id == product_id,
        models.Product.store_id == store_id
    ).first()

    if not product:
        raise HTTPException(404, "Product không tồn tại trong store")


def validate_store(db, store_id):
    store = db.query(models.Store).filter(
        models.Store.id == store_id
    ).first()

    if not store:
        raise HTTPException(404, "Store không tồn tại")


# =========================================================
# 🔹 LIST STOCK
# =========================================================
@router.get("/", dependencies=[Depends(require_permission("stock:view"))])
def list_stock(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    stocks = db.query(models.Stock).filter(
        models.Stock.store_id == current_user["store_id"]
    ).all()

    return [{"product_id": s.product_id, "quantity": s.quantity} for s in stocks]


# =========================================================
# 🔹 GET STOCK
# =========================================================
@router.get("/{product_id}", dependencies=[Depends(require_permission("stock:view"))])
def get_stock(product_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    validate_product(db, product_id, current_user["store_id"])

    stock = db.query(models.Stock).filter(
        models.Stock.product_id == product_id,
        models.Stock.store_id == current_user["store_id"]
    ).first()

    return {"product_id": product_id, "quantity": stock.quantity if stock else 0}


# =========================================================
# 🔹 IMPORT
# =========================================================
@router.post("/import", dependencies=[Depends(require_permission("stock:import"))])
def import_stock_api(
    product_id: int,
    quantity: int,
    note: str = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    validate_product(db, product_id, current_user["store_id"])

    if quantity <= 0:
        raise HTTPException(400, "Quantity phải > 0")

    try:
        movement = import_stock(
            db,
            product_id=product_id,
            store_id=current_user["store_id"],
            quantity=quantity,
            user_id=current_user["user_id"],
            note=note
        )

        db.flush()
        db.commit()

        return {"message": "Nhập kho thành công", "movement_id": movement.id}

    except Exception as e:
        db.rollback()
        raise e


# =========================================================
# 🔹 ADJUST
# =========================================================
@router.post("/adjust", dependencies=[Depends(require_permission("stock:adjust"))])
def adjust_stock_api(
    product_id: int,
    new_quantity: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    validate_product(db, product_id, current_user["store_id"])

    try:
        adjust_stock(
            db,
            product_id=product_id,
            store_id=current_user["store_id"],
            new_quantity=new_quantity,
            user_id=current_user["user_id"]
        )

        db.commit()

        return {"message": "Điều chỉnh tồn kho thành công"}

    except Exception as e:
        db.rollback()
        raise e


# =========================================================
# 🔹 TRANSFER
# =========================================================
@router.post("/transfer", dependencies=[Depends(require_permission("stock:transfer"))])
def transfer_stock_api(
    product_id: int,
    to_store_id: int,
    quantity: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    validate_product(db, product_id, current_user["store_id"])
    validate_store(db, to_store_id)

    if quantity <= 0:
        raise HTTPException(400, "Quantity phải > 0")

    try:
        transfer_stock(
            db,
            product_id=product_id,
            from_store=current_user["store_id"],
            to_store=to_store_id,
            quantity=quantity,
            user_id=current_user["user_id"]
        )

        db.commit()

        return {"message": "Chuyển kho thành công"}

    except Exception as e:
        db.rollback()
        raise e


# =========================================================
# 🔹 MOVEMENTS
# =========================================================
@router.get("/movements", dependencies=[Depends(require_permission("stock:view"))])
def stock_movements(
    product_id: int = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    query = db.query(models.StockMovement).filter(
        models.StockMovement.store_id == current_user["store_id"]
    )

    if product_id:
        validate_product(db, product_id, current_user["store_id"])
        query = query.filter(models.StockMovement.product_id == product_id)

    movements = query.order_by(
        models.StockMovement.created_at.desc()
    ).limit(limit).all()

    return [
        {
            "id": m.id,
            "product_id": m.product_id,
            "quantity": m.quantity,
            "type": m.type,
            "created_at": m.created_at,
            "note": m.note,
            "transfer_ref": m.transfer_ref
        }
        for m in movements
    ]