from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.security import get_current_user

router = APIRouter(prefix="/roles", tags=["Roles"])


# =========================
# CREATE ROLE
# =========================
@router.post("/")
def create_role(name: str, db: Session = Depends(get_db)):
    exists = db.query(models.Role).filter(models.Role.name == name).first()
    if exists:
        raise HTTPException(400, "Role đã tồn tại")

    role = models.Role(name=name)
    db.add(role)
    db.commit()
    db.refresh(role)

    return role


# =========================
# LIST ROLES
# =========================
@router.get("/")
def get_roles(db: Session = Depends(get_db)):
    return db.query(models.Role).all()


# =========================
# ADD PERMISSION TO ROLE
# =========================
@router.post("/{role_id}/permissions")
def add_permission(role_id: int, permission_name: str, db: Session = Depends(get_db)):
    role = db.query(models.Role).get(role_id)
    if not role:
        raise HTTPException(404, "Role không tồn tại")

    permission = db.query(models.Permission).filter_by(name=permission_name).first()

    if not permission:
        permission = models.Permission(name=permission_name)
        db.add(permission)
        db.commit()
        db.refresh(permission)

    role.permissions.append(permission)
    db.commit()

    return {"msg": "Đã thêm permission"}


# =========================
# ASSIGN ROLE TO USER (THEO STORE)
# =========================
@router.post("/assign")
def assign_role(
    user_id: int,
    role_id: int,
    store_id: int,
    db: Session = Depends(get_db)
):
    exists = db.query(models.UserRole).filter_by(
        user_id=user_id,
        role_id=role_id,
        store_id=store_id
    ).first()

    if exists:
        raise HTTPException(400, "User đã có role này")

    user_role = models.UserRole(
        user_id=user_id,
        role_id=role_id,
        store_id=store_id
    )

    db.add(user_role)
    db.commit()

    return {"msg": "Gán role thành công"}