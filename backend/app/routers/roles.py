# roles.py — bản sửa đầy đủ

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator
from typing import List
from app.database import get_db
from app import models
from app.security import require_permission, get_or_create_role
from app.permissions import ROLE_TEMPLATES, all_permissions

router = APIRouter(prefix="/roles", tags=["Roles"])

# whitelist cố định — tính 1 lần khi module load
_VALID_ROLE_NAMES       = set(ROLE_TEMPLATES.keys())          # owner, manager, staff, cashier
_VALID_PERMISSION_NAMES = set(all_permissions())


# =========================
# SCHEMAS
# =========================
class RoleOut(BaseModel):
    id: int
    name: str
    permissions: List[str] = []

    class Config:
        from_attributes = True


class CreateRolePayload(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Tên role không được để trống")
        return v.lower()


class AssignRolePayload(BaseModel):
    user_id: int
    role_id: int
    store_id: int


# =========================
# CREATE ROLE
# Tạo role theo ROLE_TEMPLATES và seed permissions tương ứng ngay lập tức.
# Idempotent: nếu role đã tồn tại chỉ sync permissions còn thiếu rồi trả về.
# =========================
@router.post("/", response_model=RoleOut, status_code=201)
def create_role(
    payload: CreateRolePayload,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("manage_roles"))
):
    if payload.name not in _VALID_ROLE_NAMES:
        raise HTTPException(
            400,
            f"Role không hợp lệ. Các role được phép: {sorted(_VALID_ROLE_NAMES)}"
        )

    # get_or_create_role xử lý cả tạo mới lẫn đã tồn tại,
    # đồng thời seed đúng permissions theo ROLE_TEMPLATES — không tạo role rỗng.
    role = get_or_create_role(payload.name, db)
    db.commit()
    db.refresh(role)

    return RoleOut(
        id=role.id,
        name=role.name,
        permissions=sorted(p.name for p in role.permissions),
    )


# =========================
# LIST ROLES
# ✅ Chỉ trả về role đang được dùng trong store hiện tại
# =========================
@router.get("/", response_model=List[RoleOut])
def get_roles(
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("manage_roles"))
):
    # Lấy role_id đang được assign trong store này
    store_role_ids = (
        db.query(models.UserRole.role_id)
        .filter(models.UserRole.store_id == current_user["store_id"])
        .distinct()
        .subquery()
    )

    roles = (
        db.query(models.Role)
        .filter(models.Role.id.in_(store_role_ids))
        .all()
    )

    return [
        RoleOut(id=r.id, name=r.name, permissions=[p.name for p in r.permissions])
        for r in roles
    ]


# ⚠️ QUAN TRỌNG: /assignments* phải đứng TRƯỚC /{role_id}*
# vì FastAPI match theo thứ tự — "assignments" sẽ bị hiểu là role_id nếu đặt sau

# =========================
# ASSIGN ROLE TO USER
# ✅ Kiểm tra user thuộc cùng store trước khi assign
# =========================
@router.post("/assignments", status_code=201)
def assign_role(
    payload: AssignRolePayload,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("manage_roles"))
):
    if payload.store_id != current_user["store_id"]:
        raise HTTPException(403, "Không thể gán role cho store khác")

    # ✅ Kiểm tra user tồn tại VÀ thuộc cùng store — tránh cross-tenant
    user = db.query(models.User).filter(
        models.User.id == payload.user_id,
        models.User.store_id == current_user["store_id"],
        models.User.deleted_at.is_(None)
    ).first()
    if not user:
        raise HTTPException(404, "User không tồn tại trong store này")
    if not db.get(models.Role, payload.role_id):
        raise HTTPException(404, "Role không tồn tại")

    exists = db.query(models.UserRole).filter_by(
        user_id=payload.user_id,
        role_id=payload.role_id,
        store_id=payload.store_id
    ).first()
    if exists:
        raise HTTPException(400, "User đã có role này trong store")

    db.add(models.UserRole(
        user_id=payload.user_id,
        role_id=payload.role_id,
        store_id=payload.store_id
    ))
    db.commit()
    return {"msg": "Gán role thành công"}


# =========================
# REMOVE ROLE FROM USER
# ✅ Chặn xóa role cuối cùng của user
# =========================
@router.delete("/assignments/{user_id}/{role_id}", status_code=204)
def remove_role(
    user_id: int,
    role_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("manage_roles"))
):
    user_role = db.query(models.UserRole).filter_by(
        user_id=user_id,
        role_id=role_id,
        store_id=current_user["store_id"]
    ).first()
    if not user_role:
        raise HTTPException(404, "Không tìm thấy assignment này")

    # ✅ Chặn xóa role cuối cùng — tránh user bị "mồ côi"
    remaining = db.query(models.UserRole).filter(
        models.UserRole.user_id == user_id,
        models.UserRole.store_id == current_user["store_id"]
    ).count()
    if remaining <= 1:
        raise HTTPException(400, "Không thể xóa role cuối cùng của user")

    db.delete(user_role)
    db.commit()


# =========================
# GET ROLE BY ID
# =========================
@router.get("/{role_id}", response_model=RoleOut)
def get_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("manage_roles"))
):
    role = db.get(models.Role, role_id)
    if not role:
        raise HTTPException(404, "Role không tồn tại")
    return RoleOut(id=role.id, name=role.name, permissions=[p.name for p in role.permissions])


# =========================
# DELETE ROLE
# =========================
@router.delete("/{role_id}", status_code=204)
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("manage_roles"))
):
    role = db.get(models.Role, role_id)
    if not role:
        raise HTTPException(404, "Role không tồn tại")

    in_use = db.query(models.UserRole).filter_by(role_id=role_id, store_id=current_user["store_id"]
                                                 ).first()
    if in_use:
        raise HTTPException(400, "Không thể xóa role đang được gán cho user")

    db.delete(role)
    db.commit()


# =========================
# ADD PERMISSION TO ROLE
# ✅ Chỉ cho phép permission nằm trong danh sách đã định nghĩa
# =========================
@router.post("/{role_id}/permissions")
def add_permission(
    role_id: int,
    permission_name: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("manage_roles"))
):
    # ✅ Validate trước — không tạo permission tùy ý
    if permission_name not in _VALID_PERMISSION_NAMES:
        raise HTTPException(
            400,
            f"Permission không hợp lệ: '{permission_name}'"
        )

    role = db.get(models.Role, role_id)
    if not role:
        raise HTTPException(404, "Role không tồn tại")

    # Chỉ get từ DB — permissions đã được seed khi startup, không tạo mới
    permission = db.query(models.Permission).filter_by(name=permission_name).first()
    if not permission:
        raise HTTPException(
            500,
            f"Permission '{permission_name}' chưa được seed vào DB. Chạy lại startup."
        )

    if permission not in role.permissions:
        role.permissions.append(permission)
        db.commit()

    return RoleOut(id=role.id, name=role.name, permissions=[p.name for p in role.permissions])


# =========================
# REMOVE PERMISSION FROM ROLE
# =========================
@router.delete("/{role_id}/permissions/{permission_name}")
def remove_permission(
    role_id: int,
    permission_name: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("manage_roles"))
):
    role = db.get(models.Role, role_id)
    if not role:
        raise HTTPException(404, "Role không tồn tại")

    permission = db.query(models.Permission).filter_by(name=permission_name).first()
    if not permission or permission not in role.permissions:
        raise HTTPException(404, "Permission không tồn tại trong role này")

    role.permissions.remove(permission)
    db.commit()
    return RoleOut(id=role.id, name=role.name, permissions=[p.name for p in role.permissions])