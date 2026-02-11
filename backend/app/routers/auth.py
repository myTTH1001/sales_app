from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.security import hash_password, verify_password, create_access_token
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Form
router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)



@router.post("/register")
def register(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()
    if user:
        raise HTTPException(status_code=400, detail="User đã tồn tại")

    new_user = User(
        username=username,
        password=hash_password(password)
    )
    db.add(new_user)
    db.commit()
    return {"message": "Đăng ký thành công"}

@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == form_data.username).first()

    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(status_code=401, detail="Sai tài khoản hoặc mật khẩu")
    token = create_access_token({
    "user_id": user.id,
    "sub": user.username,
    "role": user.role
})


    return {
        "access_token": token,
        "token_type": "bearer"
    }

