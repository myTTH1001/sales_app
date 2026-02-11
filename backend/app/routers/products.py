from fastapi import APIRouter, Depends, HTTPException,  UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Product
from app.security import get_current_user, require_admin
from app.schemas.product import ProductCreate
import os, uuid

router = APIRouter(
    prefix="/products",
    tags=["Products"]
)


UPLOAD_DIR = "app/static/uploads"

@router.get("/")
def get_products(
    db: Session = Depends(get_db),
    user = Depends(get_current_user)

):
    return db.query(Product).all()



@router.post("/upload-image")
def upload_product_image(
    file: UploadFile = File(...),
    admin=Depends(require_admin)
):
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    filename = f"{uuid.uuid4()}_{file.filename}"
    path = os.path.join(UPLOAD_DIR, filename)

    with open(path, "wb") as f:
        f.write(file.file.read())

    return {
        "image": f"/uploads/{filename}"
    }


@router.post("/")
def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db),
    admin=Depends(require_admin)
):
    db_product = Product(**product.dict())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product


@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    admin=Depends(require_admin)
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(product)
    db.commit()
    return {"message": "Deleted"}