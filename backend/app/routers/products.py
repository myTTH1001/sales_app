from fastapi import APIRouter, Depends, HTTPException,  UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Product
from app.security import get_current_user, require_permission
from app.schemas.product import ProductCreate, ProductResponse, ProductFilter, ProductListResponse, ProductUpdate
from app.services import product_service
import os, uuid

router = APIRouter(
    prefix="/products",
    tags=["Products"]
)


UPLOAD_DIR = "app/static/uploads"

@router.get("/", response_model=ProductListResponse)
def list_products(
    filters: ProductFilter = Depends(),
    db: Session = Depends(get_db),
    user = Depends(require_permission("product:view"))
):
    return product_service.get_products(
        db=db,
        store_id=user.store_id,
        filters=filters
    )


@router.get("/{product_id}", response_model=ProductResponse)
def get_product_api(
    product_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_permission("product:view"))
):
    return product_service.get_product(
        db=db,
        product_id=product_id,
        store_id=user.store_id
    )


@router.post("/upload-image")
def upload_product_image(
    file: UploadFile = File(...),
    # admin=Depends(require_admin)
):
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    filename = f"{uuid.uuid4()}_{file.filename}"
    path = os.path.join(UPLOAD_DIR, filename)

    with open(path, "wb") as f:
        f.write(file.file.read())

    return {
        "image": f"/uploads/{filename}"
    }

@router.post("/", response_model=ProductResponse)
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    user = Depends(require_permission("product:create"))
):
    return product_service.create_product(
        db=db,
        data=data,
        store_id=user.store_id
    )

@router.put("/{product_id}", response_model=ProductResponse)
def update_product_api(
    product_id: int,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    user = Depends(require_permission("product:update"))
):
    return product_service.update_product(
        db=db,
        product_id=product_id,
        data=data,
        store_id=user.store_id
    )

@router.delete("/{product_id}")
def delete_product_api(
    product_id: int,
    db: Session = Depends(get_db),
    user = Depends(require_permission("product:delete"))
):
    return product_service.delete_product(
        db=db,
        product_id=product_id,
        store_id=user.store_id
    )