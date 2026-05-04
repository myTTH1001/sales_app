from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from jose.exceptions import ExpiredSignatureError
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from typing import List
from app.database import get_db
from sqlalchemy.orm import Session
from app import models
import os
import uuid

# ========================
# CONFIG
# ========================
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY must be set in environment")

ALGORITHM = "HS256"
ACCESS_EXPIRE_MINUTES = 30
REFRESH_EXPIRE_DAYS = 7

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__rounds=4
)

# ========================
# PASSWORD
# ========================
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

# ========================
# TOKEN
# ========================
def create_token(data: dict, expires_delta: timedelta, token_type: str):
    now = datetime.now(timezone.utc)
    payload = data.copy()

    jti = str(uuid.uuid4())

    payload.update({
        "exp": now + expires_delta,
        "iat": now,
        "nbf": now,
        "type": token_type,
        "jti": jti
    })

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(data: dict, permissions: list[str] | None = None):
    return create_token({**data, "permissions": permissions or []},
                        timedelta(minutes=ACCESS_EXPIRE_MINUTES), "access")


# ========================
# PERMISSIONS LOADER
# ========================
def load_user_permissions(user_id: int, store_id: int, db: Session) -> list[str]:
    """
    Load danh sách permissions của user trong một store cụ thể.
    Traverse: UserRole → Role → role_permissions → Permission
    """
    from sqlalchemy.orm import joinedload

    user_roles = (
        db.query(models.UserRole)
        .options(
            joinedload(models.UserRole.role)
            .joinedload(models.Role.permissions)
        )
        .filter(
            models.UserRole.user_id == user_id,
            models.UserRole.store_id == store_id,
        )
        .all()
    )

    permissions: set[str] = set()
    for ur in user_roles:
        for perm in ur.role.permissions:
            permissions.add(perm.name)

    return sorted(permissions)


def _seed_all_permissions(db: Session) -> dict[str, models.Permission]:
    """
    Đảm bảo toàn bộ permissions trong PERMISSIONS đã có trong bảng DB.
    Trả về perm_map {name: Permission} để caller dùng tiếp — không commit.
    Idempotent: gọi nhiều lần không tạo duplicate.
    """
    from app.permissions import all_permissions

    all_perm_names = all_permissions()

    existing = db.query(models.Permission).filter(
        models.Permission.name.in_(all_perm_names)
    ).all()
    perm_map: dict[str, models.Permission] = {p.name: p for p in existing}

    for name in all_perm_names:
        if name not in perm_map:
            new_perm = models.Permission(name=name)
            db.add(new_perm)
            perm_map[name] = new_perm

    db.flush()  # đảm bảo các Permission mới có id trước khi caller dùng
    return perm_map


def get_or_create_role(role_name: str, db: Session) -> models.Role:
    """
    Lấy role theo tên từ DB, tạo mới nếu chưa có.
    Đồng thời seed permissions theo ROLE_TEMPLATES[role_name] vào role.
    Idempotent — gọi nhiều lần không gây duplicate.
    Không tự commit — caller chịu trách nhiệm commit/rollback.
    """
    from app.permissions import ROLE_TEMPLATES

    if role_name not in ROLE_TEMPLATES:
        raise ValueError(f"Role '{role_name}' không có trong ROLE_TEMPLATES")

    # 1. Seed bảng permissions (đảm bảo tất cả permissions tồn tại trong DB)
    perm_map = _seed_all_permissions(db)

    # 2. Lấy hoặc tạo role
    role = db.query(models.Role).filter(models.Role.name == role_name).first()
    if not role:
        role = models.Role(name=role_name)
        db.add(role)
        db.flush()

    # 3. Gắn permissions còn thiếu theo template (không xóa permissions đã có thêm thủ công)
    template_perm_names = set(ROLE_TEMPLATES[role_name])
    existing_perm_names = {p.name for p in role.permissions}
    missing = template_perm_names - existing_perm_names

    for name in missing:
        if name in perm_map:
            role.permissions.append(perm_map[name])

    db.flush()
    return role


def get_or_create_owner_role(db: Session) -> models.Role:
    """Giữ lại để không break auth.py — delegate sang get_or_create_role."""
    return get_or_create_role("owner", db)


def create_refresh_token(data: dict):
    return create_token(data, timedelta(days=REFRESH_EXPIRE_DAYS), "refresh")


# ========================
# BLACKLIST (DB)
# ========================
def blacklist_token(jti: str, exp: datetime, db: Session):
    db.add(models.TokenBlacklist(jti=jti, exp=exp))
    db.commit()

def is_token_blacklisted(jti: str, db: Session) -> bool:
    return db.query(models.TokenBlacklist).filter(
        models.TokenBlacklist.jti == jti
    ).first() is not None

def cleanup_blacklist(db: Session):
    db.query(models.TokenBlacklist).filter(
        models.TokenBlacklist.exp < datetime.now(timezone.utc)
    ).delete()
    db.commit()
# ========================
# CURRENT USER
# ========================
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        if payload.get("type") != "access":
            raise HTTPException(401, "Invalid token type")

        user_id = payload.get("user_id")
        store_id = payload.get("store_id")
        jti = payload.get("jti")
        permissions = payload.get("permissions", [])

        if not user_id or not store_id or not jti:
            raise HTTPException(401, "Invalid token")

        if is_token_blacklisted(jti, db):
            raise HTTPException(401, "Token revoked")

        user = db.query(models.User).filter(models.User.id == user_id).first()

        if not user:
            raise HTTPException(401, "User not found")

        if not user.is_active:
            raise HTTPException(403, "User bị khóa")

        if user.store_id != store_id:
            raise HTTPException(403, "Sai store")

        return {
            "user_id": user.id,
            "store_id": user.store_id,
            "jti": jti,
            "exp": payload["exp"],
            "permissions": permissions, 
        }

    except ExpiredSignatureError:
        raise HTTPException(401, "Token expired")

    except JWTError:
        raise HTTPException(401, "Invalid token")
# ========================
# RBAC
# ========================
def require_permission(permission_name: str):
    def checker(
        user=Depends(get_current_user)
        # db: Session = Depends(get_db)
    ):
        if permission_name not in user["permissions"]:
            raise HTTPException(403, f"Thiếu quyền: {permission_name}")
        return user
    return checker
# ========================
# REFRESH TOKEN
# ========================
def refresh_access_token(refresh_token: str , db: Session):
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])

        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401,detail="Invalid token type",headers={"WWW-Authenticate": "Bearer"})

        jti = payload.get("jti")

        if is_token_blacklisted(jti, db):
            raise HTTPException(401, "Token revoked")

        # Kiểm tra lại trạng thái user (có thể bị khóa sau khi đăng nhập)
        user_id  = payload.get("user_id")
        store_id = payload.get("store_id")

        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(401, "User không tồn tại")
        if not user.is_active:
            raise HTTPException(403, "Tài khoản đã bị khóa")
        if user.store_id != store_id:
            raise HTTPException(403, "Sai store")

        # Rotate refresh token — blacklist token cũ
        blacklist_token(jti, datetime.fromtimestamp(payload["exp"], tz=timezone.utc), db)

        new_payload = {
            "user_id": user.id,
            "sub": user.username,
            "store_id": user.store_id,
        }

        # Load lại permissions từ DB — đảm bảo luôn up-to-date
        permissions = load_user_permissions(user.id, user.store_id, db)

        return {
            "access_token": create_access_token(new_payload, permissions),
            "refresh_token": create_refresh_token(new_payload),
        }

    except ExpiredSignatureError:
        raise HTTPException(401, "Refresh token expired")

    except JWTError:
        raise HTTPException(401, "Invalid refresh token")


# ========================
# LOGOUT
# ========================
def logout_user(user_payload: dict, db: Session):
    jti = user_payload.get("jti")
    exp = datetime.fromtimestamp(user_payload["exp"], tz=timezone.utc)
    blacklist_token(jti, exp, db)
    return {"msg": "Logged out"}


def blacklist_refresh_token(refresh_token: str, db: Session):
    """
    Decode và blacklist một refresh token.
    Raise HTTPException nếu token không hợp lệ hoặc sai type.
    Token đã hết hạn được bỏ qua (không cần blacklist).
    """
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        return  # đã hết hạn → không cần blacklist, bỏ qua
    except JWTError:
        raise HTTPException(400, "Refresh token không hợp lệ")

    if payload.get("type") != "refresh":
        raise HTTPException(400, "Token không phải refresh token")

    jti = payload.get("jti")
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

    if not is_token_blacklisted(jti, db):
        blacklist_token(jti, exp, db)