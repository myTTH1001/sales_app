from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session, joinedload
from typing import Optional

from datetime import datetime, date
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
        store_id=user["store_id"],
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
    invoice_items = []
    for item in items:
        # 🔧 FIX 2: kiểm tra product
        product = db.query(Product).filter(
            Product.id == item["product_id"]
        ).first()

        if not product:
            raise HTTPException(404, f"Sản phẩm {item['product_id']} không tồn tại")

        db_item = OrderItem(
            order_id=order.id,
            product_id=item["product_id"],
            quantity=item["quantity"],
            price=item["price"]
        )
        subtotal = item["price"] * item["quantity"]
        total += subtotal
        # total += item["price"] * item["quantity"]
        db.add(db_item)

        invoice_items.append({
            "name": product.name,
            "qty": item["quantity"],
            "price": item["price"],
            "subtotal": subtotal
        })

    order.total = total
    invoice = Invoice(
        order_id=order.id,
        total=total
    )
    db.add(invoice)
    db.commit()
    db.refresh(order)
    return {
        "message": "Đã bán thành công đơn hàng !!!",
        "order_id": order.id,
        "created_at": order.created_at.strftime("%d/%m/%Y %H:%M:%S"),
        "cashier": user["username"],
        "total": total,
        "items": invoice_items
    }

@router.post("/print")
async def print_invoice(request: Request):
    from escpos.printer import Serial
    from PIL import Image
    import base64, io
    data = await request.json()
    image_base64 = data.get("imageData")

    if not image_base64:
        return {"error": "Thiếu dữ liệu ảnh"}

    # Giải mã base64 (bỏ phần "data:image/png;base64,")
    image_bytes = base64.b64decode(image_base64.split(",")[1])
    img = Image.open(io.BytesIO(image_bytes))

    # Kết nối tới máy in Bluetooth PT210 qua COM6
    p = Serial(devfile="COM6", baudrate=115200, timeout=1)
    p.image(img)
    p.cut()
    p.close()

    return {"message": "Đã in hóa đơn thành công!"}
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
    if user["role"] != "admin" and order.user_id != user["user_id"]:
        raise HTTPException(
            status_code=403,
            detail="Chỉ admin mới được hủy đơn"
        )

    order = db.query(Order).filter(
        Order.id == order_id,
        Order.status.in_(["confirmed"])
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
def get_draft_orders(
    db: Session = Depends(get_db),
    user = Depends(get_current_user)):
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
    user = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None
):
    query = db.query(Order)
    if status not in ["confirmed", "cancelled", "draft"]:
        raise HTTPException(
            status_code=400,
            detail="Status không hợp lệ"
        )
    # ===== LỌC TRẠNG THÁI =====
    if status:
        query = query.filter(Order.status == status)

    # ===== LỌC TỪ NGÀY =====
    if date_from:
        start_datetime = datetime.combine(date_from, datetime.min.time())
        query = query.filter(Order.created_at >= start_datetime)

    # ===== LỌC ĐẾN NGÀY =====
    if date_to:
        end_datetime = datetime.combine(date_to, datetime.max.time())
        query = query.filter(Order.created_at <= end_datetime)

    # ===== ĐẾM TỔNG SỐ =====
    total_count = query.count()

    # ===== PHÂN TRANG =====
    orders = (
        query.order_by(Order.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "orders": [
            {
                "id": o.id,
                "created_at": o.created_at.isoformat(),
                "total": o.total,
                "status": o.status
            }
            for o in orders
        ],
        "count": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit
    }

# =========================================================
# 4️⃣ LẤY CHI TIẾT 1 ĐƠN HÀNG (DRAFT / CONFIRMED)
# =========================================================
@router.get("/{order_id}", status_code=status.HTTP_200_OK)
def get_order_detail(
    order_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    order = (
        db.query(Order)
        .options(
            joinedload(Order.items)
            .joinedload(OrderItem.product)
        )
        .filter(
            Order.id == order_id,
            Order.status.in_(["draft", "cancelled", "confirmed"])
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

