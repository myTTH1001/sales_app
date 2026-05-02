# roles.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator
from typing import List
from app.database import get_db
from app import models
from app.security import require_permission

router = APIRouter(prefix="/roles", tags=["Roles"])


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
# =========================
@router.post("/", response_model=RoleOut, status_code=201)
def create_role(
    payload: CreateRolePayload,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("manage_roles"))
):
    if db.query(models.Role).filter(models.Role.name == payload.name).first():
        raise HTTPException(400, "Role đã tồn tại")

    role = models.Role(name=payload.name)
    db.add(role)
    db.commit()
    db.refresh(role)
    return RoleOut(id=role.id, name=role.name, permissions=[])


# =========================
# LIST ROLES
# =========================
@router.get("/", response_model=List[RoleOut])
def get_roles(
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("manage_roles"))
):
    roles = db.query(models.Role).all()
    return [
        RoleOut(id=r.id, name=r.name, permissions=[p.name for p in r.permissions])
        for r in roles
    ]


# ⚠️ QUAN TRỌNG: /assignments* phải đứng TRƯỚC /{role_id}*
# vì FastAPI match theo thứ tự — "assignments" sẽ bị hiểu là role_id nếu đặt sau

# =========================
# ASSIGN ROLE TO USER
# =========================
@router.post("/assignments", status_code=201)
def assign_role(
    payload: AssignRolePayload,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("manage_roles"))
):
    if payload.store_id != current_user["store_id"]:
        raise HTTPException(403, "Không thể gán role cho store khác")

    if not db.get(models.User, payload.user_id):
        raise HTTPException(404, "User không tồn tại")
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

    in_use = db.query(models.UserRole).filter_by(role_id=role_id).first()
    if in_use:
        raise HTTPException(400, "Không thể xóa role đang được gán cho user")

    db.delete(role)
    db.commit()


# =========================
# ADD PERMISSION TO ROLE
# =========================
@router.post("/{role_id}/permissions")
def add_permission(
    role_id: int,
    permission_name: str,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("manage_roles"))
):
    role = db.get(models.Role, role_id)
    if not role:
        raise HTTPException(404, "Role không tồn tại")

    permission = db.query(models.Permission).filter_by(name=permission_name).first()
    if not permission:
        permission = models.Permission(name=permission_name)
        db.add(permission)
        db.flush()

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