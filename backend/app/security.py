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


def create_access_token(data: dict):
    return create_token(data, timedelta(minutes=ACCESS_EXPIRE_MINUTES), "access")


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
            "exp": payload["exp"] 
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
        user=Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        permission = db.query(models.Permission).join(
            models.role_permissions,
            models.Permission.id == models.role_permissions.c.permission_id
        ).join(
            models.Role,
            models.Role.id == models.role_permissions.c.role_id
        ).join(
            models.UserRole,
            models.UserRole.role_id == models.Role.id
        ).filter(
            models.UserRole.user_id == user["user_id"],
            models.UserRole.store_id == user["store_id"],
            models.Permission.name == permission_name
        ).first()

        if not permission:
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

        # (optional) rotate refresh token
        blacklist_token(jti, datetime.fromtimestamp(payload["exp"], tz=timezone.utc), db)

        new_payload = {
            "user_id": payload["user_id"],
            "sub": payload["sub"],
            "store_id": payload.get("store_id")
        }

        return {
            "access_token": create_access_token(new_payload),
            "refresh_token": create_refresh_token(new_payload)
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