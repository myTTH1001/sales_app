from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.security import require_permission

from app.schemas.invoice import InvoiceOut, InvoiceCreate, InvoiceListResponse
from app.services import invoice_service

router = APIRouter(prefix="/invoices", tags=["Invoices"])


# =========================================================
# LIST INVOICES
# =========================================================
@router.get("", response_model=InvoiceListResponse)
def list_invoices(
    status: Optional[str] = Query(
        default=None,
        description="Lọc theo trạng thái: paid | cancelled"
    ),
    cashier_id: Optional[int] = Query(
        default=None,
        description="Lọc theo cashier"
    ),
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(require_permission("invoice:view"))
):
    return invoice_service.list_invoices(
        db,
        user=user,
        status=status,
        cashier_id=cashier_id,
        limit=limit,
        offset=offset,
    )


# =========================================================
# GET INVOICE DETAIL
# =========================================================
@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permission("invoice:view"))
):
    return invoice_service.get_invoice(db, invoice_id=invoice_id, user=user)


# =========================================================
# CREATE INVOICE (THANH TOÁN ORDER)
# =========================================================
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


# =========================================================
# CANCEL INVOICE
# =========================================================
@router.post("/{invoice_id}/cancel", response_model=InvoiceOut)
def cancel_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_permission("invoice:cancel"))
):
    return invoice_service.cancel_invoice(db, invoice_id=invoice_id, user=user)