"""认证相关接口：注册 / 登录 / 当前用户"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.models import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    email: Optional[EmailStr] = None


class UserResponse(BaseModel):
    id: str
    username: str
    email: Optional[EmailStr] = None
    is_active: bool
    is_admin: bool

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """注册新用户。

    注意：本接口创建的用户均为普通用户（is_admin=False）。
    管理员账号需要使用 `backend/scripts/create_admin.py` 离线 bootstrap，
    避免之前 "count == 0 -> is_admin=True" 的 race condition（两个并发
    注册请求都能读到 count==0，导致出现多个意外 admin）。
    详见 backend/scripts/README.md。
    """
    # 检查 username 冲突
    exists = await db.execute(select(User).where(User.username == payload.username))
    if exists.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="用户名已存在"
        )

    # email 冲突（如提供）
    if payload.email:
        email_exists = await db.execute(
            select(User).where(User.email == payload.email)
        )
        if email_exists.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="邮箱已被使用"
            )

    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        is_active=True,
        is_admin=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """OAuth2 密码模式登录，返回 JWT access_token"""
    result = await db.execute(
        select(User).where(User.username == form_data.username)
    )
    user = result.scalar_one_or_none()
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号已被禁用",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token({"sub": user.id, "username": user.username})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return current_user
