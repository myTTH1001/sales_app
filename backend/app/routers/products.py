from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone

from app.database import get_db
from app import models
from app.security import require_permission

from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductFilter
)

router = APIRouter(prefix="/products", tags=["Products"])


# =========================================================
# CREATE PRODUCT
# =========================================================
@router.post(
    "",
    response_model=ProductResponse
)
def create_product(
    data: ProductCreate,
    user=Depends(require_permission("product:create")),
    db: Session = Depends(get_db)
):
    # check trùng tên trong store
    exists = db.query(models.Product).filter(
        models.Product.name == data.name,
        models.Product.store_id == user["store_id"],
        models.Product.deleted_at.is_(None)
    ).first()

    if exists:
        raise HTTPException(400, "Sản phẩm đã tồn tại")

    product = models.Product(
        name=data.name,
        price=data.price,
        unit=data.unit,
        image=data.image,
        store_id=user["store_id"]
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    return product


# =========================================================
# GET LIST (PAGINATION + SEARCH)
# =========================================================
@router.get(
    "",
    response_model=List[ProductResponse]
)
def get_products(
    db: Session = Depends(get_db),
    user=Depends(require_permission("product:view")),
    search: Optional[str] = Query(None, description="Tìm theo tên"),
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    query = db.query(models.Product).filter(
        models.Product.store_id == user["store_id"],
        models.Product.deleted_at.is_(None)
    )

    # 🔍 search
    if search:
        query = query.filter(models.Product.name.ilike(f"%{search}%"))

    # 💰 filter price
    if min_price is not None:
        query = query.filter(models.Product.price >= min_price)

    if max_price is not None:
        query = query.filter(models.Product.price <= max_price)

    # 📄 pagination
    products = query.order_by(models.Product.created_at.desc()) \
                    .offset(offset) \
                    .limit(limit) \
                    .all()

    return products


# =========================================================
# GET DETAIL
# =========================================================
@router.get(
    "/{product_id}",
    response_model=ProductResponse
)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permission("product:view"))
):
    product = db.query(models.Product).filter(
        models.Product.id == product_id,
        models.Product.store_id == user["store_id"],
        models.Product.deleted_at.is_(None)
    ).first()

    if not product:
        raise HTTPException(404, "Không tìm thấy sản phẩm")

    return product


# =========================================================
# UPDATE
# =========================================================
@router.put(
    "/{product_id}",
    response_model=ProductResponse
)
def update_product(
    product_id: int,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_permission("product:update"))
):
    product = db.query(models.Product).filter(
        models.Product.id == product_id,
        models.Product.store_id == user["store_id"],
        models.Product.deleted_at.is_(None)
    ).first()

    if not product:
        raise HTTPException(404, "Không tìm thấy sản phẩm")

    # check trùng tên nếu đổi
    if data.name and data.name != product.name:
        exists = db.query(models.Product).filter(
            models.Product.name == data.name,
            models.Product.store_id == user["store_id"],
            models.Product.deleted_at.is_(None),
        ).first()

        if exists:
            raise HTTPException(400, "Tên sản phẩm đã tồn tại")

    for field, value in data.dict(exclude_unset=True).items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)

    return product


# =========================================================
# DELETE (SOFT DELETE)
# =========================================================
@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permission("product:delete"))
):
    product = db.query(models.Product).filter(
        models.Product.id == product_id,
        models.Product.store_id == user["store_id"],
        models.Product.deleted_at.is_(None)
    ).first()

    if not product:
        raise HTTPException(404, "Không tìm thấy sản phẩm")

    product.deleted_at = datetime.now(timezone.utc)

    db.commit()

    return {"msg": "Đã xoá sản phẩm"}