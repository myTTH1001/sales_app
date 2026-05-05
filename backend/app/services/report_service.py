from sqlalchemy import func, cast, Date
from sqlalchemy.orm import Session
from datetime import datetime
from app import models


# =========================================================
# INTERNAL BASE QUERY
# =========================================================
def _base_invoice_filter(query, user, start_date, end_date):
    return query.filter(
        models.Invoice.store_id == user["store_id"],
        models.Invoice.status == "paid",
        models.Invoice.paid_at.isnot(None),
        models.Invoice.paid_at >= start_date,
        models.Invoice.paid_at <= end_date
    )


# =========================================================
# 1. REVENUE BY DAY
# =========================================================
def revenue_by_day(db: Session, user, start_date, end_date):
    query = db.query(
        cast(models.Invoice.paid_at, Date).label("date"),
        func.sum(models.Invoice.total).label("revenue"),
        func.count(models.Invoice.id).label("total_orders")
    )

    query = _base_invoice_filter(query, user, start_date, end_date)

    result = query.group_by(
        cast(models.Invoice.paid_at, Date)
    ).order_by(
        cast(models.Invoice.paid_at, Date)
    ).all()

    return result


# =========================================================
# 2. REVENUE BY CASHIER
# =========================================================
def revenue_by_cashier(db: Session, user, start_date, end_date):
    query = db.query(
        models.User.id.label("cashier_id"),
        models.User.username,
        func.sum(models.Invoice.total).label("revenue"),
        func.count(models.Invoice.id).label("total_orders")
    ).join(
        models.User, models.User.id == models.Invoice.cashier_id
    )

    query = _base_invoice_filter(query, user, start_date, end_date)

    result = query.group_by(
        models.User.id,
        models.User.username
    ).order_by(
        func.sum(models.Invoice.total).desc()
    ).all()

    return result


# =========================================================
# 3. REVENUE BY PRODUCT
# =========================================================
def revenue_by_product(
    db: Session,
    user,
    start_date,
    end_date,
    limit: int = 10,
    offset: int = 0
):
    base = db.query(
        models.Product.id.label("product_id"),
        models.Product.name.label("product_name"),
        func.sum(models.OrderItem.quantity).label("total_sold"),
        func.sum(models.OrderItem.quantity * models.OrderItem.price).label("revenue")
    ).join(
        models.OrderItem, models.OrderItem.product_id == models.Product.id
    ).join(
        models.Order, models.Order.id == models.OrderItem.order_id
    ).join(
        models.Invoice, models.Invoice.order_id == models.Order.id
    )

    base = base.filter(
        models.Invoice.store_id == user["store_id"],
        models.Invoice.status == "paid",
        models.Invoice.paid_at.isnot(None),
        models.Invoice.paid_at >= start_date,
        models.Invoice.paid_at <= end_date
    )

    grouped = base.group_by(
        models.Product.id,
        models.Product.name
    )

    total = grouped.count()

    data = grouped.order_by(
        func.sum(models.OrderItem.quantity).desc()
    ).offset(offset).limit(limit).all()

    return {
        "total": total,
        "data": data,
        "has_more": len(data) == limit
    }