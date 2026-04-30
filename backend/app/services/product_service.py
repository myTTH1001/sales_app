from sqlalchemy.orm import Session
from sqlalchemy import func
from app import models
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductFilter
)
from fastapi import HTTPException


# =========================================================
# 🔹 CREATE PRODUCT
# =========================================================
def create_product(
    db: Session,
    data: ProductCreate,
    store_id: int
):
    # check trùng tên trong cùng store
    existing = db.query(models.Product).filter(
        models.Product.name == data.name,
        models.Product.store_id == store_id,
        models.Product.deleted_at.is_(None)
    ).first()

    if existing:
        raise HTTPException(400, "Sản phẩm đã tồn tại")

    product = models.Product(
        name=data.name,
        price=data.price,
        unit=data.unit,
        image=data.image,
        store_id=store_id
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    return product


# =========================================================
# 🔹 GET LIST (SEARCH + PAGINATION)
# =========================================================
def get_products(
    db: Session,
    store_id: int,
    filters: ProductFilter
):
    query = db.query(models.Product).filter(
        models.Product.store_id == store_id,
        models.Product.deleted_at.is_(None)
    )

    # 🔍 search theo tên
    if filters.search:
        query = query.filter(
            models.Product.name.ilike(f"%{filters.search}%")
        )

    # 💰 filter giá
    if filters.min_price is not None:
        query = query.filter(models.Product.price >= filters.min_price)

    if filters.max_price is not None:
        query = query.filter(models.Product.price <= filters.max_price)

    # 📊 tổng
    total = query.with_entities(func.count()).scalar()

    # 📄 pagination
    offset = (filters.page - 1) * filters.limit

    items = query.order_by(models.Product.created_at.desc()) \
        .offset(offset) \
        .limit(filters.limit) \
        .all()

    return {
        "total": total,
        "items": items
    }


# =========================================================
# 🔹 GET ONE
# =========================================================
def get_product(
    db: Session,
    product_id: int,
    store_id: int
):
    product = db.query(models.Product).filter(
        models.Product.id == product_id,
        models.Product.store_id == store_id,
        models.Product.deleted_at.is_(None)
    ).first()

    if not product:
        raise HTTPException(404, "Không tìm thấy sản phẩm")

    return product


# =========================================================
# 🔹 UPDATE
# =========================================================
def update_product(
    db: Session,
    product_id: int,
    data: ProductUpdate,
    store_id: int
):
    product = get_product(db, product_id, store_id)

    # check trùng tên nếu đổi tên
    if data.name and data.name != product.name:
        existing = db.query(models.Product).filter(
            models.Product.name == data.name,
            models.Product.store_id == store_id,
            models.Product.deleted_at.is_(None),
            models.Product.id != product_id
        ).first()

        if existing:
            raise HTTPException(400, "Tên sản phẩm đã tồn tại")

    # update field
    update_data = data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(product, key, value)

    db.commit()
    db.refresh(product)

    return product


# =========================================================
# 🔹 SOFT DELETE
# =========================================================
def delete_product(
    db: Session,
    product_id: int,
    store_id: int
):
    product = get_product(db, product_id, store_id)

    product.deleted_at = func.now()

    db.commit()

    return {"message": "Đã xoá sản phẩm"}


# =========================================================
# 🔹 GET STOCK (TỒN KHO HIỆN TẠI)
# =========================================================
def get_product_stock(
    db: Session,
    product_id: int,
    store_id: int
):
    # check product tồn tại
    get_product(db, product_id, store_id)

    total = db.query(
        func.coalesce(func.sum(models.StockMovement.quantity), 0)
    ).filter(
        models.StockMovement.product_id == product_id,
        models.StockMovement.store_id == store_id
    ).scalar()

    return {
        "product_id": product_id,
        "stock": int(total)
    }