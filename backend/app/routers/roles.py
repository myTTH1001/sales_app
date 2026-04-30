from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Role, Permission
from app.security import get_current_user

router = APIRouter(prefix="/roles", tags=["Roles"])

@router.get("/")
def get_roles(db: Session = Depends(get_db)):
    roles = db.query(Role).all()

    return [
        {
            "id": r.id,
            "name": r.name,
            "permissions": [p.name for p in r.permissions]
        }
        for r in roles
    ]

@router.post("/")
def create_role(
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    if user["role_id"] != 1:
        raise HTTPException(403, "Không có quyền")

    name = payload.get("name")

    role = Role(name=name)
    db.add(role)
    db.commit()

    return {"message": "Tạo role thành công"}


@router.post("/{role_id}/permissions")
def assign_permissions(
    role_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    if user["role_id"] != 1:
        raise HTTPException(403, "Không có quyền")

    permission_ids = payload.get("permission_ids", [])

    role = db.query(Role).filter(Role.id == role_id).first()

    if not role:
        raise HTTPException(404, "Role không tồn tại")

    permissions = db.query(Permission).filter(
        Permission.id.in_(permission_ids)
    ).all()

    role.permissions = permissions
    db.commit()

    return {"message": "Gán quyền thành công"}

@router.get("/permissions")
def get_permissions(db: Session = Depends(get_db)):
    permissions = db.query(Permission).all()

    return [
        {"id": p.id, "name": p.name}
        for p in permissions
    ]