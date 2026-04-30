# 🚀 1. Router: users.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import User, Role, Store
from app.security import get_current_user, hash_password

router = APIRouter(prefix="/users", tags=["Users"])


# 👤 2. Tạo user
@router.post("/", status_code=201)
def create_user(
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    # 🔒 chỉ manager hoặc owner
    if user["role_id"] not in [1, 2]:  # ví dụ
        raise HTTPException(403, "Không có quyền")

    username = payload.get("username")
    password = payload.get("password")
    role_id = payload.get("role_id")

    if not username or not password:
        raise HTTPException(400, "Thiếu dữ liệu")

    # check tồn tại
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(400, "Username đã tồn tại")

    new_user = User(
        username=username,
        password=hash_password(password),
        role_id=role_id,
        store_id=user["store_id"]  # 🔥 cùng store
    )

    db.add(new_user)
    db.commit()

    return {"message": "Tạo user thành công"}

# 📋 3. Danh sách user theo store
@router.get("/")
def get_users(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    users = (
        db.query(User)
        .options(joinedload(User.role))
        .filter(User.store_id == user["store_id"])
        .all()
    )

    return [
        {
            "id": u.id,
            "username": u.username,
            "role": u.role.name if u.role else None
        }
        for u in users
    ]

# 🔄 4. Update role cho user
@router.put("/{user_id}/role")
def update_user_role(
    user_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    if current_user["role_id"] not in [1]:  # chỉ owner
        raise HTTPException(403, "Không có quyền")

    role_id = payload.get("role_id")

    user = db.query(User).filter(
        User.id == user_id,
        User.store_id == current_user["store_id"]
    ).first()

    if not user:
        raise HTTPException(404, "Không tìm thấy user")

    user.role_id = role_id
    db.commit()

    return {"message": "Cập nhật role thành công"}

# ❌ 5. Xóa user
@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    if current_user["role_id"] != 1:
        raise HTTPException(403, "Không có quyền")

    user = db.query(User).filter(
        User.id == user_id,
        User.store_id == current_user["store_id"]
    ).first()

    if not user:
        raise HTTPException(404, "Không tìm thấy user")

    db.delete(user)
    db.commit()

    return {"message": "Đã xóa user"}