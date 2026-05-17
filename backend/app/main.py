from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import get_settings
from app.core.database import init_db
from app.api import tasks, images, nests, auth

# 显式引入 models 以确保 SQLAlchemy 的 Base.metadata 在 init_db 时能创建 users 表
from app import models  # noqa: F401

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化数据库
    await init_db()
    yield
    # 关闭时清理资源


app = FastAPI(
    title=settings.APP_NAME,
    description="无人机航拍 + AI自动检测樟巢螟系统",
    version="1.0.0",
    lifespan=lifespan,
)

# 配置 CORS：必须显式列出允许的来源（浏览器规范不允许同时使用 "*" 和 credentials）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(images.router)
app.include_router(nests.router)


@app.get("/")
async def root():
    return {"message": settings.APP_NAME, "version": "1.0.0", "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
