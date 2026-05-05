from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import require_permission

from app.schemas.invoice import InvoiceOut, InvoiceCreate
from app.services import invoice_service

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.post("/{order_id}", response_model=InvoiceOut)
def pay_order(
    order_id: int,
    data: InvoiceCreate,
    db: Session = Depends(get_db),
    user=Depends(require_permission("invoice:create"))
):
    return invoice_service.create_invoice(
        db,
        order_id=order_id,
        user=user,
        payment_method=data.payment_method
    )