# routers/auth.py

from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Store
from app.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    refresh_access_token, logout_user,
    get_current_user
)

router = APIRouter(prefix="/auth", tags=["Auth"])


# =========================
# REGISTER
# =========================
@router.post("/register", status_code=201)
def register(
    username: str = Form(...),
    password: str = Form(...),
    store_name: str = Form(...),        # ✅ mỗi lần register = tạo store mới
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
        store_id=store.id,              # ✅ gắn store
        is_active=True
    )
    db.add(new_user)
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
        "store_id": user.store_id
    }

    return {
        "access_token": create_access_token(token_payload),
        "refresh_token": create_refresh_token(token_payload), 
        "token_type": "bearer"
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
    current_user=Depends(get_current_user),     
    db: Session = Depends(get_db)
):
    from datetime import datetime, timezone
    from app.security import blacklist_token

    exp = datetime.fromtimestamp(current_user["exp"], tz=timezone.utc)
    blacklist_token(current_user["jti"], exp, db)


@router.post("/logout-token", status_code=204)
def logout_with_token(
    token: str = Form(...),
    db: Session = Depends(get_db)
):
    from jose import jwt
    from app.security import SECRET_KEY, ALGORITHM
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        logout_user(payload, db)
    except Exception:
        raise HTTPException(401, "Token không hợp lệ")