# routers/auth.py

from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import get_db
from app.security import blacklist_token, blacklist_refresh_token
from app.models import User, Store, Role, Permission, UserRole
from app.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    refresh_access_token, logout_user,
    get_current_user, load_user_permissions,
    get_or_create_owner_role,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


# =========================
# REGISTER
# =========================
@router.post("/register", status_code=201)
def register(
    username: str = Form(...),
    password: str = Form(...),
    store_name: str = Form(...),
    db: Session = Depends(get_db)
):
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(400, "Username đã tồn tại")

    if len(password) < 6:
        raise HTTPException(400, "Password phải có ít nhất 6 ký tự")

    # Tạo store mới cho owner này
    store = Store(name=store_name.strip())
    db.add(store)
    db.flush()  # lấy store.id trước khi tạo user

    new_user = User(
        username=username.strip(),
        password=hash_password(password),
        store_id=store.id,
        is_active=True
    )
    db.add(new_user)
    db.flush()  # lấy new_user.id trước khi tạo UserRole

    # Lấy hoặc tạo role "owner" (kèm seed permissions nếu chưa có)
    owner_role = get_or_create_owner_role(db)

    # Gán role owner cho user này trong store này
    db.add(UserRole(
        user_id=new_user.id,
        role_id=owner_role.id,
        store_id=store.id,
    ))
    db.commit()

    return {"message": "Đăng ký thành công", "store_id": store.id}


# =========================
# LOGIN
# =========================
@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == form_data.username).first()

    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(401, "Sai tài khoản hoặc mật khẩu")

    if not user.is_active:
        raise HTTPException(403, "Tài khoản đã bị khóa")

    # ✅ payload chỉ chứa scalar — không truyền ORM object vào token
    token_payload = {
        "user_id": user.id,
        "sub": user.username,
        "store_id": user.store_id,
    }

    # Load permissions từ DB theo store
    permissions = load_user_permissions(user.id, user.store_id, db)

    return {
        "access_token": create_access_token(token_payload, permissions),
        "refresh_token": create_refresh_token(token_payload),
        "token_type": "bearer",
    }


# =========================
# REFRESH TOKEN
# =========================
@router.post("/refresh")
def refresh(
    refresh_token: str = Form(...),
    db: Session = Depends(get_db)
):
    return refresh_access_token(refresh_token, db)   


# =========================
# LOGOUT
# =========================
@router.post("/logout", status_code=204)
def logout(
    refresh_token: str = Form(...),          # bắt buộc gửi lên
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from datetime import datetime, timezone

    # 1. Blacklist access token (lấy từ Authorization header qua get_current_user)
    exp = datetime.fromtimestamp(current_user["exp"], tz=timezone.utc)
    blacklist_token(current_user["jti"], exp, db)

    # 2. Blacklist refresh token
    blacklist_refresh_token(refresh_token, db)


@router.post("/logout-token", status_code=204)
def logout_with_token(
    token: str = Form(...),
    db: Session = Depends(get_db)
):
    # Endpoint này nhận refresh token (dùng cho client không giữ access token)
    blacklist_refresh_token(token, db)
