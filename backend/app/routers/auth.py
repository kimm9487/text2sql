from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import create_access_token, get_current_user
from app.database import app_db
from app.schemas import LoginRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(req: LoginRequest):
    user = app_db.verify_user(req.login_id.strip(), req.password)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "아이디 또는 비밀번호가 올바르지 않습니다")
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": user}


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user
