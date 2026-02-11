from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Invoice, Order

router = APIRouter(
    prefix="/invoices",
    tags=["Invoices"]
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/{order_id}")
def create_invoice(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).get(order_id)

    invoice = Invoice(
        order_id=order.id,
        total=order.total
    )
    db.add(invoice)
    db.commit()
    return invoice
