# users.py — thêm GET /{user_id} + response schema cho POST

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel, field_validator
from typing import List
from app.database import get_db
from app import models
from app.security import require_permission, hash_password, get_or_create_role
from app.permissions import ROLE_TEMPLATES

router = APIRouter(prefix="/users", tags=["Users"])


# Roles mà owner/manager được phép gán khi tạo user mới.
# "owner" bị loại khỏi danh sách — tạo owner phải qua /auth/register.
_ASSIGNABLE_ROLES = set(ROLE_TEMPLATES.keys()) - {"owner"}


# =========================
# SCHEMAS
# =========================
class CreateUserPayload(BaseModel):
    username: str
    password: str
    role_name: str  # bắt buộc — caller phải chỉ định rõ role

    @field_validator("username")
    @classmethod
    def username_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Username không được để trống")
        if len(v) < 3:
            raise ValueError("Username phải có ít nhất 3 ký tự")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password phải có ít nhất 6 ký tự")
        return v

    @field_validator("role_name")
    @classmethod
    def role_name_valid(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in _ASSIGNABLE_ROLES:
            raise ValueError(
                f"role_name không hợp lệ. Các role được phép: {sorted(_ASSIGNABLE_ROLES)}"
            )
        return v


class UpdateUserStatusPayload(BaseModel):
    is_active: bool


class UserOut(BaseModel):
    id: int
    username: str
    is_active: bool
    roles: List[str] = []

    class Config:
        from_attributes = True


class CreateUserOut(BaseModel):
    message: str
    user: UserOut  # UserOut.roles đã có tên role vừa gán


# =========================
# TẠO USER
# Tạo user + gán role trong một transaction — rollback cả hai nếu một bước lỗi.
# =========================
@router.post("/", status_code=201, response_model=CreateUserOut)
def create_user(
    payload: CreateUserPayload,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("manage_users"))
):
    # 1. Kiểm tra quyền trước — không để lỗi username lộ thông tin khi chưa đủ quyền
    if payload.role_name == "manager" and "manage_roles" not in current_user["permissions"]:
        raise HTTPException(403, "Cần quyền manage_roles để tạo user với role manager")

    # 2. Kiểm tra nghiệp vụ sau khi quyền đã được xác nhận
    if db.query(models.User).filter(models.User.username == payload.username).first():
        raise HTTPException(400, "Username đã tồn tại")

    # 3. Tạo user + gán role trong cùng một transaction
    try:
        new_user = models.User(
            username=payload.username,
            password=hash_password(payload.password),
            store_id=current_user["store_id"],
            is_active=True,
        )
        db.add(new_user)
        db.flush()  # lấy new_user.id trước khi tạo UserRole, chưa commit

        # Đảm bảo role tồn tại trong DB và có đúng permissions theo template
        role = get_or_create_role(payload.role_name, db)

        db.add(models.UserRole(
            user_id=new_user.id,
            role_id=role.id,
            store_id=current_user["store_id"],
        ))
        db.commit()
        db.refresh(new_user)

        # return nằm trong try — đảm bảo new_user luôn ở trạng thái hợp lệ
        return CreateUserOut(
            message="Tạo user thành công",
            user=UserOut(
                id=new_user.id,
                username=new_user.username,
                is_active=new_user.is_active,
                roles=[payload.role_name],
            ),
        )
    except Exception:
        db.rollback()
        raise


# =========================
# DANH SÁCH USER THEO STORE
# =========================
@router.get("/", response_model=List[UserOut])
def get_users(
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("manage_users"))
):
    users = (
        db.query(models.User)
        .options(joinedload(models.User.roles).joinedload(models.UserRole.role))
        .filter(
            models.User.store_id == current_user["store_id"],
            models.User.deleted_at.is_(None)
        )
        .all()
    )

    return [
        UserOut(
            id=u.id,
            username=u.username,
            is_active=u.is_active,
            roles=[ur.role.name for ur in u.roles if ur.store_id == current_user["store_id"]]
        )
        for u in users
    ]


# =========================
# GET USER BY ID              ✅ thêm mới
# =========================
@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("manage_users"))
):
    user = (
        db.query(models.User)
        .options(joinedload(models.User.roles).joinedload(models.UserRole.role))
        .filter(
            models.User.id == user_id,
            models.User.store_id == current_user["store_id"],
            models.User.deleted_at.is_(None)
        )
        .first()
    )

    if not user:
        raise HTTPException(404, "Không tìm thấy user")

    return UserOut(
        id=user.id,
        username=user.username,
        is_active=user.is_active,
        roles=[ur.role.name for ur in user.roles if ur.store_id == current_user["store_id"]]
    )


# =========================
# BẬT / TẮT USER
# =========================
@router.put("/{user_id}/status")
def toggle_user_status(
    user_id: int,
    payload: UpdateUserStatusPayload,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("manage_users"))
):
    user = db.query(models.User).filter(
        models.User.id == user_id,
        models.User.store_id == current_user["store_id"],
        models.User.deleted_at.is_(None)
    ).first()

    if not user:
        raise HTTPException(404, "Không tìm thấy user")

    if user.id == current_user["user_id"]:
        raise HTTPException(400, "Không thể tự khóa tài khoản của mình")

    user.is_active = payload.is_active
    db.commit()
    return {"message": f"User {'đã kích hoạt' if payload.is_active else 'đã bị khóa'}"}


# =========================
# XÓA USER (SOFT DELETE)
# =========================
@router.delete("/{user_id}", status_code=204)   # ✅ 204 No Content cho DELETE
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("manage_users"))
):
    user = db.query(models.User).filter(
        models.User.id == user_id,
        models.User.store_id == current_user["store_id"],
        models.User.deleted_at.is_(None)
    ).first()

    if not user:
        raise HTTPException(404, "Không tìm thấy user")

    if user.id == current_user["user_id"]:
        raise HTTPException(400, "Không thể tự xóa tài khoản của mình")

    user.deleted_at = datetime.now(timezone.utc)
    db.commit()