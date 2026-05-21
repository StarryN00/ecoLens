import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 显式引入 models 以确保 SQLAlchemy 的 Base.metadata 在 init_db 时能创建 users 表
from app import models  # noqa: F401
from app.api import admin_users, auth, images, nests, regions, reports, tasks
from app.core.config import get_settings
from app.core.database import init_db
from app.core.logging_config import configure_logging

settings = get_settings()
configure_logging(debug=settings.DEBUG)

try:
    import sentry_sdk
    if settings.SENTRY_DSN:
        sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.1)
except ImportError:
    pass

logger = logging.getLogger(__name__)

# 启动期把最终生效的 CORS 白名单打印出来，便于排查 "前端 CORS 失败" 的问题。
# Settings 的 model_validator 已保证列表非空，这里只需打印。
logger.info("CORS allowed origins: %s", settings.cors_origins_list)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    await init_db()
    yield


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

try:
    from prometheus_fastapi_instrumentator import Instrumentator
    # 自动埋点所有路由，暴露 /metrics 端点
    Instrumentator().instrument(app).expose(app)
except ImportError:
    pass

# 注册路由
app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(images.router)
app.include_router(nests.router)
app.include_router(admin_users.router)
app.include_router(regions.router)
app.include_router(reports.router)


@app.get("/")
async def root():
    return {"message": settings.APP_NAME, "version": "1.0.0", "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
