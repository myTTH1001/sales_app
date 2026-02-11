from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Order, OrderItem, Product, Invoice, OrderStatus
from app.security import get_current_user
from app.schemas.order_item import AddItemSchema, UpdateItemSchema

router = APIRouter(
    prefix="/orders",
    tags=["Orders"]
)

# =========================================================
# 1️⃣ TẠO ĐƠN NHÁP (KHÁCH MỚI) - KHI ẤN "ĐƠN MỚI"
# =========================================================
@router.post("/draft", status_code=status.HTTP_201_CREATED)
def save_draft_order(
    payload: dict,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    # Lưu đơn hàng nháp
    order = Order(
        user_id=user["user_id"],
        status="draft",
        total=0)

    db.add(order)
    db.commit()
    db.refresh(order)
    # Chi tiết đơn hàng nháp
    order_item = ""
    items = payload.get("items")
    if not items:
        raise HTTPException(400, "Danh sách sản phẩm trống")

    for item in items:
        # 🔧 FIX 2: kiểm tra product
        product = db.query(Product).filter(
            Product.id == item["product_id"]
        ).first()

        if not product:
            raise HTTPException(
                404,
                f"Sản phẩm {item['product_id']} không tồn tại"
            )

        db_item = OrderItem(
            order_id=order.id,
            product_id=item["product_id"],
            quantity=item["quantity"],
            price=item["price"]
        )
        db.add(db_item)

    db.commit()
    return {"message": "Đã lưu đơn nháp"}



# =========================================================
# XÁC NHẬN ĐƠN HÀNG - KHI ẤN "THANH TOÁN"
# =========================================================
@router.post("/confirmed", status_code=status.HTTP_201_CREATED)
def comfirmed_order(
    payload: dict,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    items = payload.get("items")
    if not items:
        raise HTTPException(400, "Danh sách sản phẩm trống")
    
    # Lưu đơn hàng
    order = Order(
        user_id=user["user_id"],
        status="confirmed",
        total=0)

    db.add(order)
    db.commit()
    db.refresh(order)

    # Chi tiết đơn hàng 
    total = 0    
    for item in items:
        # 🔧 FIX 2: kiểm tra product
        product = db.query(Product).filter(
            Product.id == item["product_id"]
        ).first()

        if not product:
            raise HTTPException(
                404,
                f"Sản phẩm {item['product_id']} không tồn tại"
            )

        db_item = OrderItem(
            order_id=order.id,
            product_id=item["product_id"],
            quantity=item["quantity"],
            price=item["price"]
        )
        total += item["price"] * item["quantity"]
        db.add(db_item)

    order.total = total
    db.commit()
    return {
        "message": "Đã bán thành công đơn hàng !!!",
        "order_id": order.id,
        "total": total
    }

# =========================================================
# 3️⃣ HỦY ĐƠN HÀNG - CHỈ ADMIN
# =========================================================
@router.post("/cancelled/{order_id}", status_code=status.HTTP_200_OK)
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):

    # 🔒 CHỈ ADMIN
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Chỉ admin mới được hủy đơn"
        )

    order = db.query(Order).filter(
        Order.id == order_id,
        Order.status.in_(["draft", "confirmed"])
    ).first()

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy đơn hợp lệ để hủy"
        )

    order.status = "cancelled"
    db.commit()

    return {
        "message": "Admin đã hủy đơn hàng"
    }


# =========================================================
# XÓA ĐƠN HÀNG - CHỈ ADMIN
# =========================================================
@router.post("/deleted/{order_id}", status_code=status.HTTP_200_OK)
def delete_order(
    order_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):

    # 🔒 CHỈ ADMIN
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Chỉ admin mới được hủy đơn"
        )
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.status.in_(["cancelled"])
    ).first()

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy đơn hợp lệ để xóa"
        )

    order.status = "deleted"
    db.commit()

    return {
        "message": "Admin đã xóa đơn hàng"
    }

# =========================================================
# 4️⃣ LẤY DANH SÁCH ĐƠN NHÁP (GIỎ HÀNG)
# =========================================================
@router.get("/draft", status_code=status.HTTP_200_OK)
def get_draft_orders(db: Session = Depends(get_db)):
    orders = (
        db.query(Order)
        .filter(Order.status == "draft")
        .order_by(Order.created_at.desc())
        .all()
    )

    result = []
    for order in orders:
        result.append({
            "order_id": order.id,
            "created_at": order.created_at,
            "total": order.total,
            "items": [
                {
                    "product_id": item.product_id,
                    "product_name": item.product.name,
                    "price": item.price,
                    "quantity": item.quantity,
                    "image": item.product.image
                }
                for item in order.items
            ]
        })

    return {
        "count": len(result),
        "orders": result
    }

# =========================================================
# XÓA ĐƠN NHÁP
# =========================================================
@router.delete("/draft/{order_id}", status_code=status.HTTP_200_OK)
def delete_draft_order(
    order_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    order = (
        db.query(Order)
        .filter(
            Order.id == order_id,
            Order.status == OrderStatus.draft,
            Order.user_id == user["user_id"]  # 🔒 chỉ xóa đơn của mình
        )
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy đơn nháp"
        )

    db.delete(order)
    db.commit()

    return {"message": "Đã xoá đơn nháp"}



# =========================================================
# =========================================================
@router.get("/manage", status_code=200)
def get_orders_manage(
    status: str = Query(...),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    if status not in ["confirmed", "cancelled", "draft"]:
        raise HTTPException(
            status_code=400,
            detail="Status không hợp lệ"
        )

    orders = (
        db.query(Order)
        .filter(Order.status == status)
        .order_by(Order.created_at.desc())
        .all()
    )

    return {
        "count": len(orders),
        "orders": [
            {
                "id": o.id,
                "total": o.total,
                "created_at": o.created_at
            }
            for o in orders
        ]
    }

# =========================================================
# 4️⃣ LẤY CHI TIẾT 1 ĐƠN HÀNG (DRAFT / CONFIRMED)
# =========================================================
@router.get("/{order_id}", status_code=status.HTTP_200_OK)
def get_order_detail(
    order_id: int,
    db: Session = Depends(get_db)
):
    order = (
        db.query(Order)
        .options(
            joinedload(Order.items)
            .joinedload(OrderItem.product)
        )
        .filter(
            Order.id == order_id,
            Order.status.in_(["draft", "confirmed"])
        )
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy đơn hàng"
        )

    return {
        "id": order.id,
        "status": order.status,
        "total": order.total,
        "created_at": order.created_at,
        "items": [
            {
                "product_id": item.product_id,
                "product_name": item.product.name,
                "price": item.price,
                "quantity": item.quantity,
                "image": item.product.image
            }
            for item in order.items
        ]
    }





# =========================================================
# =========================================================
