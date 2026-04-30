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
# BLACKLIST (IN-MEMORY)
# ========================
blacklist = {}  # {jti: exp_timestamp}
_last_cleanup = 0

def cleanup_blacklist():
    global _last_cleanup
    now = datetime.now(timezone.utc).timestamp()
    if now - _last_cleanup < 60:
        return
    _last_cleanup = now
    expired = [jti for jti, exp in blacklist.items() if exp < now]
    for jti in expired:
        del blacklist[jti]
def blacklist_token(jti: str, exp: datetime):
    blacklist[jti] = exp.timestamp()


def is_token_blacklisted(jti: str) -> bool:
    cleanup_blacklist()
    return jti in blacklist
# ========================
# CURRENT USER
# ========================
def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Check type
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=401,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"}
            )

        # Validate payload
        user_id = payload.get("user_id")
        username = payload.get("sub")
        jti = payload.get("jti")

        if not user_id or not username or not jti:
            raise HTTPException(
                status_code=401,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"}
            )
        if is_token_blacklisted(jti):
            raise HTTPException(
                status_code=401,
                detail="Token revoked",
                headers={"WWW-Authenticate": "Bearer"}
            )
        # TODO: check DB thật
        # user = db.query(User).filter(User.id == user_id).first()
        # if not user:
        #     raise HTTPException(401, "User not found")

        return payload

    except ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"}
        )

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"}
        )


# ========================
# RBAC
# ========================
def require_permission(permission_name: str):
    def checker(
        user=Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        # load role theo store
        user_roles = db.query(models.UserRole).filter(
            models.UserRole.user_id == user.id,
            models.UserRole.store_id == user.store_id
        ).all()

        if not user_roles:
            raise HTTPException(403, "Không có quyền (no role)")

        # lấy tất cả permission
        permissions = []
        for ur in user_roles:
            permissions.extend([p.name for p in ur.role.permissions])

        if permission_name not in permissions:
            raise HTTPException(403, "Không có quyền")

        return user

    return checker


# ========================
# REFRESH TOKEN
# ========================
def refresh_access_token(refresh_token: str):
    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])

        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401,detail="Invalid token type",headers={"WWW-Authenticate": "Bearer"})

        jti = payload.get("jti")

        if is_token_blacklisted(jti):
            raise HTTPException(401, "Token revoked")

        # (optional) rotate refresh token
        blacklist_token(jti, datetime.fromtimestamp(payload["exp"], tz=timezone.utc))

        new_payload = {
            "user_id": payload["user_id"],
            "sub": payload["sub"],
            "role": payload.get("role"),
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
def logout_user(user_payload: dict):
    jti = user_payload.get("jti")
    exp = datetime.fromtimestamp(user_payload["exp"], tz=timezone.utc)

    blacklist_token(jti, exp)

    return {"msg": "Logged out"}